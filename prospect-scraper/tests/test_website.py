import pytest

from scrapers.http import HttpClient
from scrapers.website import WebsiteCrawler
from tests.site_server import SiteServer


@pytest.fixture(scope="module")
def srv():
    with SiteServer() as s:
        yield s


@pytest.fixture()
def crawler():
    return WebsiteCrawler(HttpClient(delay=0, timeout=2, retries=0), max_pages=10, time_budget=30)


def test_full_site(srv, crawler):
    r = crawler.enrich(srv.url("127.0.0.2"))
    assert r.ok, r.error
    assert r.company_name == "Hotel Alfa"
    assert r.city == "Palermo" and r.country == "Italia" and r.region == "Sicilia"
    assert r.postal_code == "90133" and r.vat_id == "01234567890"
    assert r.emails[0] == "info@hotelalfa.it"
    assert "prenotazioni@hotelalfa.it" in r.emails and "mario@hotelalfa.it" in r.emails
    assert "noreply@hotelalfa.it" not in r.emails
    assert "privacy@hotelalfa.it" not in r.emails          # /privacy vietata da robots.txt
    assert r.phones[0].e164 == "+390911234567" and r.phones[0].from_tel_link
    assert "+393337654321" in [p.e164 for p in r.phones]
    assert r.socials["linkedin"] == ["https://www.linkedin.com/company/hotel-alfa"]
    assert r.socials["facebook"] == ["https://www.facebook.com/HotelAlfaPalermo"]
    assert r.socials["instagram"] == ["https://www.instagram.com/hotelalfa"]
    visited = " ".join(r.pages_visited)
    assert "/contatti" in visited and "/chi-siamo" in visited and "/team" in visited
    assert "/camere" not in visited and "brochure" not in visited
    assert "robots" in r.pages_failed.get(srv.url("127.0.0.2", "/privacy"), "")


def test_max_pages(srv):
    c = WebsiteCrawler(HttpClient(delay=0, timeout=2, retries=0), max_pages=2)
    r = c.enrich(srv.url("127.0.0.2"))
    assert len(r.pages_visited) == 2
    assert "/contatti" in r.pages_visited[1]  # la pagina contatti ha la priorità


def test_robots_disallow(srv, crawler):
    r = crawler.enrich(srv.url("127.0.0.3"))
    assert not r.ok and "robots" in r.error


def test_robots_500_means_disallow(srv, crawler):
    r = crawler.enrich(srv.url("127.0.0.8"))
    assert not r.ok and "robots" in r.error


def test_captcha_not_bypassed(srv, crawler):
    r = crawler.enrich(srv.url("127.0.0.4"))
    assert not r.ok and "CAPTCHA" in r.error


def test_timeout(srv):
    c = WebsiteCrawler(HttpClient(delay=0, timeout=1, retries=0))
    r = c.enrich(srv.url("127.0.0.5"))
    assert not r.ok and "timeout" in r.error


def test_404_and_non_html(srv, crawler):
    assert "404" in crawler.enrich(srv.url("127.0.0.9")).error
    assert "non HTML" in crawler.enrich(srv.url("127.0.0.10")).error


def test_dns_failure(crawler):
    r = crawler.enrich("http://dominio-che-non-esiste-xyz.invalid")
    assert not r.ok and r.error


def test_redirect_and_anchor_text_discovery(srv, crawler):
    r = crawler.enrich(srv.url("127.0.0.7"))
    assert r.ok, r.error
    assert r.final_url.endswith("/it/")
    assert r.company_name == "Studio Beta"
    assert r.emails == ["commerciale@studiobeta.it"]
    assert [p.e164 for p in r.phones] == ["+390287654321"]  # la P.IVA non è un telefono
    assert r.vat_id == "09876543210"
    assert r.city == "Milano" and r.region == "Lombardia"
    assert r.socials["twitter"] == ["https://x.com/studiobeta"]


def test_js_page(srv, crawler):
    r = crawler.enrich(srv.url("127.0.0.6"))
    assert r.ok
    if r.rendered_js:  # Playwright + Chromium disponibili
        assert r.emails == ["hello@spaco.io"]
        assert r.socials["linkedin"] == ["https://www.linkedin.com/company/spaco"]
    else:
        assert any("JavaScript" in w for w in r.warnings)
