from scrapers.search import SearchRequest, run_search, search
from scrapers.search.osm import OSMProvider
from scrapers.search.searxng import SearXNGProvider
from scrapers.search.wikidata import WikidataProvider
from tests.fakes import FakeClient


def test_osm_search_uses_place_from_keyword_and_stars():
    client = FakeClient()
    results = OSMProvider(client).search(
        SearchRequest("hotel 4 stelle Palermo", "Italia", "Hospitality", 20))
    overpass_query = next(d["data"] for u, p, d in client.calls if "overpass" in u)
    assert "area(id:3600039150)" in overpass_query  # Palermo, non Italia
    assert '["tourism"="hotel"]["stars"~"^4"]' in overpass_query
    names = [r.title for r in results]
    assert names[:2] == ["Grand Hotel Alfa", "Hotel Beta"]       # prima quelli con sito
    assert "Hotel Senza Sito" in names and len(results) == 4      # quello senza nome scartato
    alfa = results[0]
    assert alfa.url == "https://www.hotelalfa.it/"
    assert alfa.extra["city"] == "Palermo" and alfa.extra["region"] == "Sicilia"
    assert alfa.extra["address"] == "Via Roma 10, 90133 Palermo"
    assert alfa.extra["email"] == "info@hotelalfa.it"
    no_site = next(r for r in results if r.title == "Hotel Senza Sito")
    assert no_site.url == ""                                       # mai inventato


def test_osm_ignores_non_place_words():
    client = FakeClient()
    OSMProvider(client).search(SearchRequest("boutique hotel", "Sicilia", "Hospitality", 10))
    q = next(d["data"] for u, p, d in client.calls if "overpass" in u)
    assert "area(id:3600039152)" in q  # Sicilia


def test_wikidata_search():
    client = FakeClient()
    results = WikidataProvider(client).search(
        SearchRequest("magazine tecnologia", "Italia", "Editoriale", 10))
    srsearch = next(p["srsearch"] for u, p, d in client.calls if p and p.get("list") == "search")
    assert "tecnologia" in srsearch and "haswbstatement:P31=Q41298" in srsearch
    assert "haswbstatement:P17=Q38|P495=Q38" in srsearch
    assert [r.title for r in results] == ["Tech Magazine Italia"]  # chiusa e senza sito escluse
    r = results[0]
    assert r.extra["city"] == "Milano" and r.extra["country"] == "Italia"
    assert r.extra["instagram"] == "https://www.instagram.com/techmagit"


def test_searxng_filters_portals_and_duplicates():
    client = FakeClient()
    provider = SearXNGProvider(client, base_url="http://searx.local")
    results = provider.search(SearchRequest("hotel", "Palermo", "Hospitality", 10))
    assert [r.url for r in results] == ["https://www.hotelgamma.it/camere",
                                        "https://blog.example.org/migliori-hotel"]
    assert not SearXNGProvider(client, base_url="").is_available()


def test_provider_failure_does_not_block_others():
    client = FakeClient(fail={"overpass"})
    report = run_search(SearchRequest("hotel Palermo", "", "Custom", 10), ["osm", "wikidata"], client)
    assert "osm" in report.errors and "timeout" in report.errors["osm"]
    assert report.counts.get("wikidata", 0) >= 0


def test_search_interface_returns_dicts():
    out = search("hotel", 5, location="Palermo", category="Hospitality", providers=["osm"],
                 client=FakeClient())
    assert out and set(out[0]) >= {"title", "url", "snippet", "source"}
    assert out[0]["source"] == "osm"


def test_overpass_falls_back_to_mirror(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "OVERPASS_URL", "https://overpass-main.example/api")
    monkeypatch.setattr(settings, "OVERPASS_MIRRORS", ["https://overpass-mirror.example/api"])
    client = FakeClient(fail={"overpass-main"})
    results = OSMProvider(client).search(SearchRequest("hotel", "Palermo", "Hospitality", 5))
    assert results
    urls = [u for u, p, d in client.calls if "overpass" in u]
    assert urls == ["https://overpass-main.example/api", "https://overpass-mirror.example/api"]


def test_overpass_all_down_reports_error(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "OVERPASS_MIRRORS", ["https://overpass-mirror.example/api"])
    report = run_search(SearchRequest("hotel", "Palermo", "Hospitality", 5), ["osm"],
                        FakeClient(fail={"overpass"}))
    assert "osm" in report.errors
