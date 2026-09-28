from models.prospect import Prospect
from utils.deduplication import deduplicate
from utils.normalization import homepage_url, normalize_domain, normalize_name, normalize_url


def test_domain_variants_are_equal():
    variants = [
        "https://www.hotel-example.it",
        "http://hotel-example.it/",
        "https://hotel-example.it",
        "HOTEL-EXAMPLE.IT",
        "www.hotel-example.it/contatti?x=1#top",
        "https://www2.hotel-example.it:443/",
    ]
    assert {normalize_domain(v) for v in variants} == {"hotel-example.it"}


def test_invalid_domains():
    assert normalize_domain("") is None
    assert normalize_domain(None) is None
    assert normalize_domain("mailto:info@x.it") is None
    assert normalize_domain("javascript:void(0)") is None
    assert normalize_domain("nodot") is None


def test_idn_and_subdomain():
    assert normalize_domain("https://www.caffè.it") == "xn--caff-8oa.it"
    assert normalize_domain("https://shop.brand.it") == "shop.brand.it"


def test_normalize_url_and_home():
    assert normalize_url("HTTPS://WWW.Example.IT/Path?a=1#frag") == "https://www.example.it/Path?a=1"
    assert homepage_url("example.it/chi-siamo") == "https://example.it/"
    assert normalize_url("http://127.0.0.2:8000/x") == "http://127.0.0.2:8000/x"


def test_normalize_name():
    assert normalize_name("Hotel Città S.r.l.") == normalize_name("hotel citta srl")
    assert normalize_name("ACME SpA") == "acme"


def test_dedup_by_domain_merges_fields():
    a = Prospect(company_name="Hotel X", website="https://www.hotelx.it", source="osm")
    b = Prospect(company_name="Hotel X Palermo", website="http://hotelx.it/", phone="+39091", source="searxng")
    c = Prospect(company_name="Other", website="https://other.it")
    out = deduplicate([a, b, c])
    assert len(out) == 2
    assert out[0].phone == "+39091"
    assert out[0].company_name == "Hotel X"
    assert out[0].source == "osm, searxng"


def test_dedup_by_name_city_without_domain():
    a = Prospect(company_name="Bar Roma S.r.l.", city="Palermo")
    b = Prospect(company_name="bar roma srl", city="palermo", phone="123")
    c = Prospect(company_name="Bar Roma", city="Milano")
    out = deduplicate([a, b, c])
    assert len(out) == 2
    assert out[0].phone == "123"
