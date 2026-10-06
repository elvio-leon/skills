"""Diagnosi del caso "qualifica fallita su tutte le agenzie": motivo visibile, parser JSON tollerante,
ID del modello, prova di connessione e riqualifica senza nuova ricerca."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from config import settings
from core.pipeline import AGENCY_CATEGORY, MODE_BOTH
from database.db import Database
from qualify import llm
from qualify.diagnose import mask_key, run_diagnosis
from qualify.llm import ClaudeClassifier, ClassifyError, cost_usd, extract_json
from tests.agency_helpers import FakeClassifier, analysis
from tests.test_agency_pipeline import APP_PATH, app_env, env, run_agency, srv  # noqa: F401 (fixture)

KEY_ERROR = "chiave Anthropic non valida (HTTP 401 | invalid x-api-key)"


# --- parser JSON --------------------------------------------------------------
@pytest.mark.parametrize("text", [
    '{"a": 1}',
    '```json\n{"a": 1}\n```',
    'Ecco la classificazione:\n```json\n{"a": 1}\n```\nSpero sia utile.',
    '```\n{"a": 1}\n```',
    'Risultato: {"a": 1} (fine)',
    'testo {non json} poi {"a": 1}',
])
def test_extract_json_handles_fences_and_surrounding_text(text):
    assert extract_json(text) == {"a": 1}


def test_extract_json_nested_and_failure():
    assert extract_json('prima {"a": {"b": [1, 2]}} dopo') == {"a": {"b": [1, 2]}}
    with pytest.raises(ValueError):
        extract_json("nessun JSON qui")


def test_classify_accepts_fenced_json_from_the_model():
    class Fenced(FakeClassifier):
        def classify(self, system, user):            # usa la logica reale di Classifier.classify
            return llm.Classifier.classify(self, system, user)

        def _call(self, system, user):
            import json
            return llm._Raw("Certo! Ecco il JSON:\n```json\n" + json.dumps(analysis()) + "\n```", 10, 5)

    assert Fenced().classify("s", "u").data["is_agency"] == "si"


def test_invalid_answer_reason_contains_the_text():
    class Bad(FakeClassifier):
        def classify(self, system, user):
            return llm.Classifier.classify(self, system, user)

        def _call(self, system, user):
            return llm._Raw("Mi dispiace, non posso aiutarti.", 10, 5)

    with pytest.raises(ClassifyError) as err:
        Bad().classify("s", "u")
    assert "risposta non valida" in err.value.reason and "Mi dispiace" in err.value.reason


# --- modello e costi ------------------------------------------------------------
def test_haiku_uses_the_exact_dated_model_id():
    assert ClaudeClassifier("k").model == "claude-haiku-4-5-20251001"
    assert ClaudeClassifier("k", "claude-haiku-4-5").model == "claude-haiku-4-5-20251001"
    assert ClaudeClassifier("k", "claude-sonnet-5-5").model == "claude-sonnet-5-5"
    prices = {"claude-haiku-4-5": [1.0, 5.0]}
    assert cost_usd("claude-haiku-4-5-20251001", 8000, 800, prices) == pytest.approx(0.012)


def test_sent_request_uses_dated_model_id():
    sent = {}

    class Messages:
        def create(self, **kw):
            sent.update(kw)
            import json
            block = SimpleNamespace(type="text", text=json.dumps(analysis()))
            return SimpleNamespace(content=[block], stop_reason="end_turn", id="msg_1", model=kw["model"],
                                   usage=SimpleNamespace(input_tokens=100, output_tokens=50))

    fake_sdk = SimpleNamespace(messages=Messages())
    result = ClaudeClassifier("sk-ant-x", sdk_client=fake_sdk).classify("s", "u")
    assert sent["model"] == "claude-haiku-4-5-20251001" and result.data["seo_level"] == "accennata"


# --- errori dettagliati dall'SDK reale -------------------------------------------
def test_real_sdk_errors_carry_status_and_api_message():
    import anthropic
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(400, request=request, headers={"request-id": "req_123"},
                               json={"type": "error", "error": {"type": "invalid_request_error",
                                     "message": "Your credit balance is too low to access the Anthropic API."}})
    exc = anthropic.BadRequestError("bad", response=response, body=response.json())

    class Messages:
        def create(self, **kw):
            raise exc

    with pytest.raises(ClassifyError) as err:
        ClaudeClassifier("k", sdk_client=SimpleNamespace(messages=Messages())).classify("s", "u")
    reason = err.value.reason
    assert "HTTP 400" in reason and "credit balance is too low" in reason and "req_123" in reason


def test_unexpected_exception_becomes_readable_reason():
    class Messages:
        def create(self, **kw):
            raise ModuleNotFoundError("No module named 'qualcosa'")

    with pytest.raises(ClassifyError) as err:
        ClaudeClassifier("k", sdk_client=SimpleNamespace(messages=Messages())).classify("s", "u")
    assert err.value.reason.startswith("errore interno: ModuleNotFoundError") and "qualcosa" in err.value.reason


# --- prova di connessione ---------------------------------------------------------
def test_diagnosis_reports_raw_answer_and_masks_key():
    import json

    class Messages:
        def create(self, **kw):
            block = SimpleNamespace(type="text", text="```json\n" + json.dumps(analysis()) + "\n```")
            return SimpleNamespace(content=[block], stop_reason="end_turn", id="msg_9", model=kw["model"],
                                   usage=SimpleNamespace(input_tokens=900, output_tokens=200))

    key = "sk-ant-api03-ABCDEFGHIJKLMNOP-wxyz"
    report = run_diagnosis(ClaudeClassifier(key, sdk_client=SimpleNamespace(messages=Messages())))
    assert report["esito"] == "OK" and report["json_interpretato"]["is_agency"] == "si"
    assert report["dettagli_risposta"]["stop_reason"] == "end_turn" and "```json" in report["risposta_grezza"]
    assert key not in str(report) and report["chiave"].endswith("wxyz (34 caratteri)")
    assert mask_key("") == "(nessuna chiave)"


def test_diagnosis_reports_full_error():
    import anthropic
    import httpx2

    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(401, request=request, json={"type": "error", "error": {
        "type": "authentication_error", "message": "invalid x-api-key"}})

    class Messages:
        def create(self, **kw):
            raise anthropic.AuthenticationError("auth", response=response, body=response.json())

    report = run_diagnosis(ClaudeClassifier("sk-ant-0123456789abcdef", sdk_client=SimpleNamespace(messages=Messages())))
    assert report["esito"] == "ERRORE" and report["errore"] == KEY_ERROR


@pytest.mark.skipif(not os.environ.get("PS_LIVE_ANTHROPIC_401"), reason="chiamata reale facoltativa")
def test_live_api_rejects_fake_key_with_401():
    report = run_diagnosis(ClaudeClassifier("sk-ant-api03-chiave-finta-per-test-0000"))
    assert "HTTP 401" in report["errore"]


# --- il caso dell'utente: tutte fallite, poi riqualifica senza nuova ricerca ------
def test_all_failed_then_requalify_same_results_without_new_search(env, srv, monkeypatch):
    pipe, db, messages, progress = env
    broken = FakeClassifier({}, model="claude-haiku-4-5-20251001")
    broken.classify = lambda system, user: (_ for _ in ()).throw(ClassifyError(KEY_ERROR))
    result, provider, _ = run_agency(env, srv, monkeypatch, {}, classifier=broken)
    quals = db.get_qualifications(result.prospect_ids)
    attempted = [q for q in quals.values()]
    assert attempted and all(q.status == "failed" and q.error == KEY_ERROR for q in attempted)
    assert all(q.score is None and q.blog_status for q in attempted)          # il blog c'è, i campi AI no
    searches = provider.calls if hasattr(provider, "calls") else None

    fixed = FakeClassifier({})
    monkeypatch.setattr(llm, "get_classifier", lambda provider=None, client=None, model=None: fixed)
    messages.clear()
    rq = pipe.requalify(result.prospect_ids, result.run_id)
    assert not rq.fatal_error
    if searches is not None:
        assert provider.calls == searches                                     # nessuna nuova ricerca
    quals = db.get_qualifications(result.prospect_ids)
    assert all(q.status in ("ok", "excluded") and not q.error for q in quals.values())
    assert any(q.score is not None for q in quals.values())
    assert rq.n_qualified + rq.n_excluded == len(attempted) and rq.n_qual_failed == 0
    assert any(lvl == "success" and "Qualifica completata" in t for lvl, t in messages)


def test_streamlit_shows_reason_column_banner_and_requalify(app_env, monkeypatch):
    from models.prospect import Prospect
    from qualify.models import Qualification
    from streamlit.testing.v1 import AppTest

    db = Database()
    run = db.start_run(mode=MODE_BOTH, category=AGENCY_CATEGORY, keyword="agenzie", location="Italia")
    for i in range(3):
        p = Prospect(company_name=f"Agenzia {i}", website=f"https://agenzia{i}.it", status="enriched",
                     category=AGENCY_CATEGORY)
        db.link_run(run, db.save(p))
        db.save_qualification(p.id, run, Qualification(status="failed", error=KEY_ERROR, blog_status="attivo"))
    db.finish_run(run, n_found=3, n_unique=3, n_enriched=3, n_failed=0)

    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert not at.exception
    df = at.dataframe[0].value
    assert (df["Motivo"] == f"qualifica fallita: {KEY_ERROR}").all()
    assert any("Qualifica fallita su **3 di 3**" in e.value and KEY_ERROR in e.value for e in at.error)
    assert any(b.label == "Rilancia qualifica" for b in at.button)
