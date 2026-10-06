"""«Trova contatti»: decisore dal sito (AI + verifica sul testo), LinkedIn solo dai risultati di ricerca,
email dal sito o ipotesi, pipeline sui record già nel database, stato outreach, export e interfaccia."""

from __future__ import annotations

import csv
import io

import pytest

from config import settings
from core import pipeline as pipeline_mod
from core.pipeline import AGENCY_CATEGORY, MODE_BOTH, Pipeline
from database.db import Database
from decision_makers import finder
from decision_makers.email import guess_email, nominative_email
from decision_makers.extract import (PEOPLE_GROUPS, SCHEMA, choose_person, collect_people_pages,
                                     validate_people)
from decision_makers.linkedin import agency_name, build_query, pick_profile, profile_url
from decision_makers.models import DecisionMaker
from exporters.export import outreach_changes, prospects_to_dataframe, to_csv_bytes
from models.prospect import Prospect
from qualify import llm
from qualify.llm import ClassifyError, ClassifyResult
from qualify.models import Qualification
from scrapers import web_search
from scrapers.http import FetchError, HttpClient, never_open
from scrapers.search.base import SearchResult
from scrapers.web_search.tavily import TavilyProvider
from tests.agency_helpers import FakeClassifier, FakePagesClient, FakeWebProvider
from tests.test_agency_pipeline import APP_PATH, app_env  # noqa: F401 (fixture)

SITE = "https://www.agenziarossi.it/"
FILLER = "Realizziamo siti web, campagne e strategie digitali per le aziende del territorio. " * 120


def html(body: str, title: str = "Agenzia Rossi") -> str:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


def rossi_pages() -> dict:
    home = html(f"""
        <nav><a href="/chi-siamo">Chi siamo</a> <a href="/team">Il team</a> <a href="/contatti">Contatti</a>
        <a href="/blog/articolo">Blog</a> <a href="https://www.linkedin.com/company/agenzia-rossi">LinkedIn</a></nav>
        <main>{FILLER}</main>
        <footer>Agenzia Rossi di Mario Rossi – P.IVA 01234567890 – info@agenziarossi.it</footer>""",
                "Home - Agenzia Rossi | Web Marketing Milano")
    return {
        SITE: (200, "text/html", home),
        "https://www.agenziarossi.it/chi-siamo": (200, "text/html", html(
            "<h1>Chi siamo</h1><p>Agenzia Rossi è stata fondata nel 2010 da Mario Rossi, CEO e fondatore, "
            "insieme alla socia Giulia Bianchi.</p>")),
        "https://www.agenziarossi.it/team": (200, "text/html", html(
            "<h2>Team</h2><p>Mario Rossi – CEO &amp; Founder</p><p>Giulia Bianchi – Partner</p>"
            "<p>Luca Verdi – SEO Specialist</p><p>Scrivi a <a href='mailto:mario.rossi@agenziarossi.it'>Mario</a></p>")),
        "https://www.agenziarossi.it/contatti": (200, "text/html", html("<p>Via Roma 1, Milano</p>")),
    }


def person(nome, cognome, ruolo="CEO & Founder", livello="vertice", url=SITE + "team"):
    return {"nome": nome, "cognome": cognome, "ruolo": ruolo, "livello": livello,
            "citazione": f"{nome} {cognome} – {ruolo}", "pagina_url": url}


class FakeDMClassifier(FakeClassifier):
    """Risponde con ``people[dominio]`` (lista di persone) o solleva l'eccezione indicata."""

    def __init__(self, people: dict | None = None, model: str = "claude-haiku-4-5-20251001"):
        super().__init__({}, model=model)
        self.people = people or {}

    def classify(self, system, user, schema=None, validator=None):
        self.calls.append((system, user))
        assert schema is SCHEMA and validator is validate_people
        domain = user.splitlines()[0].replace("Dominio:", "").strip()
        behavior = self.people.get(domain, [])
        if isinstance(behavior, Exception):
            raise behavior
        return ClassifyResult(validator({"persone": behavior}), input_tokens=6000, output_tokens=300, latency_s=0.4)


def res(title: str, url: str) -> SearchResult:
    return SearchResult(title=title, url=url, snippet="", source="fake")


def linkedin_provider(items):
    provider = FakeWebProvider(items)
    provider.search_profiles = lambda query, count=5, domain="linkedin.com": (
        provider.calls.append((query, count, domain)) or
        [res(t, u) for u, t in items])
    return provider


# --- pagine del sito -------------------------------------------------------------------------------
def test_collects_home_footer_and_people_pages_never_linkedin():
    client = FakePagesClient(rossi_pages())
    content = collect_people_pages(SITE, client)
    assert [p.kind for p in content.pages] == ["home", "chi_siamo", "team", "contatti"]
    assert "/blog/articolo" not in " ".join(client.gets)
    assert not any("linkedin" in u for u in client.gets)
    home = content.pages[0]
    assert home.truncated and "Mario Rossi – P.IVA" in home.text          # il footer resta anche se la home è lunga
    assert "mario.rossi@agenziarossi.it" in content.emails and "info@agenziarossi.it" in content.emails
    assert set(PEOPLE_GROUPS) == {"chi_siamo", "team", "contatti"}


def test_http_client_never_opens_linkedin():
    assert never_open("https://it.linkedin.com/in/mario-rossi") and never_open("https://linkedin.com/x")
    assert not never_open("https://www.notlinkedin.com/") and not never_open(SITE)
    with pytest.raises(FetchError, match="linkedin"):
        HttpClient(delay=0, retries=0).get("https://www.linkedin.com/in/mario-rossi")
    with pytest.raises(FetchError, match="linkedin"):
        HttpClient(delay=0, retries=0).get_json("https://api.linkedin.com/v2/me")


# --- scelta del decisore ------------------------------------------------------------------------------
def test_choose_highest_role_and_reject_invented_names():
    text = "Mario Rossi CEO. Giulia Bianchi socia. Luca Verdi."
    chosen, rejected = choose_person([person("Giulia", "Bianchi", "Partner", "socio"),
                                      person("Mario", "Rossi")], text)
    assert chosen["cognome"] == "Rossi" and rejected == []

    # nome inventato dall'AI (non presente nel testo): scartato, si passa al successivo
    chosen, rejected = choose_person([person("Paolo", "Neri"), person("Giulia", "Bianchi", "Partner", "socio")], text)
    assert chosen["nome"] == "Giulia" and rejected == ["Paolo Neri"]

    chosen, rejected = choose_person([person("Paolo", "Neri")], text)
    assert chosen is None and rejected == ["Paolo Neri"]
    assert choose_person([], text) == (None, [])
    # accenti e maiuscole non contano; il solo cognome non basta
    assert choose_person([person("Niccolò", "D'Amico")], "NICCOLO D AMICO fondatore")[0] is not None
    assert choose_person([person("Mario", "Rossi")], "Rossi fondatore")[0] is None


def test_schema_is_strict_and_validator_clips():
    assert SCHEMA["additionalProperties"] is False
    item = SCHEMA["properties"]["persone"]["items"]
    assert item["additionalProperties"] is False and set(item["required"]) == set(item["properties"])
    out = validate_people({"persone": [person("Mario", "Rossi", "x" * 200)]})
    assert len(out["persone"][0]["ruolo"]) == 80
    with pytest.raises(Exception):
        validate_people({"persone": [{**person("Mario", "Rossi"), "livello": "dipendente"}]})


# --- LinkedIn: solo URL e titolo -------------------------------------------------------------------------
def test_linkedin_query_and_agency_name():
    assert agency_name("Home - Agenzia Rossi | Web Marketing Milano", "agenziarossi.it") == "Agenzia Rossi"
    assert agency_name("Home", "agenziarossi.it") == "agenziarossi"
    assert build_query("Mario", "Rossi", "Agenzia Rossi") == '"Mario Rossi" "Agenzia Rossi" site:linkedin.com/in'
    assert profile_url("https://it.linkedin.com/in/mario-rossi-123/?trk=x") == "https://it.linkedin.com/in/mario-rossi-123"
    assert profile_url("https://www.linkedin.com/company/agenzia-rossi") is None
    assert profile_url("https://www.example.com/in/mario-rossi") is None


@pytest.mark.parametrize("title,expected", [
    ("Mario Rossi - Agenzia Rossi | LinkedIn", "alta"),            # nome dell'agenzia
    ("Mario Rossi - CEO | LinkedIn", "alta"),                      # ruolo
    ("Mario Rossi | LinkedIn", "media"),
])
def test_linkedin_confidence(title, expected):
    results = [res(title, "https://it.linkedin.com/in/mario-rossi")]
    assert pick_profile(results, "Rossi", "Agenzia Rossi", "CEO & Founder", "agenziarossi.it")[2] == expected


def test_linkedin_first_result_with_surname_on_a_profile():
    results = [res("Agenzia Rossi | LinkedIn", "https://www.linkedin.com/company/agenzia-rossi"),
               res("Marco Bianchi - Agenzia Rossi", "https://www.linkedin.com/in/marco-bianchi"),
               res("Mario Rossi - Founder", "https://www.linkedin.com/in/mario-rossi"),
               res("Mario Rossi - altro", "https://www.linkedin.com/in/mario-rossi-2")]
    url, title, conf = pick_profile(results, "Rossi", "Agenzia Rossi", "CEO", "agenziarossi.it")
    assert url == "https://www.linkedin.com/in/mario-rossi" and conf == "alta"
    assert pick_profile(results[:2], "Rossi", "Agenzia Rossi", "CEO", "agenziarossi.it") is None


def test_tavily_profile_search_restricts_to_linkedin_and_reads_only_url_and_title():
    client = FakePagesClient()
    client.post_responses.append({"results": [{"url": "https://www.linkedin.com/in/mario-rossi",
                                               "title": "Mario Rossi - CEO", "content": "testo del profilo"}]})
    out = TavilyProvider(client, api_key="tvly-x").search_profiles('"Mario Rossi" site:linkedin.com/in')
    payload = client.posts[0]["payload"]
    assert payload["include_domains"] == ["linkedin.com"] and "exclude_domains" not in payload
    assert payload["include_raw_content"] is False
    assert out[0].url.endswith("/in/mario-rossi") and out[0].snippet == "" and not client.gets


# --- email -------------------------------------------------------------------------------------------------
def test_nominative_email_from_site_then_guess():
    emails = ["info@agenziarossi.it", "giulia@agenziarossi.it", "m.rossi@gmail.com"]
    assert nominative_email(emails, "Mario", "Rossi", "agenziarossi.it") == "m.rossi@gmail.com"
    assert nominative_email(["mario@agenziarossi.it", "info@agenziarossi.it"], "Mario", "Rossi",
                            "agenziarossi.it") == "mario@agenziarossi.it"
    assert nominative_email(["mario@altrosito.it"], "Mario", "Rossi", "agenziarossi.it") is None   # solo nome: serve il dominio
    assert nominative_email(["info@agenziarossi.it"], "Mario", "Rossi", "agenziarossi.it") is None
    assert nominative_email(["gianmarco.damico@x.it"], "Gian Marco", "D'Amico", "agenziarossi.it") == "gianmarco.damico@x.it"
    assert guess_email("Mario", "www.agenziarossi.it") == "mario@agenziarossi.it"
    assert guess_email("Gian Marco", "agenziarossi.it") == "gianmarco@agenziarossi.it"


# --- una agenzia, dall'inizio alla fine -------------------------------------------------------------------
def rossi_prospect(**over) -> Prospect:
    data = dict(company_name="Home - Agenzia Rossi | Web Marketing Milano", website=SITE, id=1,
                email="info@agenziarossi.it", emails="info@agenziarossi.it", status="enriched")
    data.update(over)
    return Prospect(**data)


def test_finder_found_with_linkedin_and_site_email():
    client = FakePagesClient(rossi_pages())
    clf = FakeDMClassifier({"agenziarossi.it": [person("Giulia", "Bianchi", "Partner", "socio"),
                                                person("Mario", "Rossi")]})
    provider = linkedin_provider([("https://it.linkedin.com/in/mario-rossi", "Mario Rossi - CEO - Agenzia Rossi | LinkedIn")])
    dm = finder.find_decision_maker(rossi_prospect(), client, clf, provider, {"claude-haiku-4-5": [1.0, 5.0]})
    assert dm.status == "trovato" and (dm.nome, dm.cognome, dm.ruolo) == ("Mario", "Rossi", "CEO & Founder")
    assert dm.linkedin_url == "https://it.linkedin.com/in/mario-rossi" and dm.linkedin_confidence == "alta"
    assert provider.calls == [('"Mario Rossi" "Agenzia Rossi" site:linkedin.com/in', 5, "linkedin.com")]
    assert dm.email == "mario.rossi@agenziarossi.it" and dm.email_source == "sito" and dm.email_verified
    assert dm.web_calls == 1 and dm.cost_usd == pytest.approx(0.0075) and len(dm.pages_used) == 4
    assert not any("linkedin" in u for u in client.gets)
    assert "Agenzia: Agenzia Rossi" in clf.calls[0][1] and "### [team]" in clf.calls[0][1]


def test_finder_guess_email_and_linkedin_not_found():
    pages = rossi_pages()
    pages["https://www.agenziarossi.it/team"] = (200, "text/html", html("<p>Mario Rossi – CEO</p>"))
    clf = FakeDMClassifier({"agenziarossi.it": [person("Mario", "Rossi", "CEO")]})
    provider = linkedin_provider([("https://www.linkedin.com/in/altro", "Paolo Neri - CEO")])
    dm = finder.find_decision_maker(rossi_prospect(), FakePagesClient(pages), clf, provider)
    assert dm.status == "trovato" and dm.linkedin_url == "" and dm.linkedin_confidence == "non trovato"
    assert dm.email == "mario@agenziarossi.it" and dm.email_source == "ipotesi" and not dm.email_verified


def test_finder_not_found_and_invented_and_failures():
    clf = FakeDMClassifier({"agenziarossi.it": []})
    provider = linkedin_provider([])
    dm = finder.find_decision_maker(rossi_prospect(), FakePagesClient(rossi_pages()), clf, provider)
    assert dm.status == "non_trovato" and dm.full_name == "" and dm.email == "" and not provider.calls

    clf = FakeDMClassifier({"agenziarossi.it": [person("Paolo", "Neri")]})          # non è nel testo
    dm = finder.find_decision_maker(rossi_prospect(), FakePagesClient(rossi_pages()), clf, provider)
    assert dm.status == "non_trovato" and "non presenti nel testo" in dm.error and not provider.calls

    clf = FakeDMClassifier({"agenziarossi.it": ClassifyError("chiave Anthropic non valida", 10, 0)})
    dm = finder.find_decision_maker(rossi_prospect(), FakePagesClient(rossi_pages()), clf, provider)
    assert dm.status == "fallito" and dm.error == "AI: chiave Anthropic non valida"

    n_calls = len(clf.calls)
    dm = finder.find_decision_maker(rossi_prospect(), FakePagesClient({SITE: (500, "text/html", "")}), clf, provider)
    assert dm.status == "fallito" and dm.error.startswith("sito:") and len(clf.calls) == n_calls   # niente AI

    # Web Search non configurata: decisore ed email sì, LinkedIn non cercato
    clf = FakeDMClassifier({"agenziarossi.it": [person("Mario", "Rossi")]})
    dm = finder.find_decision_maker(rossi_prospect(), FakePagesClient(rossi_pages()), clf, None)
    assert dm.status == "trovato" and dm.linkedin_confidence.startswith("non cercato") and dm.email_verified


# --- pipeline sui record già nel database -------------------------------------------------------------------
@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    db = Database(tmp_path / "t.db")
    run = db.start_run(mode=MODE_BOTH, category=AGENCY_CATEGORY, keyword="agenzie", location="Italia")
    ids = {}
    for name, is_agency, score in [("rossi", "si", 80), ("bianchi", "si", 40), ("verdi", "no", None),
                                   ("neri", "dubbio", 55)]:
        p = Prospect(company_name=f"Agenzia {name.title()}", website=f"https://www.agenzia{name}.it/",
                     status="enriched", category=AGENCY_CATEGORY)
        ids[name] = db.save(p)
        db.link_run(run, p.id)
        db.save_qualification(p.id, run, Qualification(status="ok" if is_agency != "no" else "excluded",
                                                        is_agency=is_agency, score=score))
    db.finish_run(run, n_found=4, n_unique=4, n_enriched=4, n_failed=0)
    return db, ids, run


def test_find_contacts_only_agencies_and_skips_done(db_env, monkeypatch):
    db, ids, _ = db_env
    calls = []

    def fake_find(prospect, client, classifier, provider, prices=None):
        calls.append(prospect.id)
        return DecisionMaker(status="trovato", nome="Mario", cognome=prospect.company_name.split()[-1],
                             ruolo="CEO", email="mario@x.it", email_source="ipotesi", cost_usd=0.01,
                             linkedin_url="https://www.linkedin.com/in/m", linkedin_confidence="media", web_calls=1)

    monkeypatch.setattr(pipeline_mod.dm_finder, "find_decision_maker", fake_find)
    monkeypatch.setattr(llm, "get_classifier", lambda provider=None, client=None, model=None: FakeDMClassifier())
    monkeypatch.setattr(web_search, "get_provider", lambda name=None, client=None: linkedin_provider([]))
    messages = []
    pipe = Pipeline(db, HttpClient(delay=0, retries=0), on_message=lambda t, lvl="info": messages.append((lvl, t)))

    res = pipe.find_contacts(list(ids.values()))
    assert sorted(calls) == sorted([ids["rossi"], ids["bianchi"]])          # solo is_agency = si
    assert res.n_found == 2 and res.n_skipped_not_agency == 2 and res.web_calls == 2 and res.n_email_guess == 2
    assert res.llm_cost_usd == pytest.approx(0.02)
    assert any(lvl == "success" and "2 decisori trovati" in t and "2 profili LinkedIn" in t for lvl, t in messages)
    assert db.get_decision_makers([ids["rossi"]])[ids["rossi"]].cognome == "Rossi"

    calls.clear()
    res = pipe.find_contacts([ids["rossi"]])                                 # già cercata: saltata
    assert calls == [] and res.n_skipped_done == 1
    res = pipe.find_contacts([ids["rossi"]], force=True)                     # «Ricalcola»
    assert calls == [ids["rossi"]] and res.n_found == 1


def test_find_contacts_without_ai_key_does_nothing(db_env, monkeypatch):
    db, ids, _ = db_env
    monkeypatch.setattr(llm, "get_classifier",
                        lambda provider=None, client=None, model=None: FakeClassifier(configured=False))
    messages = []
    res = Pipeline(db, on_message=lambda t, lvl="info": messages.append((lvl, t))).find_contacts([ids["rossi"]])
    assert res.n_targets == 0 and any("AI non configurata" in t for _, t in messages)
    assert db.get_decision_makers([ids["rossi"]]) == {}


# --- stato outreach ----------------------------------------------------------------------------------------
def test_outreach_saved_and_changes_detected(db_env):
    db, ids, _ = db_env
    db.set_outreach(ids["rossi"], "contattato")
    db.set_outreach(ids["rossi"], "call")
    assert db.get_outreach(list(ids.values())) == {ids["rossi"]: "call"}
    with pytest.raises(ValueError):
        db.set_outreach(ids["rossi"], "boh")

    plist = db.list_prospects(ids=list(ids.values()))
    df = prospects_to_dataframe(plist, db.get_qualifications(list(ids.values())), {}, db.get_outreach(list(ids.values())))
    assert dict(zip(df["ID"], df["Stato outreach"]))[ids["rossi"]] == "call"
    after = df.copy()
    after.loc[after["ID"] == ids["neri"], "Stato outreach"] = "risposto"
    assert outreach_changes(df, after) == {ids["neri"]: "risposto"}
    assert outreach_changes(df, df.copy()) == {}


def test_export_contains_decision_maker_columns(db_env):
    db, ids, _ = db_env
    db.save_decision_maker(ids["rossi"], DecisionMaker(
        status="trovato", nome="Mario", cognome="Rossi", ruolo="CEO", linkedin_url="https://it.linkedin.com/in/m",
        linkedin_confidence="alta", email="mario.rossi@agenziarossi.it", email_source="sito", email_verified=True))
    db.save_decision_maker(ids["bianchi"], DecisionMaker(status="non_trovato"))
    db.save_decision_maker(ids["neri"], DecisionMaker(status="fallito", error="sito: timeout"))
    all_ids = list(ids.values())
    df = prospects_to_dataframe(db.list_prospects(ids=all_ids), db.get_qualifications(all_ids),
                                db.get_decision_makers(all_ids), db.get_outreach(all_ids))
    rows = {r["ID"]: r for r in csv.DictReader(io.StringIO(to_csv_bytes(df).decode("utf-8-sig")))}
    r = rows[str(ids["rossi"])]
    assert (r["Decisore"], r["Ruolo"], r["Confidenza LinkedIn"], r["Fonte email"]) == (
        "Mario Rossi", "CEO", "alta", "sito (verificata)")
    assert r["Email decisore"] == "mario.rossi@agenziarossi.it" and r["Stato outreach"] == "da contattare"
    assert rows[str(ids["bianchi"])]["Decisore"] == "non trovato"
    assert rows[str(ids["neri"])]["Decisore"] == "errore: sito: timeout"
    assert rows[str(ids["verdi"])]["Decisore"] == ""


# --- interfaccia -------------------------------------------------------------------------------------------
def test_streamlit_contacts_columns_filter_and_button(app_env, monkeypatch):  # noqa: F811
    from streamlit.testing.v1 import AppTest

    db = Database()
    run = db.start_run(mode=MODE_BOTH, category=AGENCY_CATEGORY, keyword="agenzie", location="Italia")
    ids = []
    for i, score in enumerate([80, 60, 30]):
        p = Prospect(company_name=f"Agenzia {i}", website=f"https://agenzia{i}.it", status="enriched",
                     category=AGENCY_CATEGORY)
        db.link_run(run, db.save(p))
        db.save_qualification(p.id, run, Qualification(status="ok", is_agency="si", score=score))
        ids.append(p.id)
    db.finish_run(run, n_found=3, n_unique=3, n_enriched=3, n_failed=0)
    db.save_decision_maker(ids[0], DecisionMaker(status="trovato", nome="Mario", cognome="Rossi", ruolo="CEO",
                                                 email="mario@agenzia0.it", email_source="ipotesi"))
    db.set_outreach(ids[0], "contattato")

    seen = []

    def fake_find(prospect, client, classifier, provider, prices=None):
        seen.append(prospect.id)
        return DecisionMaker(status="non_trovato")

    monkeypatch.setattr(pipeline_mod.dm_finder, "find_decision_maker", fake_find)
    monkeypatch.setattr(llm, "get_classifier", lambda provider=None, client=None, model=None: FakeDMClassifier())

    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert not at.exception
    df = at.dataframe[0].value
    row = df[df["ID"] == ids[0]].iloc[0]
    assert (row["Decisore"], row["Fonte email"], row["Stato outreach"]) == (
        "Mario Rossi", "ipotesi – da verificare", "contattato")
    assert set(df["Stato outreach"]) == {"contattato", "da contattare"}

    at.multiselect(key="outreach_filter").set_value(["contattato"]).run()
    assert list(at.dataframe[0].value["ID"]) == [ids[0]]
    at.multiselect(key="outreach_filter").set_value([]).run()

    button = next(b for b in at.button if b.key == "dm_score")
    assert button.label == "Trova contatti (score ≥ 50: 1 da cercare)"
    button.click().run()
    assert not at.exception
    assert sorted(seen) == [ids[1]]          # la prima è già stata cercata, la terza ha score < 50
    assert any("1 non trovato" in s.value for s in at.success)
