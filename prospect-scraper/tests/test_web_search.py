"""Web Search: normalizzazione domini, provider (HTTP simulato), discovery, impostazioni utente,
pipeline end-to-end con siti locali e smoke test dell'interfaccia Streamlit."""

from __future__ import annotations

import csv
import io
import json
import os
import stat
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from config import settings, user_settings
from core import pipeline as pipeline_mod
from core.pipeline import (MODE_BOTH, MODE_SEARCH, SOURCE_LOCAL, SOURCE_WEB, WEB_CATEGORY, Pipeline,
                           RunParams, web_result_to_prospect)
from database.db import Database
from exporters.export import prospects_to_dataframe, to_csv_bytes
from scrapers import web_search
from scrapers.http import FetchError, HttpClient
from scrapers.search.base import SearchResult
from scrapers.web_search.base import WebSearchProvider
from scrapers.web_search.brave import BraveProvider
from scrapers.web_search.discovery import discover
from scrapers.web_search.searxng import SearXNGWebProvider
from scrapers.web_search.tavily import TavilyProvider
from scrapers.website import WebsiteCrawler
from tests.site_server import SiteServer
from utils.normalization import registrable_domain


# ----------------------------------------------------------------- strumenti ---
class RecordingClient(HttpClient):
    """Client finto: registra le chiamate e risponde con JSON predefinito (o solleva)."""

    def __init__(self, response=None, error: Exception | None = None):
        super().__init__(delay=0, retries=0)
        self.calls: list[dict] = []
        self.response = response if response is not None else {}
        self.error = error

    def get_json(self, url, *, params=None, data=None, min_interval=None, timeout=None, headers=None):
        self.calls.append({"method": "GET", "url": url, "params": params, "headers": headers})
        if self.error:
            raise self.error
        return self.response

    def post_json(self, url, payload, *, headers=None, min_interval=None, timeout=None):
        self.calls.append({"method": "POST", "url": url, "payload": payload, "headers": headers})
        if self.error:
            raise self.error
        return self.response


class FakeProvider(WebSearchProvider):
    """Provider con pagine predefinite: ``pages[(query, page)] -> [(url, title), ...]``."""

    name = "fake"
    label = "Fake"

    def __init__(self, pages=None, per_call=10, max_pages=1, fail_on: dict[int, Exception] | None = None,
                 configured=True, client=None, **config):
        super().__init__(client or HttpClient(delay=0, retries=0), **config)
        self.pages = pages or {}
        self.per_call, self.max_pages = per_call, max_pages
        self.fail_on = fail_on or {}
        self.configured = configured
        self.calls: list[tuple] = []

    def is_configured(self):
        return self.configured

    def search_page(self, query, count, page, country_code):
        self.calls.append((query, count, page, country_code))
        if len(self.calls) in self.fail_on:
            raise self.fail_on[len(self.calls)]
        items = self.pages.get((query, page), [])
        return [SearchResult(title=t, url=u, snippet=f"snippet {t}", source=self.name,
                             extra={"source_url": u, "rank": i}) for i, (u, t) in enumerate(items, 1)]


def urls(report):
    return [r.url for r in report.results]


# ------------------------------------------------------------ registrable_domain ---
@pytest.mark.parametrize("value, expected", [
    ("https://www.example.com/", "example.com"),
    ("example.com", "example.com"),
    ("http://blog.example.com/x", "example.com"),
    ("shop.example.co.uk", "example.co.uk"),
    ("https://www.example.com.au/x", "example.com.au"),
    ("acme.substack.com", "acme.substack.com"),
    ("https://www.acme.substack.com/post", "acme.substack.com"),
    ("app.acme.vercel.app", "acme.vercel.app"),
    ("127.0.0.2", "127.0.0.2"),
    ("http://127.0.0.2:8080/x", "127.0.0.2"),
    ("localhost", "localhost"),
    ("", None),
    ("mailto:a@b.it", None),
])
def test_registrable_domain(value, expected):
    assert registrable_domain(value) == expected


# ---------------------------------------------------------------- discovery ---
def test_discover_collapses_domain_variants():
    variants = [("https://www.example.com/", "Example"), ("https://example.com", "Example home"),
                ("http://blog.example.com/post", "Blog"), ("https://example.com/prezzi/", "Prezzi"),
                ("https://www.altra.it/", "Altra")]
    prov = FakeProvider({("saas Italia", 0): variants})
    report = discover(prov, "saas", "Italia", 10)
    assert [r.extra["query"] for r in report.results] == ["saas Italia"] * 2
    assert urls(report) == ["https://www.example.com/", "https://www.altra.it/"]
    assert report.results[0].extra["other_urls"] == [
        "https://example.com", "http://blog.example.com/post", "https://example.com/prezzi/"]
    assert report.raw_count == 5 and report.api_calls >= 1 and report.provider == "fake"


def test_discover_filters_excluded_domains():
    items = [("https://it.linkedin.com/company/x", "LinkedIn"), ("https://www.g2.com/products/x", "G2"),
             ("https://blog.medium.com/x", "Medium"), ("https://it.indeed.com/q-x", "Indeed"),
             ("https://www.booking.com/hotel", "Booking"), ("https://en.wikipedia.org/wiki/X", "Wiki"),
             ("https://startupitalia.eu/", "StartupItalia"), ("https://www.acme.io/", "Acme")]
    report = discover(FakeProvider({("saas Italia", 0): items}), "saas", "Italia", 10)
    assert urls(report) == ["https://startupitalia.eu/", "https://www.acme.io/"]
    assert report.raw_count == 8


def test_discover_respects_max_results_and_max_calls():
    page = lambda n, k: [(f"https://site{n}-{i}.it/", f"S{n}{i}") for i in range(k)]  # noqa: E731
    q = "saas Italia"
    pages = {(q, 0): page(0, 4), (q, 1): page(1, 4), (q, 2): page(2, 4)}
    prov = FakeProvider(pages, per_call=4, max_pages=3)
    report = discover(prov, "saas", "Italia", 6)
    assert len(report.results) == 6 and report.api_calls == 2     # si ferma appena ne ha abbastanza
    prov = FakeProvider(pages, per_call=4, max_pages=3)
    report = discover(prov, "saas", "Italia", 100, max_calls=2)
    assert len(report.results) == 8 and report.api_calls == 2 and len(prov.calls) == 2


def test_discover_uses_query_variants_when_short():
    base = "saas Italia"
    pages = {(base, 0): [("https://a.it/", "A"), ("https://b.it/", "B")],
             (base + " azienda", 0): [("https://b.it/x", "B2"), ("https://c.it/", "C")],
             (base + " sito ufficiale", 0): [("https://d.it/", "D")],
             (base + " company", 0): [("https://e.it/", "E")]}
    prov = FakeProvider(pages)                                    # nessuna paginazione
    report = discover(prov, "saas", "Italia", 4)
    assert [c[0] for c in prov.calls] == [base, base + " azienda", base + " sito ufficiale"]
    assert report.queries == [base, base + " azienda", base + " sito ufficiale"]
    assert sorted(r.url for r in report.results) == sorted(
        ["https://a.it/", "https://b.it/", "https://c.it/", "https://d.it/"])
    assert report.results[1].extra["other_urls"] == ["https://b.it/x"]
    assert {r.extra["query"] for r in report.results} == set(report.queries)


def test_discover_stops_when_a_call_adds_nothing_new():
    base = "saas Italia"
    prov = FakeProvider({(base, 0): [("https://a.it/", "A")], (base + " azienda", 0): [("https://a.it/", "A")],
                         (base + " sito ufficiale", 0): [("https://z.it/", "Z")]})
    report = discover(prov, "saas", "Italia", 10)
    assert report.api_calls == 2 and urls(report) == ["https://a.it/"]


def test_discover_query_and_country():
    prov = FakeProvider()
    discover(prov, "startup fintech", "Milano", 5, max_calls=1)
    assert prov.calls[0] == ("startup fintech Milano", 10, 0, "it")
    prov = FakeProvider()
    discover(prov, "startup Milano", "", 5, max_calls=1)          # località vuota = default (Italia)
    assert prov.calls[0][0] == "startup Milano Italia"
    prov = FakeProvider()
    discover(prov, "SaaS Italia", "Italia", 5, max_calls=1)       # già nella keyword: non si ripete
    assert prov.calls[0][0] == "SaaS Italia"
    prov = FakeProvider()
    discover(prov, "software", "Francia", 5, max_calls=1)
    assert prov.calls[0][0] == "software Francia" and prov.calls[0][3] == "fr"


@pytest.mark.parametrize("code, marker", [(401, "401"), (403, "403"), (429, "429")])
def test_discover_stops_on_auth_or_limit_errors(code, marker):
    base = "saas Italia"
    pages = {(base, 0): [("https://a.it/", "A")], (base, 1): [("https://b.it/", "B")]}
    err = FetchError(f"chiave API non valida (HTTP {code}) da api.x.com")
    prov = FakeProvider(pages, per_call=1, max_pages=3, fail_on={2: err})
    report = discover(prov, "saas", "Italia", 10)                 # non solleva
    assert len(prov.calls) == 2 and report.api_calls == 2
    assert urls(report) == ["https://a.it/"]                      # tiene quanto già raccolto
    assert len(report.errors) == 1 and marker in report.errors[0]


def test_discover_records_other_errors_and_tries_variants():
    base = "saas Italia"
    pages = {(base + " azienda", 0): [("https://a.it/", "A")]}
    prov = FakeProvider(pages, fail_on={1: RuntimeError("boom")})
    report = discover(prov, "saas", "Italia", 5)
    assert report.errors == ["errore: RuntimeError"] and urls(report) == ["https://a.it/"]


def test_run_web_search_not_configured_makes_no_calls(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    for var in ("PS_TAVILY_API_KEY", "PS_BRAVE_API_KEY", "PS_SEARXNG_URL", "PS_WEB_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(settings, "SEARXNG_URL", "")
    client = RecordingClient({"results": []})
    report = web_search.run_web_search("saas", "Italia", 10, client=client)
    assert client.calls == [] and report.api_calls == 0 and report.results == []
    assert report.errors and "non configurata" in report.errors[0]
    assert web_search.web_search_status() == (False, "Tavily")
    assert web_search.web_search_status("brave") == (False, "Brave Search")
    prov = FakeProvider(configured=False)
    assert web_search.run_web_search("saas", "Italia", 10, provider=prov).api_calls == 0 and not prov.calls


def test_get_provider_uses_user_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    for var in ("PS_TAVILY_API_KEY", "PS_BRAVE_API_KEY", "PS_SEARXNG_URL", "PS_WEB_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    user_settings.save({"tavily_api_key": "tvly-abc", "brave_api_key": "BSA", "searxng_url": "http://s:8888/"})
    assert isinstance(web_search.get_provider(), TavilyProvider) and web_search.web_search_status() == (True, "Tavily")
    assert web_search.get_provider("brave").api_key == "BSA"
    assert web_search.get_provider("searxng").url == "http://s:8888"
    assert isinstance(web_search.get_provider("sconosciuto"), TavilyProvider)   # ripiega sul default
    assert set(web_search.WEB_PROVIDERS) == {"tavily", "brave", "searxng"}


# ---------------------------------------------------------------- providers ---
def test_tavily_request_and_parsing(monkeypatch):
    client = RecordingClient({"results": [
        {"title": "Acme - SaaS", "url": "https://www.acme.io/", "content": "Software B2B", "score": 0.9},
        {"title": "", "url": "", "content": "senza url"},
        {"title": "Beta", "url": "https://beta.it/", "content": "Altro", "score": 0.5}]})
    prov = TavilyProvider(client, api_key="tvly-secret")
    assert prov.is_configured() and not TavilyProvider(client, api_key="").is_configured()
    assert (prov.per_call, prov.max_pages) == (20, 1)
    res = prov.search_page("saas Italia", 50, 0, "it")
    call = client.calls[0]
    assert call["method"] == "POST" and call["url"] == settings.TAVILY_API_URL
    assert call["headers"] == {"Authorization": "Bearer tvly-secret"}
    body = call["payload"]
    assert body["query"] == "saas Italia" and body["max_results"] == 20 and body["country"] == "italy"
    assert body["search_depth"] == "basic" and body["include_answer"] is False
    assert body["include_raw_content"] is False and body["include_images"] is False
    assert 0 < len(body["exclude_domains"]) <= 50 and set(body["exclude_domains"]) <= settings.WEB_EXCLUDED_DOMAINS
    assert "tvly-secret" not in json.dumps(body)
    assert [(r.title, r.url, r.snippet, r.source) for r in res] == [
        ("Acme - SaaS", "https://www.acme.io/", "Software B2B", "tavily"),
        ("Beta", "https://beta.it/", "Altro", "tavily")]
    assert res[0].extra == {"source_url": "https://www.acme.io/", "rank": 1}
    prov.search_page("q", 5, 0, "")                                # paese ignoto: nessun "country"
    assert client.calls[1]["payload"]["max_results"] == 5 and "country" not in client.calls[1]["payload"]


def test_brave_request_and_parsing():
    client = RecordingClient({"web": {"results": [
        {"title": "Acme", "url": "https://acme.io/", "description": "Desc"},
        {"title": "Beta", "url": "https://beta.it/x", "description": "D2"}]}})
    prov = BraveProvider(client, api_key="BSA-secret")
    assert prov.is_configured() and (prov.per_call, prov.max_pages) == (20, 5)
    res = prov.search_page("saas Italia", 30, 2, "it")
    call = client.calls[0]
    assert call["method"] == "GET" and call["url"] == settings.BRAVE_API_URL
    assert call["headers"] == {"X-Subscription-Token": "BSA-secret", "Accept": "application/json"}
    assert call["params"] == {"q": "saas Italia", "count": 20, "offset": 2, "country": "IT", "search_lang": "it"}
    assert [(r.title, r.url, r.snippet, r.source) for r in res] == [
        ("Acme", "https://acme.io/", "Desc", "brave"), ("Beta", "https://beta.it/x", "D2", "brave")]
    assert res[0].extra["rank"] == 2 * 20 + 1
    prov.search_page("x", 5, 0, "fr")
    assert client.calls[1]["params"]["country"] == "FR" and "search_lang" not in client.calls[1]["params"]
    prov.search_page("x", 5, 99, "")
    assert client.calls[2]["params"]["offset"] == 9 and "country" not in client.calls[2]["params"]


def test_searxng_request_and_parsing():
    client = RecordingClient({"results": [{"url": "https://acme.io/", "title": "Acme", "content": "C"},
                                          {"url": "", "title": "x"}]})
    prov = SearXNGWebProvider(client, url="http://localhost:8888/")
    assert prov.is_configured() and not SearXNGWebProvider(client, url="").is_configured()
    assert (prov.per_call, prov.max_pages) == (10, 5)
    res = prov.search_page("saas Italia", 10, 1, "it")
    call = client.calls[0]
    assert call["url"] == "http://localhost:8888/search"
    assert call["params"] == {"q": "saas Italia", "format": "json", "pageno": 2, "language": "it-IT"}
    assert [(r.title, r.url, r.snippet, r.source) for r in res] == [("Acme", "https://acme.io/", "C", "searxng")]


def test_provider_errors_propagate_and_discover_reports_them():
    client = RecordingClient(error=FetchError("chiave API non valida (HTTP 401) da api.tavily.com"))
    report = discover(TavilyProvider(client, api_key="x"), "saas", "Italia", 10)
    assert len(client.calls) == 1 and report.api_calls == 1 and report.results == []
    assert report.errors == ["chiave API non valida (HTTP 401) da api.tavily.com"]


# ------------------------------------------------ HttpClient: get_json/post_json ---
class _ApiHandler(BaseHTTPRequestHandler):
    seen: list[dict] = []

    def log_message(self, *args):
        pass

    def _reply(self, status, obj=None, raw=None):
        data = raw if raw is not None else json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _handle(self, body=None):
        type(self).seen.append({"method": self.command, "path": self.path, "body": body,
                                "auth": self.headers.get("Authorization"),
                                "token": self.headers.get("X-Subscription-Token")})
        key = self.headers.get("Authorization") or self.headers.get("X-Subscription-Token") or ""
        if "bad" in key:
            return self._reply(401, {"error": "unauthorized"})
        if "limit" in key:
            return self._reply(429, {"error": "too many"})
        if "html" in key:
            return self._reply(200, raw=b"<html>")
        self._reply(200, {"ok": True, "body": body})

    def do_POST(self):  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        self._handle(json.loads(self.rfile.read(n) or b"null"))

    def do_GET(self):  # noqa: N802
        self._handle()


@pytest.fixture()
def api_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _ApiHandler)
    _ApiHandler.seen = []
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/api"
    httpd.shutdown()
    httpd.server_close()


def test_http_client_post_json_and_headers(api_server):
    client = HttpClient(delay=0, timeout=2, retries=0)
    out = client.post_json(api_server, {"query": "x"}, headers={"Authorization": "Bearer good"})
    assert out == {"ok": True, "body": {"query": "x"}}
    assert _ApiHandler.seen[-1]["auth"] == "Bearer good" and _ApiHandler.seen[-1]["method"] == "POST"
    out = client.get_json(api_server, params={"q": "a"}, headers={"X-Subscription-Token": "good"})
    assert out["ok"] and _ApiHandler.seen[-1]["token"] == "good" and "q=a" in _ApiHandler.seen[-1]["path"]
    with pytest.raises(FetchError, match=r"chiave API non valida \(HTTP 401\)"):
        client.post_json(api_server, {}, headers={"Authorization": "Bearer bad"})
    with pytest.raises(FetchError, match=r"chiave API non valida \(HTTP 401\)"):
        client.get_json(api_server, headers={"X-Subscription-Token": "bad"})
    with pytest.raises(FetchError, match=r"limite di ricerche raggiunto \(HTTP 429\)"):
        client.post_json(api_server, {}, headers={"Authorization": "Bearer limit"})
    with pytest.raises(FetchError, match="non JSON"):
        client.post_json(api_server, {}, headers={"Authorization": "Bearer html"})


def test_real_tavily_provider_over_http_reports_401(api_server, monkeypatch):
    monkeypatch.setattr(settings, "TAVILY_API_URL", api_server)
    client = HttpClient(delay=0, timeout=2, retries=0)
    report = discover(TavilyProvider(client, api_key="bad-key"), "saas", "Italia", 10)
    assert report.results == [] and report.api_calls == 1
    assert "chiave API non valida (HTTP 401)" in report.errors[0] and "bad-key" not in report.errors[0]


# ------------------------------------------------------------ user_settings ---
def test_user_settings_roundtrip_env_override_and_permissions(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "DATA_HOME", tmp_path / "nuova" / "cartella")
    for var in ("PS_TAVILY_API_KEY", "PS_BRAVE_API_KEY", "PS_SEARXNG_URL", "PS_WEB_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(settings, "SEARXNG_URL", "")
    assert user_settings.load()["web_provider"] == "tavily" and user_settings.get("tavily_api_key") == ""
    assert user_settings.get("tavily_api_key", "x") == "x"
    user_settings.save({"tavily_api_key": " tvly-1 ", "web_provider": "brave"})
    user_settings.save({"brave_api_key": "BSA-1"})                      # unisce, non sovrascrive
    path = tmp_path / "nuova" / "cartella" / "user_settings.json"
    assert path.exists() and stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert json.loads(path.read_text())["tavily_api_key"] == "tvly-1"
    assert user_settings.get("tavily_api_key") == "tvly-1" and user_settings.get("brave_api_key") == "BSA-1"
    assert user_settings.get("web_provider") == "brave"
    assert [p.name for p in path.parent.iterdir()] == ["user_settings.json"]   # nessun temporaneo
    monkeypatch.setenv("PS_TAVILY_API_KEY", "from-env")
    monkeypatch.setenv("PS_WEB_PROVIDER", "searxng")
    assert user_settings.get("tavily_api_key") == "from-env" and user_settings.get("web_provider") == "searxng"
    assert user_settings.load()["tavily_api_key"] == "tvly-1"            # il file non viene toccato
    assert user_settings.get("searxng_url") == ""
    monkeypatch.setattr(settings, "SEARXNG_URL", "http://legacy:8888")   # ripiego sulla vecchia impostazione
    assert user_settings.get("searxng_url") == "http://legacy:8888"
    monkeypatch.setenv("PS_SEARXNG_URL", "http://env:1")
    assert user_settings.get("searxng_url") == "http://env:1"
    path.write_text("{non json")                                         # file corrotto: valori predefiniti
    monkeypatch.delenv("PS_TAVILY_API_KEY")
    assert user_settings.get("tavily_api_key") == ""


# ----------------------------------------------------------------- pipeline ---
def test_web_result_to_prospect():
    r = SearchResult("Acme | Software B2B", "https://blog.acme.io/post?x=1", "  Il   software\nper aziende " + "x" * 600,
                     "tavily", {"rank": 3, "other_urls": ["https://acme.io/p"]})
    p = web_result_to_prospect(r, RunParams(category=WEB_CATEGORY, keyword="saas"), "saas Italia")
    assert p.domain == "acme.io" and p.website == "https://acme.io/"
    assert p.company_name == "Acme" and p.category == "Web Search" and p.source == "tavily"
    assert p.source_url == r.url and p.search_query == "saas Italia" and p.status == "found"
    assert len(p.description) == 500 and p.description.startswith("Il software per aziende")
    assert p.raw_data["name_source"] == "title"
    assert p.raw_data["search"] == {"title": r.title, "snippet": r.snippet, "url": r.url,
                                    "rank": 3, "other_urls": ["https://acme.io/p"]}
    assert not (p.city or p.country or p.email or p.phone)
    home = web_result_to_prospect(SearchResult("X", "http://www.acme.io/chi-siamo", "", "brave"), RunParams(), "q")
    assert home.website == "http://www.acme.io/"
    assert web_result_to_prospect(SearchResult("", "https://acme.io/a", "", "brave"), RunParams(), "q").company_name == "acme.io"


@pytest.fixture(scope="module")
def srv():
    with SiteServer() as s:
        yield s


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "USE_PLAYWRIGHT", False)
    client = HttpClient(delay=0, timeout=1, retries=0)
    db = Database(tmp_path / "t.db")
    messages = []
    pipe = Pipeline(db, client, WebsiteCrawler(client, time_budget=20),
                    on_message=lambda t, lvl="info": messages.append((lvl, t)))
    return pipe, db, messages


def test_web_pipeline_end_to_end(env, srv, monkeypatch):
    pipe, db, messages = env
    base = "hotel Palermo Italia"
    results = {(base, 0): [
        (srv.url("127.0.0.2", "/"), "Hotel Alfa Palermo - Sito ufficiale"),
        (srv.url("127.0.0.2", "/camere"), "Hotel Alfa | Camere"),        # stesso dominio
        (srv.url("127.0.0.7", "/"), "Benvenuti | Studio Beta"),
        (srv.url("127.0.0.3", "/"), "Sito vietato"),                     # robots.txt vieta
        ("https://www.booking.com/hotel/alfa", "Booking")]}              # portale: escluso
    fake = FakeProvider(results, per_call=20)
    monkeypatch.setattr(web_search, "get_provider", lambda name=None, client=None: fake)

    def no_local(*a, **k):
        raise AssertionError("la ricerca locale non deve partire")
    monkeypatch.setattr(pipeline_mod, "run_search", no_local)

    params = RunParams(category=WEB_CATEGORY, keyword="hotel Palermo", location="", max_results=20,
                       mode=MODE_BOTH, search_source=SOURCE_WEB, web_provider="fake")
    res = pipe.run(params)
    assert not res.fatal_error, res.log_text
    texts = [t for _, t in messages]
    assert texts[0] == "Searching the web (Fake)..."
    assert any(t.startswith("Found 5 results, 3 domini aziendali (") and t.endswith("ricerche API)") for t in texts)
    assert "Deduplicating..." in texts and "Enriching websites..." in texts
    assert res.n_found == 3 and res.n_unique == 3 and len(res.prospect_ids) == 3 and not res.provider_errors
    assert fake.calls[0] == (base, 20, 0, "it")

    rows = {p.domain: p for p in db.list_prospects(ids=res.prospect_ids)}
    assert set(rows) == {"127.0.0.2", "127.0.0.7", "127.0.0.3"}
    alfa = rows["127.0.0.2"]
    assert alfa.status == "enriched" and alfa.email == "info@hotelalfa.it"
    assert alfa.category == "Web Search" and alfa.source == "fake" and alfa.search_query == base
    assert alfa.description == "Hotel 4 stelle nel cuore di Palermo"       # dal sito
    assert alfa.company_name == "Hotel Alfa" and alfa.city == "Palermo" and alfa.country
    assert alfa.raw_data["search"]["other_urls"] == [srv.url("127.0.0.2", "/camere")]
    assert alfa.source_url == srv.url("127.0.0.2", "/") and alfa.website == srv.url("127.0.0.2", "/")
    beta = rows["127.0.0.7"]
    assert beta.status == "enriched" and beta.email == "commerciale@studiobeta.it"
    blocked = rows["127.0.0.3"]
    assert blocked.status == "failed" and "robots" in blocked.error_message
    assert blocked.description == "snippet Sito vietato"                   # resta il testo del risultato
    run = db.list_runs()[0]
    assert run["providers"] == "fake" and run["category"] == "Web Search"

    df = prospects_to_dataframe(db.list_prospects(ids=res.prospect_ids))
    reader = list(csv.DictReader(io.StringIO(to_csv_bytes(df).decode("utf-8-sig"))))
    assert len(reader) == 3
    assert {"Company", "Website", "Category", "City", "Region", "Country", "Source", "Search query",
            "Email", "Phone", "Description", "Source URL"} <= set(reader[0])
    row = next(r for r in reader if r["Email"] == "info@hotelalfa.it")
    assert row["Category"] == "Web Search" and row["Source"] == "fake" and row["Search query"] == base
    assert row["Description"] and row["Source URL"]


def test_web_pipeline_reports_provider_errors_and_no_config(env, monkeypatch):
    pipe, db, messages = env
    fake = FakeProvider(fail_on={1: FetchError("chiave API non valida (HTTP 401) da x")})
    monkeypatch.setattr(web_search, "get_provider", lambda name=None, client=None: fake)
    res = pipe.run(RunParams(category=WEB_CATEGORY, keyword="saas", mode=MODE_SEARCH,
                             search_source=SOURCE_WEB, web_provider="fake"))
    assert not res.fatal_error and res.n_found == 0
    assert res.provider_errors == {"fake": "chiave API non valida (HTTP 401) da x"}
    assert ("warning", "Fake: chiave API non valida (HTTP 401) da x") in messages
    messages.clear()
    off = FakeProvider(configured=False)
    monkeypatch.setattr(web_search, "get_provider", lambda name=None, client=None: off)
    res = pipe.run(RunParams(category=WEB_CATEGORY, keyword="saas", mode=MODE_SEARCH,
                             search_source=SOURCE_WEB))
    assert not off.calls and any(l == "warning" and "non configurata" in t for l, t in messages)


def test_local_mode_still_uses_local_search(env, monkeypatch):
    pipe, db, messages = env
    seen = {}

    class Report:
        results = [SearchResult("Hotel Gamma", "https://hotelgamma.it/", "", "osm")]
        errors: dict = {}
        counts = {"osm": 1}

    def fake_run_search(request, providers, client):
        seen["request"], seen["providers"] = request, providers
        return Report()

    def no_web(*a, **k):
        raise AssertionError("la Web Search non deve partire")
    monkeypatch.setattr(pipeline_mod, "run_search", fake_run_search)
    monkeypatch.setattr(web_search, "get_provider", no_web)
    assert RunParams().search_source == SOURCE_LOCAL and RunParams().web_provider is None
    res = pipe.run(RunParams(category="Hospitality", keyword="hotel", location="Palermo",
                             mode=MODE_SEARCH, providers=["osm"]))
    assert not res.fatal_error, res.log_text
    assert seen["request"].keyword == "hotel" and seen["providers"] == ["osm"]
    assert [t for _, t in messages][0] == "Searching..." and res.n_found == 1
    assert db.list_prospects(ids=res.prospect_ids)[0].domain == "hotelgamma.it"


# ------------------------------------------------------------------ interfaccia ---
APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def test_streamlit_app_web_search_smoke(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import streamlit as st

    monkeypatch.setattr(settings, "DATA_HOME", tmp_path)
    monkeypatch.setattr(settings, "DB_PATH", tmp_path / "data" / "prospects.db")
    monkeypatch.setattr(settings, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(settings, "SEARXNG_URL", "")
    monkeypatch.setattr(settings, "DESKTOP", False)
    for var in ("PS_TAVILY_API_KEY", "PS_BRAVE_API_KEY", "PS_SEARXNG_URL", "PS_WEB_PROVIDER"):
        monkeypatch.delenv(var, raising=False)
    st.cache_resource.clear()

    at = AppTest.from_file(APP_PATH, default_timeout=60).run()
    assert not at.exception
    assert at.segmented_control(key="search_source").value == "Local (OSM + Wikidata)"
    assert any(s.label == "Tipo di ricerca" for s in at.selectbox)

    at.segmented_control(key="search_source").set_value("Web Search").run()
    assert not at.exception
    assert any(e.label == "Impostazioni Web Search" for e in at.sidebar.expander)
    assert not any(s.label == "Tipo di ricerca" for s in at.selectbox)
    assert any(t.label == "Località / Paese" for t in at.text_input)
    assert at.checkbox(key="web_enrich").value is True
    assert at.selectbox(key="web_provider_select").value == "tavily"
    secret = at.text_input(key="web_secret_tavily")
    assert secret.label == "Chiave API" and secret.proto.type == 1          # password

    # senza keyword / senza chiave: errori di validazione, nessuna ricerca
    run_btn = next(b for b in at.button if b.label == "CERCA PROSPECT")
    run_btn.click().run()
    assert not at.exception and any("keyword" in e.value for e in at.sidebar.error)
    at.text_input(key="web_keyword").set_value("saas b2b")
    next(b for b in at.button if b.label == "CERCA PROSPECT").click().run()
    assert any("non configurata" in e.value for e in at.sidebar.error)

    # salvataggio della chiave
    at.text_input(key="web_secret_tavily").set_value("tvly-test-key")
    at.button(key="web_save").click().run()
    assert not at.exception
    saved = tmp_path / "user_settings.json"
    assert json.loads(saved.read_text())["tavily_api_key"] == "tvly-test-key"
    assert stat.S_IMODE(os.stat(saved).st_mode) == 0o600
    assert any("✅" in m.value for m in at.sidebar.markdown)

    at.segmented_control(key="search_source").set_value("Local (OSM + Wikidata)").run()
    assert not at.exception
    assert any(s.label == "Tipo di ricerca" for s in at.selectbox)
    assert not any(e.label == "Impostazioni Web Search" for e in at.sidebar.expander)
