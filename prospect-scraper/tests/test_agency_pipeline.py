"""Agenzie: pipeline end-to-end (Web Search finta + siti locali + classificatore finto), database,
export e interfaccia Streamlit."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from config import settings, user_settings
from core import pipeline as pipeline_mod
from core.pipeline import (AGENCY_CATEGORY, MODE_BOTH, SOURCE_AGENCY, SOURCE_LOCAL, SOURCE_WEB, WEB_CATEGORY,
                           Pipeline, RunParams)
from database.db import Database
from exporters.export import prospects_to_dataframe, to_csv_bytes, to_xlsx_bytes
from qualify import config as qc
from qualify import llm
from qualify.llm import ClassifyError
from scrapers import web_search
from scrapers.http import HttpClient
from scrapers.website import WebsiteCrawler
from tests.agency_helpers import FakeClassifier, FakeWebProvider, analysis
from tests.agency_sites import HOST_BLU, HOST_GRIGIO, HOST_OTHER, HOST_ROSSO, HOST_VERDE, AgencySites
from tests.site_server import SiteServer


@pytest.fixture(scope="module")
def srv():
    with AgencySites() as s:
        yield s


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "USE_PLAYWRIGHT", False)
    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    for var in ("PS_LLM_PROVIDER", "PS_CLAUDE_MODEL", "PS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    client = HttpClient(delay=0, timeout=2, retries=0)
    db = Database(tmp_path / "t.db")
    messages, progress = [], []
    pipe = Pipeline(db, client, WebsiteCrawler(client, time_budget=20),
                    on_message=lambda t, lvl="info": messages.append((lvl, t)),
                    on_progress=lambda d, n, label="": progress.append((d, n, label)))
    return pipe, db, messages, progress


def agency_items(srv):
    return [
        (srv.url(HOST_ROSSO, "/"), "Studio Rosso | Agenzia web e SEO"),
        (srv.url(HOST_ROSSO, "/blog/migliori-agenzie-web"), "Studio Rosso blog"),      # frase nell'URL
        (srv.url(HOST_OTHER, "/"), "Sito in blacklist per dominio"),
        ("https://www.listicle-example.it/p", "Le migliori agenzie SEO d'Italia"),       # frase nel titolo
        ("https://www.clutch.co/it/agencies/seo", "Clutch"),                             # dominio predefinito
        (srv.url(HOST_BLU, "/"), "Web Agency Blu"),
        (srv.url(HOST_VERDE, "/"), "Verde Shop"),
        (srv.url(HOST_GRIGIO, "/"), "Grigio Studio"),
    ]


def run_agency(env, srv, monkeypatch, behaviors, qualify=True, classifier=None):
    pipe, db, messages, progress = env
    qc.save_blacklist_text(qc.blacklist_text() + f"\n[domini]\n{HOST_OTHER}\n")
    provider = FakeWebProvider(agency_items(srv))
    classifier = classifier or FakeClassifier(behaviors)
    monkeypatch.setattr(web_search, "get_provider", lambda name=None, client=None: provider)
    monkeypatch.setattr(llm, "get_classifier", lambda provider=None, client=None, model=None: classifier)

    def no_local(*a, **k):
        raise AssertionError("la ricerca locale non deve partire")
    monkeypatch.setattr(pipeline_mod, "run_search", no_local)
    params = RunParams(category=AGENCY_CATEGORY, keyword="agenzia web marketing", location="Italia",
                       max_results=20, mode=MODE_BOTH, search_source=SOURCE_AGENCY, web_provider="fake",
                       llm_provider="claude", qualify=qualify)
    return pipe.run(params), provider, classifier


def test_agency_pipeline_end_to_end(env, srv, monkeypatch):
    pipe, db, messages, progress = env
    behaviors = {
        HOST_ROSSO: analysis(seo_level="assente", size_signal="2-5"),
        HOST_BLU: analysis(is_agency="dubbio", seo_level="accennata", size_signal="6-20", servizi_ricorrenti="no"),
        HOST_VERDE: analysis(is_agency="no"),
        HOST_GRIGIO: ClassifyError("limite di richieste Anthropic raggiunto"),
    }
    res, provider, clf = run_agency(env, srv, monkeypatch, behaviors)
    assert not res.fatal_error, res.log_text
    texts = [t for _, t in messages]
    assert texts[0] == "Searching the web (Fake)..."
    assert "4 risultati scartati dalla blacklist" in texts   # URL, titolo, clutch.co, dominio aggiunto
    assert "Qualifying agencies..." in texts

    # nessuna richiesta ai siti in blacklist, né per dominio né per frase nell'URL
    assert HOST_OTHER not in srv.hosts_hit()
    assert "/blog/migliori-agenzie-web" not in srv.paths_hit(HOST_ROSSO)
    assert res.n_found == 4 and res.n_unique == 4 and res.n_enriched == 4

    assert (res.n_qualified, res.n_excluded, res.n_qual_failed) == (2, 1, 1)
    assert res.llm_cost_usd == 0.0                                               # modello finto: prezzo ignoto
    summary = texts[-1]
    assert summary.startswith("Completed in") and "2 qualificate, 1 esclusa, 1 fallita, costo AI 0,000 $" in summary
    assert progress[-1][:2] == (4, 4)

    prospects = {p.domain: p for p in db.list_prospects(ids=res.prospect_ids)}
    assert set(prospects) == {HOST_ROSSO, HOST_BLU, HOST_VERDE, HOST_GRIGIO}
    assert all(p.category == AGENCY_CATEGORY and p.status == "enriched" for p in prospects.values())
    quals = db.get_qualifications([p.id for p in prospects.values()])
    by_domain = {d: quals[p.id] for d, p in prospects.items()}
    rosso = by_domain[HOST_ROSSO]
    assert rosso.status == "ok" and rosso.score == 40 + 25 + 15 + 0 + 0 and rosso.blog_status == "attivo"
    assert rosso.blog_last_post and len(rosso.pages_used) == 4 and rosso.note
    assert by_domain[HOST_BLU].status == "ok" and by_domain[HOST_BLU].is_agency == "dubbio"
    assert by_domain[HOST_BLU].blog_status == "fermo" and by_domain[HOST_BLU].score == 25 + 0 + 25 + 10 - 20
    assert by_domain[HOST_VERDE].status == "excluded" and by_domain[HOST_VERDE].score is None
    assert by_domain[HOST_GRIGIO].status == "failed" and "limite di richieste" in by_domain[HOST_GRIGIO].error
    # la qualifica non cambia lo status del prospect
    assert prospects[HOST_GRIGIO].status == "enriched" and not prospects[HOST_GRIGIO].error_message

    # ogni testo inviato all'AI è il contenuto delle pagine del sito (home inclusa)
    assert len(clf.calls) == 4 and all(u.startswith("Dominio: 127.0.0.") for _, u in clf.calls)
    rosso_msg = next(u for _, u in clf.calls if HOST_ROSSO in u.splitlines()[0])
    assert "### [servizi]" in rosso_msg and "canone mensile" in rosso_msg and "### [portfolio]" in rosso_msg
    assert "/portfolio" not in srv.paths_hit(HOST_BLU)                           # robots.txt di Blu
    assert "### [portfolio]" not in next(u for _, u in clf.calls if HOST_BLU in u.splitlines()[0])

    run = db.list_runs()[0]
    assert run["category"] == AGENCY_CATEGORY and run["providers"] == "fake,fake-model"

    # la pipeline conserva gli esiti dell'enrichment per riusare le pagine
    assert set(pipe.last_enrichment) == {p.id for p in prospects.values()}

    # export: colonne di qualifica solo per i dati delle agenzie
    plist = db.list_prospects(ids=res.prospect_ids)
    df = prospects_to_dataframe(plist, quals)
    cols = list(df.columns)
    assert cols[:2] == ["Company", "Score"] and cols[2:12] == [
        "Is agency", "SEO level", "Servizi ricorrenti", "Size", "Blog", "Ultimo post blog", "Servizi",
        "Servizi (altro)", "Verticali", "Note"]
    assert cols[-9:] == ["Qualifica status", "Qualifica errore", "Prova agenzia", "Prova SEO", "Prova ricorrenti",
                         "Prova team", "Pagine analizzate", "Modello AI", "Costo AI ($)"]
    rows = list(csv.DictReader(io.StringIO(to_csv_bytes(df).decode("utf-8-sig"))))
    r_rosso = next(r for r in rows if r["Domain"] == HOST_ROSSO)
    assert r_rosso["Score"] == "80" and r_rosso["Servizi"] == "siti_web, seo" and r_rosso["Qualifica status"] == "ok"
    assert r_rosso["Prova SEO"] == "SEO, social media" and r_rosso["Modello AI"] == "fake-model"
    assert r_rosso["Pagine analizzate"].count(",") == 3
    r_fail = next(r for r in rows if r["Domain"] == HOST_GRIGIO)
    assert r_fail["Score"] == "" and "limite di richieste" in r_fail["Qualifica errore"]
    assert next(r for r in rows if r["Domain"] == HOST_VERDE)["Qualifica status"] == "excluded"
    assert to_xlsx_bytes(df)


def test_agency_run_without_configured_key_skips_qualification(env, srv, monkeypatch):
    res, _, clf = run_agency(env, srv, monkeypatch, {}, classifier=FakeClassifier(configured=False))
    _, db, messages, _ = env
    assert not res.fatal_error and res.n_enriched == 4
    assert ("warning", "Qualifica non configurata: inserisci la chiave API in «Impostazioni Agenzie»") in messages
    assert clf.calls == [] and db.get_qualifications(res.prospect_ids) == {}
    assert "qualificat" not in messages[-1][1]


def test_agency_run_with_qualify_false_only_discovers_and_enriches(env, srv, monkeypatch):
    res, _, clf = run_agency(env, srv, monkeypatch, {}, qualify=False)
    _, db, messages, _ = env
    assert res.n_enriched == 4 and clf.calls == [] and db.get_qualifications(res.prospect_ids) == {}
    assert not any("Qualifica" in t or "Qualifying" in t for _, t in messages)
    assert db.list_runs()[0]["providers"] == "fake"


def test_agency_requalification_after_cache_and_failed_enrichment_not_qualified(env, srv, monkeypatch):
    pipe, db, messages, _ = env
    first, _, _ = run_agency(env, srv, monkeypatch, {})
    messages.clear()
    second, _, clf = run_agency(env, srv, monkeypatch, {HOST_VERDE: analysis(is_agency="no")})
    assert second.n_cached == 4                                                  # arricchiti di recente
    assert second.n_qualified + second.n_excluded == 4 and len(clf.calls) == 4  # qualificati anche senza enrichment
    assert pipe.last_enrichment == {}                                            # nessun risultato in cache
    quals = db.get_qualifications(second.prospect_ids)
    assert len(quals) == 4 and sorted(first.prospect_ids) == sorted(second.prospect_ids)


def test_local_and_web_runs_still_produce_old_columns(env, srv, monkeypatch):
    pipe, db, messages, _ = env
    old = ["Company", "Website", "Domain", "Country", "Region", "City", "Address", "Postal code", "Category",
           "Phone", "All phones", "Email", "All emails", "LinkedIn", "Instagram", "Facebook", "YouTube",
           "X / Twitter", "VAT ID", "Description", "Source", "Source URL", "Search query", "Status", "Error",
           "First seen", "Last seen", "ID"]
    web = FakeWebProvider([(srv.url(HOST_ROSSO, "/"), "Studio Rosso")])
    monkeypatch.setattr(web_search, "get_provider", lambda name=None, client=None: web)
    monkeypatch.setattr(llm, "get_classifier", lambda *a, **k: (_ for _ in ()).throw(AssertionError("niente AI")))
    res = pipe.run(RunParams(category=WEB_CATEGORY, keyword="agenzia", mode=MODE_BOTH, search_source=SOURCE_WEB,
                             web_provider="fake"))
    assert not res.fatal_error and res.n_enriched == 1 and res.n_qualified == 0
    assert db.list_runs()[0]["providers"] == "fake" and "blacklist" not in " ".join(t for _, t in messages)
    prospects = db.list_prospects(ids=res.prospect_ids)
    assert prospects[0].category == WEB_CATEGORY and db.get_qualifications(res.prospect_ids) == {}
    assert list(prospects_to_dataframe(prospects).columns) == old
    assert messages[-1][1].startswith("Completed in") and "qualificat" not in messages[-1][1]

    # Local (OSM + Wikidata): stessa cosa
    class Report:
        results = []
        errors: dict = {}
        counts: dict = {}
    monkeypatch.setattr(pipeline_mod, "run_search", lambda *a, **k: Report())
    local = pipe.run(RunParams(category="Custom", keyword="hotel", mode=MODE_BOTH, providers=["osm"]))
    assert not local.fatal_error and RunParams().search_source == SOURCE_LOCAL
    assert RunParams().llm_provider is None and RunParams().qualify is True


def test_web_result_category_is_overridable_only_for_agencies():
    from core.pipeline import web_result_to_prospect
    from scrapers.search.base import SearchResult
    r = SearchResult("Acme", "https://acme.it/", "", "fake")
    assert web_result_to_prospect(r, RunParams(), "q").category == WEB_CATEGORY
    assert web_result_to_prospect(r, RunParams(), "q", AGENCY_CATEGORY).category == AGENCY_CATEGORY


# ------------------------------------------------------------------ interfaccia ---
APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    import streamlit as st

    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "data" / "prospects.db")
    monkeypatch.setattr(settings, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(settings, "SEARXNG_URL", "")
    monkeypatch.setattr(settings, "DESKTOP", False)
    for var in ("PS_TAVILY_API_KEY", "PS_BRAVE_API_KEY", "PS_SEARXNG_URL", "PS_WEB_PROVIDER", "PS_LLM_PROVIDER",
                "PS_CLAUDE_MODEL", "PS_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", "PS_OPENAI_API_KEY",
                "OPENAI_API_KEY", "PS_GEMINI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    st.cache_resource.clear()
    return tmp_path


def test_streamlit_agency_sidebar_smoke(app_env):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert not at.exception
    assert at.segmented_control(key="search_source").options == ["Local (OSM + Wikidata)", "Web Search", "Agenzie"]

    at.segmented_control(key="search_source").set_value("Agenzie").run()
    assert not at.exception
    assert any(e.label == "Impostazioni Agenzie" for e in at.sidebar.expander)
    assert not any(s.label == "Tipo di ricerca" for s in at.selectbox)
    assert at.text_input(key="ag_keyword").placeholder == "es. agenzia web marketing, agenzia di comunicazione"
    assert at.text_input(key="ag_location").placeholder == "es. Milano, Lombardia, Italia"
    choice = at.selectbox(key="ag_llm_choice")
    assert choice.value == "claude" and choice.options == [
        "Claude Haiku 4.5 (economico)", "Claude Sonnet 5.5 (più accurato)", "OpenAI GPT-5.4 mini",
        "Google Gemini 2.5 Flash"]
    assert at.text_input(key="ag_secret_claude").proto.type == 1                  # password
    assert "[seo_level]" in at.text_area(key="ag_scoring").value and "[domini]" in at.text_area(key="ag_blacklist").value
    est = [c.value for c in at.sidebar.caption if c.value.startswith("Costo stimato")]
    assert est and "0.012 $" in est[0]                                            # Haiku: 8000 in + 800 out

    at.selectbox(key="ag_llm_choice").select("claude_alt").run()
    est = [c.value for c in at.sidebar.caption if c.value.startswith("Costo stimato")]
    assert "0.036 $" in est[0] and "2000 out" in est[0]                           # Sonnet: 2000 out per il pensiero
    at.selectbox(key="ag_llm_choice").select("openai").run()
    assert at.text_input(key="ag_secret_openai").label == "Chiave API"

    # validazione di CERCA PROSPECT: keyword, Web Search, chiave AI
    next(b for b in at.button if b.label == "CERCA PROSPECT").click().run()
    assert any("keyword" in e.value for e in at.sidebar.error)
    at.text_input(key="ag_keyword").set_value("agenzia web")
    next(b for b in at.button if b.label == "CERCA PROSPECT").click().run()
    assert any("Web Search non configurata" in e.value for e in at.sidebar.error)
    user_settings.save({"tavily_api_key": "tvly-x"})
    next(b for b in at.button if b.label == "CERCA PROSPECT").click().run()
    assert any("Chiave AI non configurata" in e.value for e in at.sidebar.error)

    # salvataggio della chiave e del modello Claude
    at.selectbox(key="ag_llm_choice").select("claude_alt").run()
    at.text_input(key="ag_secret_claude").set_value("sk-ant-test")
    at.button(key="ag_save").click().run()
    assert not at.exception
    saved = json.loads((app_env / "user_settings.json").read_text())
    assert saved["anthropic_api_key"] == "sk-ant-test" and saved["llm_provider"] == "claude"
    assert saved["claude_model"] == "claude-sonnet-5-5"

    # blacklist e pesi: salvataggio e rifiuto di un file non valido
    at.text_area(key="ag_blacklist").set_value("[domini]\nesempio.it\n[frasi]\nofferta\n")
    at.button(key="ag_save_blacklist").click().run()
    assert qc.load_blacklist().domains == {"esempio.it"}
    original = qc.scoring_text()
    at.text_area(key="ag_scoring").set_value("[seo_level\nrotto")
    at.button(key="ag_save_scoring").click().run()
    assert not at.exception and any("Pesi non salvati" in e.value for e in at.sidebar.error)
    assert qc.scoring_text() == original

    at.segmented_control(key="search_source").set_value("Local (OSM + Wikidata)").run()
    assert not at.exception and any(s.label == "Tipo di ricerca" for s in at.selectbox)
    assert not any(e.label == "Impostazioni Agenzie" for e in at.sidebar.expander)


def test_streamlit_agency_results_table(app_env):
    """Una ricerca Agenzie salvata: colonne di qualifica, ordine per score, filtri, status; le altre viste restano com'erano."""
    from models.prospect import Prospect
    from qualify.models import Qualification
    from streamlit.testing.v1 import AppTest

    db = Database()
    run = db.start_run(mode=MODE_BOTH, category=AGENCY_CATEGORY, keyword="agenzie", location="Italia")
    specs = [("Bassa", "ok", 20, ""), ("Alta", "ok", 90, ""), ("Esclusa", "excluded", None, ""),
             ("Fallita", "failed", None, "timeout"), ("Media", "ok", 55, "")]
    for name, status, score, err in specs:
        p = Prospect(company_name=name, website=f"https://{name.lower()}.it", status="enriched", category=AGENCY_CATEGORY)
        db.link_run(run, db.save(p))
        db.save_qualification(p.id, run, Qualification(status=status, score=score, error=err, is_agency="no" if status == "excluded" else "si",
                                                        servizi=["seo", "adv"], note=f"nota {name}"))
    other = db.start_run(mode=MODE_BOTH, category="Web Search", keyword="web")
    plain = Prospect(company_name="Normale", website="https://normale.it", status="enriched")
    db.link_run(other, db.save(plain))

    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert not at.exception
    # ultima ricerca = quella Web (la più recente): nessuna colonna di qualifica
    assert not any(s.label == "Score minimo" for s in at.slider)
    at.segmented_control(key="view").set_value("Ricerche salvate").run()
    assert not at.exception
    runs_box = next(s for s in at.selectbox if s.label == "Ricerca")
    runs_box.select_index(1).run()                                                # la ricerca Agenzie
    assert not at.exception
    assert any(s.label == "Score minimo" for s in at.slider) and any(c.label == "Mostra escluse" for c in at.checkbox)
    df = at.dataframe[0].value
    assert list(df["Company"]) == ["Alta", "Media", "Bassa", "Fallita"]            # Score decrescente, None in fondo, esclusa nascosta
    assert df["Status"].tolist()[-1] == "⚠️ failed" and df["Error"].tolist()[-1] == "qualifica: timeout"
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Prospect"] == "4" and metrics["Falliti"] == "1"
    at.checkbox[next(i for i, c in enumerate(at.checkbox) if c.label == "Mostra escluse")].check().run()
    df = at.dataframe[0].value
    assert "Esclusa" in list(df["Company"]) and df.loc[df["Company"] == "Esclusa", "Status"].iloc[0] == "🚫 esclusa"
    assert {m.label: m.value for m in at.metric}["Falliti"] == "1"
    at.slider[next(i for i, s in enumerate(at.slider) if s.label == "Score minimo")].set_value(50).run()
    assert list(at.dataframe[0].value["Company"]) == ["Alta", "Media"]
