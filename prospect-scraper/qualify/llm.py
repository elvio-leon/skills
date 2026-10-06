"""Provider AI per la qualifica: Claude (SDK ufficiale ``anthropic``, importato solo quando serve),
OpenAI e Gemini (chiamate HTTP dirette con ``HttpClient.post_json``). Tutti usano lo stesso schema
JSON e sollevano ``ClassifyError`` con un motivo leggibile in italiano. Le chiavi non vengono mai
loggate né incluse nei messaggi."""

from __future__ import annotations

import importlib.util
import json
import re
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
# Alias -> ID esatto inviato all'API (versione fissata del modello)
MODEL_IDS = {"claude-haiku-4-5": "claude-haiku-4-5-20251001"}

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
    meta: dict | None = None      # dettagli della risposta (per la diagnostica)


def cost_usd(model: str, input_tokens: int, output_tokens: int, prices: dict) -> float:
    """Costo in dollari dalla tabella [prezzi] (dollari per milione di token). 0 se il modello è ignoto."""
    prices = prices or {}
    pair = prices.get(model) or prices.get(re.sub(r"-\d{8}$", "", model or ""))   # ID datato -> alias
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


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)


def extract_json(text: str) -> dict:
    """Oggetto JSON dalla risposta del modello. Accetta JSON puro, blocchi ```json ... ``` e testo
    prima o dopo il JSON. Solleva ValueError se non trova un oggetto."""
    text = (text or "").strip()
    candidates = [m.group(1).strip() for m in _FENCE_RE.finditer(text)] + [text]
    decoder = json.JSONDecoder()
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        for i, ch in enumerate(cand):           # primo "{" da cui parte un oggetto JSON valido
            if ch != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(cand, i)
            except ValueError:
                continue
            if isinstance(obj, dict):
                return obj
    raise ValueError("nessun oggetto JSON nella risposta")


def _api_detail(exc: Exception) -> str:
    """Dettaglio di un errore dell'SDK Anthropic: codice HTTP, messaggio dell'API, request id."""
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    message = ""
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        message = str(err.get("message") or "")
    message = message or str(getattr(exc, "message", "") or exc)
    request_id = getattr(exc, "request_id", None)
    parts = [f"HTTP {status}" if status else type(exc).__name__, message[:250]]
    if request_id:
        parts.append(f"request id {request_id}")
    return " | ".join(p for p in parts if p)


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
    def _call(self, system: str, user: str, schema: dict | None = None) -> _Raw:
        """Una chiamata al modello (``schema``: JSON schema della risposta, default quello della
        qualifica). Solleva ``ClassifyError``."""

    def classify(self, system: str, user: str, schema: dict | None = None,
                 validator=None) -> ClassifyResult:
        """Chiamata + validazione. Senza argomenti usa schema e validazione della qualifica agenzie;
        altri compiti (es. il decisore) passano il proprio ``schema`` e ``validator``."""
        validator = validator or validate_analysis
        t0 = time.monotonic()
        tokens_in = tokens_out = 0
        last_text = ""
        for attempt in (1, 2):
            try:
                raw = self._call(system, user, schema) if schema is not None else self._call(system, user)
            except ClassifyError as exc:
                exc.input_tokens += tokens_in
                exc.output_tokens += tokens_out
                exc.latency_s = time.monotonic() - t0
                raise
            tokens_in += raw.input_tokens
            tokens_out += raw.output_tokens
            last_text = raw.text
            try:
                data = validator(extract_json(raw.text))
            except (ValueError, ValidationError) as exc:     # JSON non valido o fuori schema
                log.info("%s: risposta non valida (tentativo %d): %s", self.name, attempt,
                         type(exc).__name__)
                continue
            return ClassifyResult(data, tokens_in, tokens_out, time.monotonic() - t0)
        snippet = re.sub(r"\s+", " ", last_text)[:200]
        raise ClassifyError(f"risposta non valida: «{snippet}»", tokens_in, tokens_out, time.monotonic() - t0)

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
        model = model or CLAUDE_MODELS[0]
        super().__init__(api_key, MODEL_IDS.get(model, model), client)
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

    def _request(self, sdk, system: str, user: str, schema: dict | None = None):
        schema = schema or SCHEMA
        messages = [{"role": "user", "content": user}]
        if self.model == SONNET_MODEL:
            # Sonnet: pensiero adattivo (predefinito), sforzo basso, fallback lato server
            return sdk.beta.messages.create(
                model=self.model, max_tokens=8000, betas=list(SONNET_BETAS), fallbacks="default",
                system=system, messages=messages,
                output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}})
        return sdk.messages.create(
            model=self.model, max_tokens=2000, system=system, messages=messages,
            output_config={"format": {"type": "json_schema", "schema": schema}})

    def _call(self, system: str, user: str, schema: dict | None = None) -> _Raw:
        try:
            import anthropic
        except ImportError:
            raise ClassifyError("libreria «anthropic» non installata") from None
        try:
            response = self._request(self._sdk_client(anthropic), system, user, schema)
        except anthropic.AuthenticationError as exc:
            raise ClassifyError(f"chiave Anthropic non valida ({_api_detail(exc)})") from None
        except anthropic.PermissionDeniedError as exc:
            raise ClassifyError(f"accesso negato dalla chiave Anthropic ({_api_detail(exc)})") from None
        except anthropic.NotFoundError as exc:
            raise ClassifyError(f"modello «{self.model}» non trovato ({_api_detail(exc)})") from None
        except anthropic.RateLimitError as exc:
            raise ClassifyError(f"limite di richieste Anthropic raggiunto ({_api_detail(exc)})") from None
        except anthropic.BadRequestError as exc:
            raise ClassifyError(f"richiesta rifiutata da Anthropic ({_api_detail(exc)})") from None
        except anthropic.APITimeoutError:
            raise ClassifyError(f"timeout dopo {TIMEOUT_S}s") from None
        except anthropic.APIStatusError as exc:
            raise ClassifyError(f"errore dell'API Anthropic ({_api_detail(exc)})") from None
        except anthropic.APIConnectionError as exc:
            cause = exc.__cause__ or exc.__context__
            detail = f"{type(cause).__name__}: {cause}" if cause else str(exc)
            raise ClassifyError(f"connessione ad Anthropic non riuscita ({detail[:250]})") from None
        except Exception as exc:  # noqa: BLE001 - es. librerie mancanti nell'app impacchettata
            log.exception("errore imprevisto nella chiamata ad Anthropic")
            raise ClassifyError(f"errore interno: {type(exc).__name__}: {str(exc)[:250]}") from None
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
            kinds = ", ".join(getattr(b, "type", "?") for b in response.content) or "nessuno"
            raise ClassifyError(f"risposta vuota (stop_reason {stop}, blocchi: {kinds})", *tokens)
        meta = {"id": getattr(response, "id", ""), "model": getattr(response, "model", ""),
                "stop_reason": stop, "input_tokens": tokens[0], "output_tokens": tokens[1]}
        return _Raw(text, *tokens, meta=meta)


# --- OpenAI (HTTP) -------------------------------------------------------------------
class OpenAIClassifier(Classifier):
    name = "openai"
    label = "OpenAI"
    who = "OpenAI"

    def _call(self, system: str, user: str, schema: dict | None = None) -> _Raw:
        name = "agency_qualification" if schema is None else "structured_answer"
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": name, "strict": True, "schema": schema or SCHEMA}},
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

    def _call(self, system: str, user: str, schema: dict | None = None) -> _Raw:
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "responseJsonSchema": schema or SCHEMA, "maxOutputTokens": 4000,
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
