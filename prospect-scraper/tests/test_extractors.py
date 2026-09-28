from bs4 import BeautifulSoup

from scrapers.company import (company_name_from_title, extract_address, extract_jsonld,
                              extract_meta, extract_microdata, extract_vat)
from scrapers.contacts import extract_emails, extract_phones, sort_emails
from scrapers.social import extract_socials, normalize_social_url

HTML = """
<html lang="it"><head><title>Home | Hotel Alfa Palermo</title>
<meta name="description" content="Hotel 4 stelle nel centro di Palermo">
<meta property="og:site_name" content="Hotel Alfa">
<script type="application/ld+json">
{"@context":"https://schema.org","@graph":[{"@type":"WebSite","name":"Sito"},
 {"@type":"Hotel","name":"Hotel Alfa","telephone":"+39 091 1234567","email":"booking@hotelalfa.it",
  "address":{"@type":"PostalAddress","streetAddress":"Via Roma 10","postalCode":"90133",
  "addressLocality":"Palermo","addressRegion":"PA","addressCountry":"IT"},
  "sameAs":["https://www.instagram.com/hotelalfa/","https://www.facebook.com/HotelAlfa"]}]}
</script></head>
<body>
<a href="mailto:Info@HotelAlfa.it?subject=Ciao">Scrivici</a>
<a href="mailto:noreply@hotelalfa.it">x</a>
<p>Commerciale: commerciale@hotelalfa.it - Email: info@hotelalfa.it.</p>
<img src="/img/logo@2x.png"> <span>privacy@hotelalfa.it</span>
<p>Staff: mario.rossi@gmail.com</p>
<div data-x="abc123def4567890abc123def4567890@sentry.io"></div>
<a href="tel:+390911234567">091 123 4567</a>
<p>Cell. 333 123 4567 · Int: +44 20 7946 0958</p>
<footer>Hotel Alfa S.r.l. - Via Roma, 10 - 90133 Palermo (PA) - P.IVA 01234567890 - REA PA-123456
Cap. soc. 10.000 € - CF 01234567890</footer>
<a href="https://www.linkedin.com/company/hotel-alfa/about/">in</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=x">share</a>
<a href="https://www.facebook.com/HotelAlfa/">fb</a>
<a href="https://instagram.com/p/ABC123/">post</a>
<a href="https://twitter.com/intent/tweet?text=x">tw</a>
<a href="https://x.com/hotelalfa?lang=it">x</a>
<a href="https://www.youtube.com/watch?v=abc">video</a>
<a href="https://www.youtube.com/@hotelalfa/videos">yt</a>
</body></html>
"""
SOUP = BeautifulSoup(HTML, "lxml")


def test_emails():
    emails = extract_emails(SOUP, HTML)
    assert "info@hotelalfa.it" in emails and "commerciale@hotelalfa.it" in emails
    assert "privacy@hotelalfa.it" in emails and "mario.rossi@gmail.com" in emails
    assert not any(e.startswith("noreply") for e in emails)
    assert not any("2x" in e or "sentry" in e for e in emails)
    assert len(emails) == len(set(emails))
    ordered = sort_emails(emails, "hotelalfa.it")
    assert ordered[0] == "info@hotelalfa.it"
    assert ordered[-1] == "mario.rossi@gmail.com"


def test_phones():
    phones = extract_phones(SOUP)
    e164 = [p.e164 for p in phones]
    assert e164[0] == "+390911234567"            # dal link tel: per primo
    assert "+393331234567" in e164                # cellulare italiano
    assert "+442079460958" in e164                # internazionale
    assert "+3901234567890" not in e164 and not any("1234567890" in e for e in e164[1:] if e.endswith("567890")
                                                     and e != "+390911234567")
    assert phones[0].raw == "091 123 4567"


def test_vat_is_not_phone():
    soup = BeautifulSoup("<p>P.IVA 01234567890</p><p>C.F. 01234567890</p><p>Tel 06 1234 5678</p>", "lxml")
    assert [p.e164 for p in extract_phones(soup)] == ["+390612345678"]


def test_socials():
    anchors = [a["href"] for a in SOUP.find_all("a", href=True)]
    s = extract_socials(anchors + ["https://www.instagram.com/hotelalfa/"])
    assert s["linkedin"] == ["https://www.linkedin.com/company/hotel-alfa"]
    assert s["facebook"] == ["https://www.facebook.com/HotelAlfa"]
    assert s["instagram"] == ["https://www.instagram.com/hotelalfa"]
    assert s["twitter"] == ["https://x.com/hotelalfa"]
    assert s["youtube"] == ["https://www.youtube.com/@hotelalfa"]
    assert normalize_social_url("https://www.facebook.com/profile.php?id=123&ref=x") == \
        ("facebook", "https://www.facebook.com/profile.php?id=123")
    assert normalize_social_url("https://example.com/facebook") is None


def test_company_info():
    ld = extract_jsonld(SOUP)
    assert ld["name"] == "Hotel Alfa" and ld["city"] == "Palermo" and ld["country"] == "Italia"
    assert ld["email"] == "booking@hotelalfa.it"
    meta = extract_meta(SOUP)
    assert meta["description"].startswith("Hotel 4 stelle") and meta["site_name"] == "Hotel Alfa"
    text = SOUP.get_text(" ")
    addr = extract_address(text)
    assert addr["postal_code"] == "90133" and addr["city"] == "Palermo" and addr["province"] == "PA"
    assert addr["address"].startswith("Via Roma")
    assert extract_vat(text) == "01234567890"


def test_address_variants():
    assert extract_address("Sede: Viale Europa 5/A, 20121 Milano MI Italia")["city"] == "Milano"
    assert extract_address("Corso Italia 1 - 00198 Roma (RM)")["address"] == "Corso Italia 1"
    assert extract_address("ordine 12345 Prodotto") == {}
    assert extract_address("tel 20121 Milano (MI)")["city"] == "Milano"


def test_microdata():
    soup = BeautifulSoup('<span itemprop="addressLocality">Roma</span><meta itemprop="addressCountry" content="IT">', "lxml")
    assert extract_microdata(soup) == {"city": "Roma", "country": "Italia"}


def test_title_to_name():
    assert company_name_from_title("Home | Hotel Alfa Palermo", "hotelalfa.it") == "Hotel Alfa Palermo"
    assert company_name_from_title("Camere - Hotel Gamma | Palermo", "hotelgamma.it") == "Hotel Gamma"
    assert company_name_from_title("Benvenuti", "x.it") == ""
