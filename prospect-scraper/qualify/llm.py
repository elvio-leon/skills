"""Provider AI per la qualifica: Claude (SDK ufficiale ``anthropic``, importato solo quando serve),
OpenAI e Gemini (chiamate HTTP dirette con ``HttpClient.post_json``). Tutti usano lo stesso schema
JSON e sollevano ``ClassifyError`` con un motivo leggibile in italiano. Le chiavi non vengono mai
loggate né incluse nei messaggi."""

from __future__ import annotations

import importlib.util
import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import ValidationError

from config import settings, user_settings
from qualify import config as qconfig
from qualify.schema import SCHEMA, validate_analysis
from scrapers.http import FetchError, HttpClient, default_client, describe_exception
from utils.logging import get_logger

log = get_logger("qualify.llm")

TIMEOUT_S = 60
CLAUDE_MODELS = ("claude-haiku-4-5", "claude-sonnet-5-5")
SONNET_MODEL = "claude-sonnet-5-5"
SONNET_BETAS = ["server-side-fallback-2026-07-01"]

PROVIDER_LABELS = {"claude": "Anthropic", "openai": "OpenAI", "gemini": "Google Gemini"}
KEY_SETTINGS = {"claude": "anthropic_api_key", "openai": "openai_api_key", "gemini": "gemini_api_key"}


class ClassifyError(Exception):
    """Classificazione fallita: ``reason`` è un testo breve in italiano per l'utente."""

    def __init__(self, reason: str, input_tokens: int = 0, output_tokens: int = 0,
                 latency_s: float = 0.0):
        super().__init__(reason)
        self.reason = reason
        self.input_tokens, self.output_tokens, self.latency_s = input_tokens, output_tokens, latency_s


@dataclass
class ClassifyResult:
    data: dict
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0


@dataclass
class _Raw:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


def cost_usd(model: str, input_tokens: int, output_tokens: int, prices: dict) -> float:
    """Costo in dollari dalla tabella [prezzi] (dollari per milione di token). 0 se il modello è ignoto."""
    pair = (prices or {}).get(model)
    if not pair or len(pair) != 2:
        return 0.0
    return (input_tokens * float(pair[0]) + output_tokens * float(pair[1])) / 1_000_000


def _http_reason(message: str, who: str) -> str:
    """Messaggio leggibile da un errore di ``HttpClient.post_json``."""
    for code in ("401", "403"):
        if f"HTTP {code}" in message:
            return f"chiave {who} non valida"
    if "HTTP 429" in message:
        return f"limite di richieste {who} raggiunto"
    if "HTTP 404" in message:
        return "modello non trovato"
    if "HTTP 400" in message:
        return f"richiesta rifiutata da {who}"
    if message.startswith("rate limit"):
        return f"limite di richieste {who} raggiunto"
    return message[:160]


class Classifier(ABC):
    """Un provider = un modo di chiamare un modello. ``classify`` fa al più un secondo tentativo
    se la risposta non è un JSON valido."""

    name = "base"
    label = "Base"
    who = "AI"

    def __init__(self, api_key: str = "", model: str = "", client: HttpClient | None = None):
        self.api_key = (api_key or "").strip()
        self.model = model
        self.client = client

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @abstractmethod
    def _call(self, system: str, user: str) -> _Raw:
        """Una chiamata al modello. Solleva ``ClassifyError``."""

    def classify(self, system: str, user: str) -> ClassifyResult:
        t0 = time.monotonic()
        tokens_in = tokens_out = 0
        for attempt in (1, 2):
            try:
                raw = self._call(system, user)
            except ClassifyError as exc:
                exc.input_tokens += tokens_in
                exc.output_tokens += tokens_out
                exc.latency_s = time.monotonic() - t0
                raise
            tokens_in += raw.input_tokens
            tokens_out += raw.output_tokens
            try:
                data = validate_analysis(json.loads(raw.text))
            except (ValueError, ValidationError) as exc:     # JSON non valido o fuori schema
                log.info("%s: risposta non valida (tentativo %d): %s", self.name, attempt,
                         type(exc).__name__)
                continue
            return ClassifyResult(data, tokens_in, tokens_out, time.monotonic() - t0)
        raise ClassifyError("risposta non valida", tokens_in, tokens_out, time.monotonic() - t0)

    def _post(self, url: str, payload: dict, headers: dict) -> dict:
        client = self.client or default_client()
        try:
            out = client.post_json(url, payload, headers=headers, min_interval=0, timeout=TIMEOUT_S)
        except FetchError as exc:
            raise ClassifyError(_http_reason(str(exc), self.who)) from None
        except Exception as exc:  # noqa: BLE001
            raise ClassifyError(describe_exception(exc)) from None
        if not isinstance(out, dict):
            raise ClassifyError("risposta non valida")
        return out


# --- Claude (SDK anthropic) ---------------------------------------------------------
class ClaudeClassifier(Classifier):
    name = "claude"
    label = "Claude"
    who = "Anthropic"

    def __init__(self, api_key: str = "", model: str = "", client: HttpClient | None = None,
                 sdk_client=None):
        super().__init__(api_key, model or CLAUDE_MODELS[0], client)
        self._sdk = sdk_client
        self._lock = threading.Lock()

    def is_configured(self) -> bool:
        if self._sdk is not None:
            return True
        return bool(self.api_key) and importlib.util.find_spec("anthropic") is not None

    def _sdk_client(self, anthropic):
        with self._lock:
            if self._sdk is None:
                self._sdk = anthropic.Anthropic(api_key=self.api_key, timeout=float(TIMEOUT_S),
                                                max_retries=2)
            return self._sdk

    def _request(self, sdk, system: str, user: str):
        messages = [{"role": "user", "content": user}]
        if self.model == SONNET_MODEL:
            # Sonnet: pensiero adattivo (predefinito), sforzo basso, fallback lato server
            return sdk.beta.messages.create(
                model=self.model, max_tokens=8000, betas=list(SONNET_BETAS), fallbacks="default",
                system=system, messages=messages,
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}})
        return sdk.messages.create(
            model=self.model, max_tokens=2000, system=system, messages=messages,
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}})

    def _call(self, system: str, user: str) -> _Raw:
        try:
            import anthropic
        except ImportError:
            raise ClassifyError("libreria «anthropic» non installata") from None
        try:
            response = self._request(self._sdk_client(anthropic), system, user)
        except anthropic.AuthenticationError:
            raise ClassifyError("chiave Anthropic non valida") from None
        except anthropic.PermissionDeniedError:
            raise ClassifyError("accesso negato dalla chiave Anthropic") from None
        except anthropic.NotFoundError:
            raise ClassifyError("modello non trovato") from None
        except anthropic.RateLimitError:
            raise ClassifyError("limite di richieste Anthropic raggiunto") from None
        except anthropic.BadRequestError as exc:
            detail = str(getattr(exc, "message", "") or "")[:120]
            raise ClassifyError("richiesta rifiutata da Anthropic" + (f": {detail}" if detail else "")) from None
        except anthropic.APITimeoutError:
            raise ClassifyError("timeout") from None
        except anthropic.APIStatusError as exc:
            raise ClassifyError(f"errore dell'API Anthropic (HTTP {getattr(exc, 'status_code', '?')})") from None
        except anthropic.APIConnectionError:
            raise ClassifyError("connessione ad Anthropic non riuscita") from None
        usage = getattr(response, "usage", None)
        tokens = (int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0))
        stop = getattr(response, "stop_reason", None)
        if stop == "refusal":
            raise ClassifyError("il modello ha rifiutato la richiesta", *tokens)
        if stop == "max_tokens":
            raise ClassifyError("risposta troncata", *tokens)
        # il primo blocco "text": salta i blocchi di pensiero e di fallback
        text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), None)
        if not text:
            raise ClassifyError("risposta vuota", *tokens)
        return _Raw(text, *tokens)


# --- OpenAI (HTTP) -------------------------------------------------------------------
class OpenAIClassifier(Classifier):
    name = "openai"
    label = "OpenAI"
    who = "OpenAI"

    def _call(self, system: str, user: str) -> _Raw:
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "agency_qualification", "strict": True, "schema": SCHEMA}},
            "reasoning_effort": "low",
            "max_completion_tokens": 4000,
        }
        out = self._post(settings.OPENAI_API_URL, payload,
                         {"Authorization": f"Bearer {self.api_key}"})
        usage = out.get("usage") or {}
        tokens = (int(usage.get("prompt_tokens") or 0), int(usage.get("completion_tokens") or 0))
        choices = out.get("choices") or []
        if not choices:
            raise ClassifyError("risposta vuota", *tokens)
        choice = choices[0] or {}
        message = choice.get("message") or {}
        if message.get("refusal"):
            raise ClassifyError("il modello ha rifiutato la richiesta", *tokens)
        finish = choice.get("finish_reason")
        if finish == "length":
            raise ClassifyError("risposta troncata", *tokens)
        if finish == "content_filter":
            raise ClassifyError("risposta bloccata dal filtro di OpenAI", *tokens)
        if not message.get("content"):
            raise ClassifyError("risposta vuota", *tokens)
        return _Raw(message["content"], *tokens)


# --- Gemini (HTTP) -------------------------------------------------------------------
_GEMINI_BLOCKED = {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "OTHER"}


class GeminiClassifier(Classifier):
    name = "gemini"
    label = "Gemini"
    who = "Google"

    def _call(self, system: str, user: str) -> _Raw:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "responseJsonSchema": SCHEMA, "maxOutputTokens": 4000,
                                 "thinkingConfig": {"thinkingBudget": 512}},
        }
        url = f"{settings.GEMINI_API_URL.rstrip('/')}/models/{self.model}:generateContent"
        out = self._post(url, payload, {"x-goog-api-key": self.api_key})
        usage = out.get("usageMetadata") or {}
        tokens = (int(usage.get("promptTokenCount") or 0),
                  int(usage.get("candidatesTokenCount") or 0) + int(usage.get("thoughtsTokenCount") or 0))
        block = (out.get("promptFeedback") or {}).get("blockReason")
        if block:
            raise ClassifyError(f"richiesta bloccata da Gemini ({block})", *tokens)
        candidates = out.get("candidates") or []
        if not candidates:
            raise ClassifyError("risposta vuota", *tokens)
        cand = candidates[0] or {}
        finish = cand.get("finishReason")
        if finish == "MAX_TOKENS":
            raise ClassifyError("risposta troncata", *tokens)
        if finish in _GEMINI_BLOCKED:
            raise ClassifyError(f"risposta bloccata da Gemini ({finish})", *tokens)
        parts = (cand.get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if not text:
            raise ClassifyError("risposta vuota", *tokens)
        return _Raw(text, *tokens)


CLASSIFIERS: dict[str, type[Classifier]] = {
    "claude": ClaudeClassifier,
    "openai": OpenAIClassifier,
    "gemini": GeminiClassifier,
}


def provider_name(provider: str | None = None) -> str:
    chosen = (provider or user_settings.get("llm_provider", "claude")).strip().lower()
    return chosen if chosen in CLASSIFIERS else "claude"


def model_for(provider: str, scoring: dict | None = None) -> str:
    """Modello del provider: per Claude quello scelto in ``claude_model`` (Haiku o Sonnet)."""
    llm = (scoring or qconfig.load_scoring())["llm"]
    if provider == "claude":
        wanted = user_settings.get("claude_model", llm["claude"])
        allowed = {llm["claude"], llm.get("claude_alt", SONNET_MODEL)}
        return wanted if wanted in allowed else llm["claude"]
    return llm[provider]


def get_classifier(provider: str | None = None, client: HttpClient | None = None,
                   model: str | None = None) -> Classifier:
    """Classificatore del provider scelto (default: quello nelle impostazioni) con chiave e modello salvati."""
    name = provider_name(provider)
    return CLASSIFIERS[name](user_settings.get(KEY_SETTINGS[name]), model or model_for(name),
                             client or default_client())
