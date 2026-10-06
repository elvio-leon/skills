"""Agenzie: schema, classificatori (Claude via SDK finto, OpenAI e Gemini via HttpClient finto),
score e qualificatore (non solleva mai)."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import anthropic
import pytest
from pydantic import ValidationError

from config import settings
from qualify import config as qc
from qualify import llm
from qualify.blog import BlogInfo
from qualify.llm import (ClaudeClassifier, ClassifyError, GeminiClassifier, OpenAIClassifier, cost_usd,
                         get_classifier)
from qualify.models import Qualification
from qualify.pages import PageText, SiteContent
from qualify.qualifier import classify_and_score, qualify_site
from qualify.schema import SCHEMA, validate_analysis
from qualify.scoring import compute_score
from scrapers.http import FetchError
from tests.agency_helpers import FakeClassifier, FakePagesClient, analysis

try:
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx  # type: ignore[no-redef]


# ---------------------------------------------------------------------- schema ---
def test_schema_is_strict_compatible():
    assert SCHEMA["additionalProperties"] is False
    assert set(SCHEMA["required"]) == set(SCHEMA["properties"]) and len(SCHEMA["properties"]) == 12
    banned = {"minLength", "maxLength", "minItems", "maxItems", "pattern", "format", "minimum", "maximum"}

    def walk(node):
        if isinstance(node, dict):
            assert not banned & set(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(SCHEMA)
    assert SCHEMA["properties"]["size_signal"]["enum"] == ["1", "2-5", "6-20", "20+", "non determinabile"]
    assert len(SCHEMA["properties"]["servizi"]["items"]["enum"]) == 13


def test_validate_analysis_clamps_and_rejects_invalid():
    out = validate_analysis(analysis(seo_evidence="x" * 500, note="n" * 900, servizi=["seo", "seo", "adv"],
                                     verticali=[f"v{i}" for i in range(12)] + [""]))
    assert len(out["seo_evidence"]) == 300 and len(out["note"]) == 400
    assert out["servizi"] == ["seo", "adv"] and len(out["verticali"]) == 8
    for bad in (analysis(is_agency="forse"), analysis(servizi=["magia"]), analysis(size_signal="3"),
                {k: v for k, v in analysis().items() if k != "note"}):
        with pytest.raises(ValidationError):
            validate_analysis(bad)
    with pytest.raises(ValueError):
        validate_analysis([1])
    assert validate_analysis({**analysis(), "extra": 1})["is_agency"] == "si"       # chiavi extra ignorate


# ------------------------------------------------------------------------ Claude ---
class FakeSdk:
    """Finto ``anthropic.Anthropic``: registra le chiamate a messages.create e beta.messages.create."""

    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls: list[tuple[str, dict]] = []
        self.messages = SimpleNamespace(create=lambda **kw: self._create("messages", kw))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: self._create("beta", kw)))

    def _create(self, kind, kw):
        self.calls.append((kind, kw))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def msg(blocks, stop="end_turn", tokens=(1200, 300)):
    return SimpleNamespace(stop_reason=stop, content=blocks,
                           usage=SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1]))


def text(s):
    return SimpleNamespace(type="text", text=s)


def thinking():
    return SimpleNamespace(type="thinking", thinking="ragiono...", text=None)


def api_error(cls, status):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("errore", response=httpx.Response(status, request=request), body=None)


def test_claude_haiku_request_shape_and_parsing():
    sdk = FakeSdk([msg([text(json.dumps(analysis()))])])
    c = ClaudeClassifier("sk-key", "claude-haiku-4-5", sdk_client=sdk)
    assert c.is_configured()
    res = c.classify("SISTEMA", "UTENTE")
    assert res.data["is_agency"] == "si" and (res.input_tokens, res.output_tokens) == (1200, 300)
    kind, kw = sdk.calls[0]
    assert kind == "messages"
    assert kw == {"model": "claude-haiku-4-5", "max_tokens": 2000, "system": "SISTEMA",
                  "messages": [{"role": "user", "content": "UTENTE"}],
                  "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}}}
    assert "thinking" not in kw and "temperature" not in kw


def test_claude_sonnet_uses_beta_call_with_fallbacks_and_skips_thinking_blocks():
    sdk = FakeSdk([msg([thinking(), SimpleNamespace(type="fallback", text=None), text(json.dumps(analysis(seo_level="strutturata")))],
                       tokens=(2000, 1500))])
    c = ClaudeClassifier("sk-key", "claude-sonnet-5-5", sdk_client=sdk)
    res = c.classify("SISTEMA", "UTENTE")
    assert res.data["seo_level"] == "strutturata" and res.output_tokens == 1500
    kind, kw = sdk.calls[0]
    assert kind == "beta"
    assert kw["model"] == "claude-sonnet-5-5" and kw["max_tokens"] == 8000
    assert kw["betas"] == ["server-side-fallback-2026-07-01"] and kw["fallbacks"] == "default"
    assert kw["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert kw["system"] == "SISTEMA" and kw["messages"] == [{"role": "user", "content": "UTENTE"}]
    assert "thinking" not in kw and "temperature" not in kw


@pytest.mark.parametrize("model", ["claude-haiku-4-5", "claude-sonnet-5-5"])
def test_claude_stop_reasons(model):
    refusal = FakeSdk([msg([], stop="refusal")])
    with pytest.raises(ClassifyError, match="il modello ha rifiutato la richiesta"):
        ClaudeClassifier("k", model, sdk_client=refusal).classify("s", "u")
    truncated = FakeSdk([msg([text('{"is_agency":')], stop="max_tokens", tokens=(500, 2000))])
    with pytest.raises(ClassifyError, match="risposta troncata") as exc:
        ClaudeClassifier("k", model, sdk_client=truncated).classify("s", "u")
    assert exc.value.output_tokens == 2000                                  # il costo non si perde
    with pytest.raises(ClassifyError, match="risposta vuota"):
        ClaudeClassifier("k", model, sdk_client=FakeSdk([msg([thinking()])])).classify("s", "u")


@pytest.mark.parametrize("error, reason", [
    (api_error(anthropic.AuthenticationError, 401), "chiave Anthropic non valida"),
    (api_error(anthropic.PermissionDeniedError, 403), "accesso negato"),
    (api_error(anthropic.NotFoundError, 404), "modello non trovato"),
    (api_error(anthropic.RateLimitError, 429), "limite di richieste Anthropic raggiunto"),
    (api_error(anthropic.BadRequestError, 400), "richiesta rifiutata"),
    (anthropic.APITimeoutError(httpx.Request("POST", "https://api.anthropic.com")), "timeout"),
    (api_error(anthropic.InternalServerError, 500), r"errore dell'API Anthropic \(HTTP 500\)"),
    (anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com")), "connessione"),
])
def test_claude_error_mapping(error, reason):
    sdk = FakeSdk([error])
    with pytest.raises(ClassifyError, match=reason) as exc:
        ClaudeClassifier("sk-secret", "claude-haiku-4-5", sdk_client=sdk).classify("s", "u")
    assert "sk-secret" not in exc.value.reason


def test_claude_retries_once_on_invalid_json_then_fails_and_sums_tokens():
    sdk = FakeSdk([msg([text("non è json")], tokens=(100, 10)), msg([text(json.dumps(analysis()))], tokens=(100, 20))])
    res = ClaudeClassifier("k", "claude-haiku-4-5", sdk_client=sdk).classify("s", "u")
    assert len(sdk.calls) == 2 and (res.input_tokens, res.output_tokens) == (200, 30)
    bad = FakeSdk([msg([text("{}")], tokens=(100, 10)), msg([text('{"is_agency": "boh"}')], tokens=(100, 10)),
                   msg([text("{}")])])
    with pytest.raises(ClassifyError, match="risposta non valida") as exc:
        ClaudeClassifier("k", "claude-haiku-4-5", sdk_client=bad).classify("s", "u")
    assert len(bad.calls) == 2 and exc.value.input_tokens == 200


def test_claude_is_configured_requires_key_and_sdk():
    assert not ClaudeClassifier("", "claude-haiku-4-5").is_configured()
    assert ClaudeClassifier("k", "claude-haiku-4-5").is_configured()           # anthropic è installato
    assert ClaudeClassifier("", "claude-haiku-4-5", sdk_client=FakeSdk()).is_configured()


class _Echo(BaseHTTPRequestHandler):
    seen: list = []

    def log_message(self, *a):
        pass

    def do_POST(self):  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Echo.seen.append({"path": self.path, "body": body, "key": self.headers.get("x-api-key"),
                           "beta": self.headers.get("anthropic-beta")})
        out = json.dumps({"id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                          "content": [{"type": "text", "text": json.dumps(analysis())}],
                          "stop_reason": "end_turn", "stop_sequence": None,
                          "usage": {"input_tokens": 10, "output_tokens": 5}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)


@pytest.mark.parametrize("model, beta", [("claude-haiku-4-5", False), ("claude-sonnet-5-5", True)])
def test_claude_with_the_real_sdk_against_a_local_server(model, beta):
    """L'SDK reale accetta i parametri e serializza la richiesta come previsto (nessuna rete esterna)."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Echo)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    _Echo.seen.clear()
    try:
        sdk = anthropic.Anthropic(api_key="sk-test", base_url=f"http://127.0.0.1:{httpd.server_address[1]}",
                                  timeout=5.0, max_retries=0)
        res = ClaudeClassifier("sk-test", model, sdk_client=sdk).classify("sistema", "utente")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert res.data["is_agency"] == "si" and (res.input_tokens, res.output_tokens) == (10, 5)
    seen = _Echo.seen[0]
    assert seen["key"] == "sk-test" and seen["body"]["model"] == model and seen["body"]["system"] == "sistema"
    assert seen["body"]["output_config"]["format"]["schema"] == SCHEMA
    if beta:
        assert seen["body"]["fallbacks"] == "default" and seen["body"]["output_config"]["effort"] == "low"
        assert "server-side-fallback-2026-07-01" in (seen["beta"] or "") and seen["body"]["max_tokens"] == 8000
    else:
        assert "effort" not in seen["body"]["output_config"] and seen["body"]["max_tokens"] == 2000


# ------------------------------------------------------------------ OpenAI/Gemini ---
def openai_ok(data=None, **over):
    body = {"choices": [{"message": {"content": json.dumps(data or analysis())}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 7000, "completion_tokens": 600}}
    body.update(over)
    return body


def gemini_ok(data=None, **over):
    body = {"candidates": [{"content": {"parts": [{"text": "pensiero", "thought": True},
                                                  {"text": json.dumps(data or analysis())}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 6000, "candidatesTokenCount": 500, "thoughtsTokenCount": 300}}
    body.update(over)
    return body


def test_openai_request_shape_and_parsing(monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_URL", "http://127.0.0.1:1/v1/chat/completions")
    client = FakePagesClient()
    client.post_responses = [openai_ok()]
    c = OpenAIClassifier("sk-oa", "gpt-5.4-mini", client)
    res = c.classify("SISTEMA", "UTENTE")
    assert (res.input_tokens, res.output_tokens) == (7000, 600) and res.data["seo_level"] == "accennata"
    call = client.posts[0]
    assert call["url"] == "http://127.0.0.1:1/v1/chat/completions" and call["timeout"] == 60
    assert call["headers"] == {"Authorization": "Bearer sk-oa"}
    assert call["payload"] == {
        "model": "gpt-5.4-mini",
        "messages": [{"role": "system", "content": "SISTEMA"}, {"role": "user", "content": "UTENTE"}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "agency_qualification", "strict": True, "schema": SCHEMA}},
        "reasoning_effort": "low", "max_completion_tokens": 4000}


@pytest.mark.parametrize("response, reason", [
    ({"choices": [{"message": {"content": None, "refusal": "no"}, "finish_reason": "stop"}]}, "rifiutato"),
    ({"choices": [{"message": {"content": "{"}, "finish_reason": "length"}]}, "risposta troncata"),
    ({"choices": []}, "risposta vuota"),
    (FetchError("chiave API non valida (HTTP 401) da api.openai.com"), "chiave OpenAI non valida"),
    (FetchError("limite di ricerche raggiunto (HTTP 429) da api.openai.com"), "limite di richieste OpenAI"),
    (FetchError("HTTP 404 (pagina non trovata) da api.openai.com"), "modello non trovato"),
    (TimeoutError("x"), "errore: TimeoutError"),
])
def test_openai_errors(response, reason):
    client = FakePagesClient()
    client.post_responses = [response]
    with pytest.raises(ClassifyError, match=reason):
        OpenAIClassifier("k", "gpt-5.4-mini", client).classify("s", "u")


def test_gemini_request_shape_and_parsing(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_URL", "http://127.0.0.1:1/v1beta")
    client = FakePagesClient()
    client.post_responses = [gemini_ok()]
    res = GeminiClassifier("g-key", "gemini-2.5-flash", client).classify("SISTEMA", "UTENTE")
    assert res.data["is_agency"] == "si" and res.input_tokens == 6000 and res.output_tokens == 800   # 500 + 300 di pensiero
    call = client.posts[0]
    assert call["url"] == "http://127.0.0.1:1/v1beta/models/gemini-2.5-flash:generateContent"
    assert call["headers"] == {"x-goog-api-key": "g-key"}
    assert call["payload"] == {
        "systemInstruction": {"parts": [{"text": "SISTEMA"}]},
        "contents": [{"role": "user", "parts": [{"text": "UTENTE"}]}],
        "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": SCHEMA,
                             "maxOutputTokens": 4000, "thinkingConfig": {"thinkingBudget": 512}}}
    assert "thought" not in json.dumps(res.data)                              # il blocco di pensiero è escluso


@pytest.mark.parametrize("response, reason", [
    ({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{"}]}}]}, "risposta troncata"),
    ({"candidates": [{"finishReason": "SAFETY"}]}, "bloccata da Gemini"),
    ({"candidates": [{"finishReason": "RECITATION"}]}, "bloccata da Gemini"),
    ({"candidates": []}, "risposta vuota"),
    ({"promptFeedback": {"blockReason": "PROHIBITED_CONTENT"}}, "bloccata da Gemini"),
    (FetchError("limite di ricerche raggiunto (HTTP 429) da generativelanguage.googleapis.com"),
     "limite di richieste Google raggiunto"),
    (FetchError("chiave API non valida (HTTP 403) da x"), "chiave Google non valida"),
])
def test_gemini_errors(response, reason):
    client = FakePagesClient()
    client.post_responses = [response]
    with pytest.raises(ClassifyError, match=reason):
        GeminiClassifier("k", "gemini-2.5-flash", client).classify("s", "u")


@pytest.mark.parametrize("cls, ok", [(OpenAIClassifier, openai_ok), (GeminiClassifier, gemini_ok)])
def test_http_providers_retry_once_on_invalid_json(cls, ok):
    client = FakePagesClient()
    broken = openai_ok() if cls is OpenAIClassifier else gemini_ok()
    if cls is OpenAIClassifier:
        broken["choices"][0]["message"]["content"] = "non json"
    else:
        broken["candidates"][0]["content"]["parts"] = [{"text": "non json"}]
    client.post_responses = [broken, ok()]
    res = cls("k", "m", client).classify("s", "u")
    assert len(client.posts) == 2 and res.data["is_agency"] == "si"
    client.post_responses = [broken, broken, ok()]
    with pytest.raises(ClassifyError, match="risposta non valida"):
        cls("k", "m", client).classify("s", "u")
    assert len(client.posts) == 4                                             # 2 + 2, mai 3 tentativi


def test_cost_and_registry(tmp_path, monkeypatch):
    prices = {"claude-haiku-4-5": [1.0, 5.0], "claude-sonnet-5-5": [2.0, 10.0]}
    assert cost_usd("claude-haiku-4-5", 8000, 800, prices) == pytest.approx(0.012)
    assert cost_usd("claude-sonnet-5-5", 8000, 2000, prices) == pytest.approx(0.036)
    assert cost_usd("sconosciuto", 10**6, 10**6, prices) == 0.0
    assert set(llm.CLASSIFIERS) == {"claude", "openai", "gemini"}

    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    for var in ("PS_LLM_PROVIDER", "PS_CLAUDE_MODEL", "PS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY",
                "PS_OPENAI_API_KEY", "OPENAI_API_KEY", "PS_GEMINI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    default = get_classifier()
    assert default.name == "claude" and default.model == "claude-haiku-4-5" and not default.is_configured()
    from config import user_settings
    user_settings.save({"claude_model": "claude-sonnet-5-5", "anthropic_api_key": "k", "openai_api_key": "o"})
    assert get_classifier("claude").model == "claude-sonnet-5-5" and get_classifier("claude").is_configured()
    assert get_classifier("claude", model="claude-haiku-4-5").model == "claude-haiku-4-5"
    user_settings.save({"claude_model": "modello-inventato"})
    assert get_classifier("claude").model == "claude-haiku-4-5"               # valore non ammesso: Haiku
    g = get_classifier("openai")
    assert g.name == "openai" and g.model == "gpt-5.4-mini" and g.is_configured()
    assert get_classifier("gemini").model == "gemini-2.5-flash" and not get_classifier("gemini").is_configured()
    assert get_classifier("boh").name == "claude"


# --------------------------------------------------------------------- punteggio ---
@pytest.fixture()
def weights(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    return qc.load_scoring()


def q_(**over):
    return validate_analysis(analysis(**over))


def test_score_rules_each_signal(weights):
    best = q_(seo_level="assente", servizi_ricorrenti="si", size_signal="6-20")
    assert compute_score(best, "assente", weights) == (100, {
        "seo_level": 40, "servizi_ricorrenti": 25, "size_signal": 25, "blog": 10, "is_agency": 0})
    assert compute_score(best, "fermo", weights)[0] == 100 and compute_score(best, "attivo", weights)[0] == 90
    assert compute_score(best, "non determinabile", weights)[0] == 90
    worst = q_(seo_level="strutturata", servizi_ricorrenti="no", size_signal="non determinabile")
    assert compute_score(worst, "attivo", weights)[0] == 0
    mid = q_(seo_level="accennata", servizi_ricorrenti="no", size_signal="2-5")
    assert compute_score(mid, "attivo", weights)[0] == 40
    for size, pts in {"1": 5, "2-5": 15, "6-20": 25, "20+": 5}.items():
        assert compute_score(q_(seo_level="strutturata", servizi_ricorrenti="no", size_signal=size),
                             "attivo", weights)[0] == pts


def test_score_doubt_penalty_exclusion_and_clamp(weights):
    base = dict(seo_level="assente", servizi_ricorrenti="si", size_signal="6-20")
    score, breakdown = compute_score(q_(is_agency="dubbio", **base), "assente", weights)
    assert score == 80 and breakdown["is_agency"] == -20
    assert compute_score(q_(is_agency="no", **base), "assente", weights) == (None, {})
    low = q_(is_agency="dubbio", seo_level="strutturata", servizi_ricorrenti="no", size_signal="non determinabile")
    assert compute_score(low, "attivo", weights)[0] == 0                      # mai sotto il minimo
    capped = {**weights, "limiti": {"min": 10, "max": 60}}
    assert compute_score(q_(**base), "assente", capped)[0] == 60
    assert compute_score(low, "attivo", capped)[0] == 10


def test_score_with_custom_weights_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    qc.save_scoring_text('[seo_level]\nassente = 5\n[blog]\nassente = 0\nfermo = 0\n[limiti]\nmax = 50\n')
    w = qc.load_scoring()
    best = q_(seo_level="assente", servizi_ricorrenti="si", size_signal="6-20")
    assert compute_score(best, "assente", w)[0] == 50                         # 5+25+25 = 55 -> tetto 50


# ------------------------------------------------------------------ qualificatore ---
def content(pages=True, error="", blog="assente", last=None):
    c = SiteContent(domain="a.it", home_url="https://a.it/", error=error,
                    blog=BlogInfo(blog, last, "https://a.it/blog" if blog != "assente" else "", ""))
    if pages:
        c.pages = [PageText("home", "https://a.it/", "A", "testo"), PageText("servizi", "https://a.it/servizi", "S", "testo")]
    return c


def test_classify_and_score_ok_excluded_and_failures(weights):
    clf = FakeClassifier({"a.it": analysis(seo_level="assente", size_signal="6-20")})
    q = classify_and_score(content(blog="fermo", last=__import__("datetime").date(2024, 1, 2)), clf, weights)
    assert q.status == "ok" and q.score == 100 and q.is_agency == "si" and q.blog_status == "fermo"
    assert q.blog_last_post == "2024-01-02" and q.pages_used == ["https://a.it/", "https://a.it/servizi"]
    assert q.evidence == {"agenzia": "agenzia web e SEO", "seo": "SEO, social media",
                          "ricorrenti": "canone mensile", "team": "team di 4 persone"}
    assert q.llm_provider == "fake" and q.llm_model == "fake-model" and q.qualified_at
    assert (q.input_tokens, q.output_tokens) == (8000, 800) and q.latency_s == 0.5
    assert q.score_breakdown["seo_level"] == 40 and q.servizi == ["siti_web", "seo"]
    assert "Dominio: a.it" in clf.calls[0][1] and "SCHEMA" not in clf.calls[0][1]

    excl = classify_and_score(content(), FakeClassifier({"a.it": analysis(is_agency="no")}), weights)
    assert excl.status == "excluded" and excl.score is None and excl.is_agency == "no"

    failed = classify_and_score(content(), FakeClassifier({"a.it": ClassifyError("limite di richieste Anthropic raggiunto", 10, 0)}), weights)
    assert failed.status == "failed" and failed.error == "limite di richieste Anthropic raggiunto" and failed.score is None
    assert failed.input_tokens == 10 and failed.pages_used == ["https://a.it/", "https://a.it/servizi"]

    nohome = classify_and_score(content(pages=False, error="timeout"), clf, weights)
    assert nohome.status == "failed" and nohome.error == "timeout"


def test_qualifier_never_raises(weights):
    class Boom(FakeClassifier):
        def classify(self, system, user):
            raise ZeroDivisionError("bug")
    q = classify_and_score(content(), Boom(), weights)
    assert q.status == "failed" and "ZeroDivisionError" in q.error
    assert classify_and_score(content(), FakeClassifier(), {}).status == "failed"        # pesi rotti
    prospect = SimpleNamespace(website="https://a.it/")
    class BoomClient(FakePagesClient):
        def get(self, *a, **k):
            raise RuntimeError("giù")
    q = qualify_site(prospect, BoomClient(), FakeClassifier(), weights)
    assert q.status == "failed" and q.error == "errore: RuntimeError"           # home non raggiungibile
    assert qualify_site(SimpleNamespace(website=None), FakePagesClient(), FakeClassifier(), weights).status == "failed"


def test_qualify_site_end_to_end_with_fake_http(weights):
    pages = {"https://a.it/": (200, "text/html", '<html><head><title>A</title></head><body><a href="/servizi">Servizi</a>'
                                                  '<a href="/blog">Blog</a><p>Agenzia</p></body></html>'),
             "https://a.it/servizi": (200, "text/html", "<html><body>SEO e social</body></html>"),
             "https://a.it/blog": (200, "text/html", "<html><body>niente date</body></html>")}
    clf = FakeClassifier()
    q = qualify_site(SimpleNamespace(website="https://a.it/"), FakePagesClient(pages), clf, weights)
    assert q.status == "ok" and q.blog_status == "non determinabile" and len(q.pages_used) == 2
    q2 = qualify_site(SimpleNamespace(website="https://b.it/"), FakePagesClient(pages), clf, weights)
    assert q2.status == "failed" and "404" in q2.error


def test_qualification_row_roundtrip():
    q = Qualification(status="ok", servizi=["seo"], verticali=["vino"], score=77, score_breakdown={"blog": 10},
                      evidence={"seo": "x"}, pages_used=["https://a.it/"], cost_usd=0.012, input_tokens=5)
    back = Qualification.from_row(q.to_row())
    assert back == q
    assert Qualification.from_row({}).score is None
