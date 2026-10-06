"""Agenzie: blacklist, scoperta con filtro extra, file dei pesi, impostazioni utente."""

from __future__ import annotations

import pytest

from config import settings, user_settings
from qualify import config as qc
from scrapers.search.base import SearchResult
from scrapers.web_search.discovery import discover
from tests.agency_helpers import FakeWebProvider


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    for var in ("PS_LLM_PROVIDER", "PS_ANTHROPIC_API_KEY", "PS_OPENAI_API_KEY", "PS_GEMINI_API_KEY",
                "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "PS_CLAUDE_MODEL"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


# ------------------------------------------------------------------ blacklist ---
def test_default_blacklist_is_copied_and_parsed(home):
    assert not (home / "agency_blacklist.txt").exists()
    bl = qc.load_blacklist()
    assert (home / "agency_blacklist.txt").exists()
    assert {"clutch.co", "sortlist.it", "linkedin.com", "addlance.com"} <= bl.domains
    assert len(bl.domains) == 44
    assert "migliori agenzie" in bl.phrases and "come scegliere" in bl.phrases and len(bl.phrases) == 12


def test_blacklist_matches_domains_and_subdomains(home):
    bl = qc.load_blacklist()
    assert bl.match("https://clutch.co/agencies/seo", "x") == "dominio in blacklist: clutch.co"
    assert bl.match("https://it.clutch.co/x", "") == "dominio in blacklist: clutch.co"
    assert bl.match("https://www.sortlist.it/", "") == "dominio in blacklist: sortlist.it"
    assert bl.match("https://studiorosso.it/", "Studio Rosso") is None
    assert bl.match("https://notclutch.co/", "") is None           # non è un sottodominio


def test_blacklist_matches_phrases_in_title_and_url_path(home):
    bl = qc.load_blacklist()
    assert bl.match("https://a.it/", "Le MIGLIORI Agenzie SEO") == "frase in blacklist: migliori agenzie"
    assert bl.match("https://a.it/blog/top-10-agenzie-seo", "Blog") == "frase in blacklist: top 10"
    assert bl.match("https://a.it/come_scegliere-agenzia", "") == "frase in blacklist: come scegliere"
    assert bl.match("https://a.it/chi-siamo", "Chi siamo") is None
    assert bl.match("https://classifica.it/", "Home") is None      # la frase non conta nel dominio


def test_blacklist_edit_roundtrip_and_format(home):
    qc.save_blacklist_text("# commento\n[domini]\nWWW.Esempio.IT\nhttps://altro.com/x\n\n[frasi]\n  Offerta  Speciale \n")
    bl = qc.load_blacklist()
    assert bl.domains == {"esempio.it", "altro.com"} and bl.phrases == ["offerta speciale"]
    assert "commento" in qc.blacklist_text()
    assert bl.match("https://blog.esempio.it/", "") == "dominio in blacklist: esempio.it"
    assert bl.match("https://x.it/", "Offerta speciale!") == "frase in blacklist: offerta speciale"


# --------------------------------------------------------------------- discover ---
def _items(n: int, prefix: str = "https://site{}.it/") -> list[tuple[str, str]]:
    return [(prefix.format(i), f"Sito {i}") for i in range(n)]


def test_discover_without_extra_filter_is_unchanged():
    prov = FakeWebProvider(_items(5) + [("https://x.it/top-10", "Top 10 agenzie")])
    report = discover(prov, "agenzia", "Italia", 10)
    assert len(report.results) == 6 and report.filtered == 0


def test_discover_extra_filter_skips_before_counting_toward_max():
    bl = qc.Blacklist(domains={"bad.it"}, phrases=["classifica"])
    items = [("https://bad.it/", "Bad"), ("https://a.it/classifica-agenzie", "A"),
             ("https://b.it/", "B"), ("https://sub.bad.it/x", "Sub"), ("https://c.it/", "C"),
             ("https://d.it/", "D")]
    prov = FakeWebProvider(items)
    report = discover(prov, "agenzia", "Italia", 3, extra_filter=lambda r: bl.match(r.url, r.title))
    assert [r.url for r in report.results] == ["https://b.it/", "https://c.it/", "https://d.it/"]
    assert report.filtered == 3


def test_discover_keeps_paging_when_a_page_is_entirely_filtered():
    class Paged(FakeWebProvider):
        max_pages = 3

        def search_page(self, query, count, page, country_code):
            urls = {0: [f"https://bad{i}.it/" for i in range(4)],
                    1: [f"https://ok{i}.it/" for i in range(4)]}.get(page, [])
            return [SearchResult(u, u, "", "fake", {}) for u in urls]

    report = discover(Paged([], per_call=4), "agenzia", "Italia", 3,
                      extra_filter=lambda r: "bad" if "bad" in r.url else None)
    assert [r.url for r in report.results] == [f"https://ok{i}.it/" for i in range(3)]
    assert report.filtered == 4


# --------------------------------------------------------------------- pesi ---
def test_default_scoring_loaded_and_copied(home):
    scoring = qc.load_scoring()
    assert (home / "agency_scoring.toml").exists()
    assert scoring["seo_level"] == {"assente": 40, "accennata": 25, "strutturata": 0}
    assert scoring["size_signal"]["6-20"] == 25 and scoring["is_agency"]["dubbio"] == -20
    assert scoring["limiti"] == {"min": 0, "max": 100}
    assert scoring["llm"]["claude"] == "claude-haiku-4-5" and scoring["llm"]["claude_alt"] == "claude-sonnet-5-5"
    assert scoring["prezzi"]["claude-sonnet-5-5"] == [2.0, 10.0]
    assert qc.load_scoring_with_error()[1] == ""


def test_save_scoring_validates_before_writing(home):
    original = qc.scoring_text()
    for bad in ("[seo_level\nassente = 1", "[seo_level]\nassente = \"tanto\"",
                "[prezzi]\n\"x\" = [1]", "[limiti]\nmin = 50\nmax = 10", "[llm]\nclaude = 3"):
        with pytest.raises(ValueError):
            qc.save_scoring_text(bad)
        assert qc.scoring_text() == original                      # il file non è stato toccato
    qc.save_scoring_text("[seo_level]\nassente = 10\n")           # sezioni mancanti: predefiniti
    scoring = qc.load_scoring()
    assert scoring["seo_level"]["assente"] == 10 and scoring["seo_level"]["accennata"] == 25
    assert scoring["servizi_ricorrenti"]["si"] == 25


def test_broken_user_scoring_file_falls_back_and_reports(home):
    qc.load_scoring()
    (home / "agency_scoring.toml").write_text("[seo_level\nrotto", encoding="utf-8")
    scoring, error = qc.load_scoring_with_error()
    assert scoring["seo_level"]["assente"] == 40 and "non valido" in error


# -------------------------------------------------------------- user_settings ---
def test_llm_settings_keys_and_env_fallbacks(home, monkeypatch):
    assert user_settings.get("llm_provider") == "claude" and user_settings.get("claude_model") == "claude-haiku-4-5"
    assert user_settings.get("anthropic_api_key") == ""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "plain")
    assert user_settings.get("anthropic_api_key") == "plain"
    user_settings.save({"anthropic_api_key": "saved", "llm_provider": "openai", "claude_model": "claude-sonnet-5-5"})
    assert user_settings.get("anthropic_api_key") == "saved"       # il file batte la variabile standard
    monkeypatch.setenv("PS_ANTHROPIC_API_KEY", "ps-env")
    assert user_settings.get("anthropic_api_key") == "ps-env"      # PS_* batte tutto
    monkeypatch.setenv("OPENAI_API_KEY", "oa")
    monkeypatch.setenv("GEMINI_API_KEY", "gm")
    assert user_settings.get("openai_api_key") == "oa" and user_settings.get("gemini_api_key") == "gm"
    monkeypatch.setenv("PS_LLM_PROVIDER", "gemini")
    assert user_settings.get("llm_provider") == "gemini"
