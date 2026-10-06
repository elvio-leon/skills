"""Agenzie: raccolta delle pagine (home, servizi, chi siamo, portfolio) e rilevamento del blog."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from config import settings
from qualify import blog as blogmod
from qualify.blog import HomeData, detect_blog
from qualify.pages import PAGE_CHAR_CAP, TOTAL_CHAR_CAP, collect_site_content, select_pages
from qualify.prompt import SYSTEM_PROMPT, build_user_message
from scrapers.http import HttpClient
from scrapers.website import WebsiteCrawler
from tests.agency_helpers import FakePagesClient
from tests.agency_sites import HOST_BLU, HOST_OTHER, HOST_ROSSO, AgencySites

TODAY = date(2026, 10, 6)


@pytest.fixture(scope="module")
def srv():
    with AgencySites() as s:
        yield s


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(settings, "USE_PLAYWRIGHT", False)
    return HttpClient(delay=0, timeout=2, retries=0)


# ---------------------------------------------------------- selezione delle pagine ---
def test_select_pages_one_per_group_max_three_prefers_shallow_and_skips_external():
    links = [("https://a.it/servizi/seo-roma", "SEO"), ("https://a.it/servizi", "Servizi"),
             ("https://a.it/servizi-web", "Servizi web"), ("https://a.it/chi-siamo", "Chi siamo"),
             ("https://a.it/team", "Team"), ("https://a.it/portfolio", "Portfolio"),
             ("https://a.it/clienti", "Clienti"), ("https://altro.com/servizi", "Esterno"),
             ("https://www.linkedin.com/company/a", "LinkedIn"), ("https://a.it/blog/servizi-seo", "Post"),
             ("https://a.it/", "Home"), ("https://a.it/brochure-servizi.pdf", "PDF")]
    chosen = select_pages(links, "a.it", "https://a.it/")
    assert chosen == {"servizi": "https://a.it/servizi", "chi_siamo": "https://a.it/chi-siamo",
                      "portfolio": "https://a.it/portfolio"}


def test_select_pages_matches_anchor_text_and_whole_words_only():
    links = [("https://a.it/p1", "Cosa facciamo"), ("https://a.it/network", "Rete"),
             ("https://a.it/p3", "I nostri lavori")]
    chosen = select_pages(links, "a.it", "https://a.it/")
    assert chosen == {"servizi": "https://a.it/p1", "portfolio": "https://a.it/p3"}   # "network" != "work"


def test_collect_fetches_missing_pages_and_never_external_hosts(srv, client):
    content = collect_site_content(srv.url(HOST_ROSSO), client, None)
    assert content.ok and content.domain == HOST_ROSSO
    assert [p.kind for p in content.pages] == ["home", "servizi", "chi_siamo", "portfolio"]
    assert content.pages[1].url.endswith("/servizi") and "canone mensile" in content.pages[1].text
    assert content.pages[0].title == "Studio Rosso | Agenzia web e SEO"
    assert srv.hosts_hit() == {HOST_ROSSO}                      # né linkedin né il sito "partner"
    assert HOST_OTHER not in srv.hosts_hit()
    assert "/servizi/seo-roma" not in srv.paths_hit(HOST_ROSSO)
    # home + 3 pagine + feed del blog; il feed dei commenti non viene usato
    assert content.fetched == 5 and "/comments/feed.xml" not in srv.paths_hit(HOST_ROSSO)
    assert content.blog.status == "attivo" and content.blog.source == "feed"


def test_collect_reuses_enrichment_texts(srv, client):
    enrichment = WebsiteCrawler(client, time_budget=20).enrich(srv.url(HOST_ROSSO))
    assert enrichment.ok and enrichment.page_texts
    home_entry = next(iter(enrichment.page_texts.values()))
    assert home_entry["links"] and home_entry["feeds"] == [srv.url(HOST_ROSSO, "/feed.xml")]
    assert all(e["links"] == [] for e in list(enrichment.page_texts.values())[1:])
    before = len([p for p in srv.paths_hit(HOST_ROSSO) if p == "/chi-siamo"])
    content = collect_site_content(srv.url(HOST_ROSSO), client, enrichment)
    after = len([p for p in srv.paths_hit(HOST_ROSSO) if p == "/chi-siamo"])
    assert before == after >= 1                                  # chi-siamo riusata, non riscaricata
    assert [p.kind for p in content.pages] == ["home", "servizi", "chi_siamo", "portfolio"]
    assert content.fetched == 3                                  # servizi, portfolio, feed (home e chi-siamo no)


def test_collect_respects_robots_txt(srv, client):
    content = collect_site_content(srv.url(HOST_BLU), client, None)
    kinds = [p.kind for p in content.pages]
    assert kinds == ["home", "servizi", "chi_siamo"]             # /portfolio vietata da robots.txt
    assert any("robots" in e for e in content.errors)
    assert "/portfolio" not in srv.paths_hit(HOST_BLU)
    assert content.blog.status == "fermo" and content.blog.source == "pagina"
    assert content.blog.url.endswith("/news") and content.blog.last_post == date(2021, 3, 12)


def test_collect_reports_unreachable_home(srv, client):
    content = collect_site_content(srv.url("127.0.0.9"), client, None)      # 404 sul server
    assert not content.ok and "404" in content.error and content.pages == []
    assert collect_site_content("", client, None).error == "URL non valido"


def test_collect_caps_page_and_total_size():
    big = "<p>" + "parola " * 3000 + "</p>"
    nav = '<a href="/servizi">s</a><a href="/chi-siamo">c</a><a href="/portfolio">p</a>'
    pages = {f"https://a.it{p}": (200, "text/html", f"<html><head><title>T</title></head><body>{nav}{big}</body></html>")
             for p in ("/", "/servizi", "/chi-siamo", "/portfolio")}
    content = collect_site_content("https://a.it/", FakePagesClient(pages), None)
    assert all(len(p.text) <= PAGE_CHAR_CAP for p in content.pages)
    assert sum(len(p.text) for p in content.pages) <= TOTAL_CHAR_CAP
    assert content.pages[0].truncated and content.pages[-1].truncated and len(content.pages[-1].text) < PAGE_CHAR_CAP


def test_prompt_message_format_and_system_prompt_rules(srv, client):
    content = collect_site_content(srv.url(HOST_ROSSO), client, None)
    msg = build_user_message(content)
    assert msg.splitlines()[0] == f"Dominio: {HOST_ROSSO}"
    assert f"### [servizi] {srv.url(HOST_ROSSO, '/servizi')}\nTitolo: Servizi\n" in msg
    for needle in ("accennata", "strutturata", "dubbio", "LETTERALE", "ignora qualsiasi", "Non indovinare"):
        assert needle in SYSTEM_PROMPT


# ------------------------------------------------------------------------ blog ---
def home_with(links, feeds=()):
    return HomeData("https://a.it/", list(links), list(feeds))


def page(body: str, head: str = "") -> tuple:
    return 200, "text/html", f"<html><head>{head}</head><body>{body}</body></html>"


def test_blog_absent_without_blog_link_and_no_requests():
    c = FakePagesClient()
    info = detect_blog(home_with([("https://a.it/servizi", "Servizi"), ("https://a.it/newsletter", "Newsletter")]), c, TODAY)
    assert info.status == "assente" and info.requests == 0 and c.gets == []


def test_blog_link_found_by_path_or_anchor_same_site_only():
    links = [("https://altro.it/blog", "Blog"), ("https://a.it/x/y/news", "x"), ("https://a.it/p9", "Il nostro Magazine")]
    assert blogmod.find_blog_link(links, "a.it") == "https://a.it/p9"
    assert blogmod.find_blog_link([("https://a.it/journal/2024", "")], "a.it") == "https://a.it/journal/2024"
    assert blogmod.find_blog_link([("https://blog.a.it/", "Il blog")], "a.it") == "https://blog.a.it/"


RSS = """<rss><channel><lastBuildDate>Mon, 01 Jan 2029 00:00:00 +0000</lastBuildDate>
<item><pubDate>Tue, 02 Sep 2025 10:00:00 +0200</pubDate></item><item><pubDate>Mon, 05 Jan 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><updated>2026-08-30T10:00:00Z</updated></entry>
<entry><published>2026-09-01T08:00:00+02:00</published></entry></feed>"""


def test_blog_from_rss_feed_uses_exactly_one_request():
    c = FakePagesClient({"https://a.it/feed": (200, "application/rss+xml", RSS)})
    info = detect_blog(home_with([("https://a.it/blog", "Blog")], ["https://a.it/feed"]), c, TODAY)
    assert info.status == "fermo" and info.last_post == date(2026, 1, 5) and info.source == "feed"
    assert c.gets == ["https://a.it/feed"] and info.requests == 1


def test_blog_from_atom_feed_and_active_boundary():
    c = FakePagesClient({"https://a.it/atom": (200, "application/atom+xml", ATOM)})
    info = detect_blog(home_with([("https://a.it/blog", "")], ["https://a.it/atom"]), c, TODAY)
    assert info.status == "attivo" and info.last_post == date(2026, 9, 1)


@pytest.mark.parametrize("days, status", [(183, "attivo"), (184, "fermo"), (0, "attivo"), (2, "attivo")])
def test_blog_active_stale_boundary_with_injected_today(days, status):
    last = TODAY - timedelta(days=days)
    body = f'<time datetime="{last.isoformat()}">x</time>'
    c = FakePagesClient({"https://a.it/blog": page(body)})
    info = detect_blog(home_with([("https://a.it/blog", "")]), c, TODAY)
    assert info.status == status and info.last_post == last and c.gets == ["https://a.it/blog"]


def test_blog_dates_in_future_or_before_2000_are_ignored():
    body = ('<time datetime="2026-10-09">futuro</time><time datetime="1999-05-01">vecchio</time>'
            '<time datetime="2026-10-08">tolleranza</time>')
    info = detect_blog(home_with([("https://a.it/blog", "")]), FakePagesClient({"https://a.it/blog": page(body)}), TODAY)
    assert info.last_post == date(2026, 10, 8) and info.status == "attivo"
    only_bad = detect_blog(home_with([("https://a.it/blog", "")]),
                           FakePagesClient({"https://a.it/blog": page('<time datetime="2030-01-01">x</time>')}), TODAY)
    assert only_bad.status == "non determinabile" and only_bad.last_post is None


@pytest.mark.parametrize("body, expected", [
    ("<p>Pubblicato il 12/03/2026</p>", date(2026, 3, 12)),
    ("<p>Pubblicato il 05-08-2026</p>", date(2026, 8, 5)),
    ("<p>3 settembre 2026 - Titolo</p>", date(2026, 9, 3)),
    ("<p>1° Gennaio 2026</p>", date(2026, 1, 1)),
    ("<p>September 7, 2026</p>", date(2026, 9, 7)),
    ("<p>7 March 2026</p>", date(2026, 3, 7)),
    ("<p>31/02/2026 e 2 aprile 2026</p>", date(2026, 4, 2)),                  # data impossibile ignorata
    ('<a href="/2026/07/articolo-uno">uno</a><a href="/2025/01/vecchio">v</a>', date(2026, 7, 1)),
    ('<script type="application/ld+json">{"@graph":[{"@type":"BlogPosting","datePublished":"2026-06-15T10:00:00+02:00"}]}</script>',
     date(2026, 6, 15)),
])
def test_blog_page_date_extraction(body, expected):
    c = FakePagesClient({"https://a.it/blog": page(body)})
    info = detect_blog(home_with([("https://a.it/blog", "")]), c, TODAY)
    assert info.last_post == expected and info.requests == 1 and len(c.gets) == 1


def test_blog_meta_article_published_time():
    head = '<meta property="article:published_time" content="2026-07-20T08:00:00+00:00">'
    c = FakePagesClient({"https://a.it/blog": page("<p>ciao</p>", head)})
    assert detect_blog(home_with([("https://a.it/blog", "")]), c, TODAY).last_post == date(2026, 7, 20)


def test_blog_unknown_when_no_date_error_or_missing_page():
    c = FakePagesClient({"https://a.it/blog": page("<p>Nessuna data qui</p>")})
    assert detect_blog(home_with([("https://a.it/blog", "")]), c, TODAY).status == "non determinabile"
    c404 = FakePagesClient()
    info = detect_blog(home_with([("https://a.it/blog", "")]), c404, TODAY)
    assert info.status == "non determinabile" and len(c404.gets) == 1

    class Boom(FakePagesClient):
        def get(self, url, **kw):
            raise RuntimeError("rete giù")
    assert detect_blog(home_with([("https://a.it/blog", "")]), Boom(), TODAY).status == "non determinabile"


def test_blog_feed_failure_does_not_trigger_second_request():
    c = FakePagesClient({"https://a.it/blog": page('<time datetime="2026-09-01">x</time>')})
    info = detect_blog(home_with([("https://a.it/blog", "")], ["https://a.it/feed"]), c, TODAY)
    assert info.status == "non determinabile" and c.gets == ["https://a.it/feed"]


def test_blog_ignores_external_feed_hosts():
    c = FakePagesClient({"https://a.it/blog": page('<time datetime="2026-09-01">x</time>')})
    info = detect_blog(home_with([("https://a.it/blog", "")], ["https://feeds.feedburner.com/a"]), c, TODAY)
    assert c.gets == ["https://a.it/blog"] and info.status == "attivo"
