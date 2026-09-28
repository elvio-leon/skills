"""Estrazione delle informazioni aziendali: nome, titolo, descrizione, indirizzo,
città, paese, P.IVA. Fonti in ordine di affidabilità: JSON-LD schema.org,
microdata, meta tag, pattern di indirizzo italiano nel testo."""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from scrapers.search.geo import COUNTRIES, COUNTRY_BY_NAME
from utils.normalization import clean_text

ORG_TYPES = re.compile(
    r"(Organization|Organisation|Business|Corporation|Hotel|Lodging|Resort|Hostel|Motel|"
    r"BedAndBreakfast|Restaurant|Store|Shop|Agency|Company|NewsMedia|Publisher|Winery|"
    r"Brewery|Campground|FoodEstablishment|ProfessionalService|LegalService|Dentist|"
    r"MedicalBusiness|HealthAndBeautyBusiness|Place)$",
    re.I,
)

_PROVINCES = (
    "AG AL AN AO AP AQ AR AT AV BA BG BI BL BN BO BR BS BT BZ CA CB CE CH CL CN CO CR CS CT "
    "CZ EN FC FE FG FI FM FR GE GO GR IM IS KR LC LE LI LO LT LU MB MC ME MI MN MO MS MT NA "
    "NO NU OR PA PC PD PE PG PI PN PO PR PT PU PV PZ RA RC RE RG RI RM RN RO SA SI SO SP SR "
    "SS SU SV TA TE TN TO TP TR TS TV UD VA VB VC VE VI VR VT VV"
).split()
_STREET = (r"(?:Via|V\.le|Viale|Piazza|P\.zza|P\.za|Piazzale|Corso|C\.so|Largo|Vicolo|Contrada|C\.da|"
           r"Strada|Str\.|Lungomare|Lungotevere|Borgo|Località|Loc\.|Frazione|Fraz\.|Salita|Via\s+Nazionale)")
_CITY = r"[A-ZÀ-Ý][\w'’.-]*(?:\s+(?:[A-ZÀ-Ý][\w'’.-]*|di|de|del|della|dei|sul|sulla|al|in|a|d'[A-ZÀ-Ý][\w'’.-]*))*"
# "Via Roma 10, 90133 Palermo (PA)" / "Via Roma, 10 - 90133 Palermo PA"
ADDRESS_RE = re.compile(
    rf"(?P<street>\b{_STREET}\s+[^\n,;|]{{2,60}}?(?:,?\s*(?:n\.?\s*)?(?:\d{{1,4}}[A-Za-z]?(?:/[A-Za-z0-9]+)?|snc))?)"
    rf"\s*[,\-–|]?\s*(?P<cap>\d{{5}})\s+(?P<city>{_CITY})(?:\s*\(\s*(?P<prov>[A-Z]{{2}})\s*\))?"
)
CAP_CITY_RE = re.compile(rf"\b(?P<cap>\d{{5}})\s+(?P<city>{_CITY})\s*\(\s*(?P<prov>[A-Z]{{2}})\s*\)")
_CITY_STOP = {"tel", "tel.", "telefono", "fax", "email", "e-mail", "mail", "p", "p.", "partita",
              "c.f.", "cf", "cod", "cell", "cell.", "mob", "info", "sede", "italia", "italy", "it",
              "whatsapp", "pec", "reg", "rea", "capitale", "cap", "copyright"}


def _clean_city(raw: str) -> tuple[str, str]:
    """Pulisce la città catturata: toglie la coda (sigla provincia, "Italia", "Tel"...)."""
    tokens = raw.split()
    prov = ""
    for i, tok in enumerate(tokens):
        if i and (tok.lower() in _CITY_STOP or tok.lower().rstrip(".:") in _CITY_STOP):
            tokens = tokens[:i]
            break
        if i and tok in _PROVINCES:
            prov = tok
            tokens = tokens[:i]
            break
    while tokens and tokens[-1].lower() in {"di", "de", "del", "della", "dei", "sul", "sulla", "al", "in", "a"}:
        tokens.pop()
    return " ".join(tokens).strip(" .-'’"), prov


VAT_RE = re.compile(
    r"(?:P\.?\s?IVA|Partita\s+I\.?V\.?A\.?|VAT(?:\s+(?:number|no\.?|n\.?|id))?|C\.?F\.?\s*(?:e|/|-)\s*P\.?\s?IVA)"
    r"\s*[:.]?\s*(?:n\.?|nr\.?|n°)?\s*(?:IT\s?)?(\d{11})\b",
    re.I,
)
_TITLE_SPLIT = re.compile(r"\s+[|–—\-·•:»]\s+|\s*[|–—·•»]\s*")
_GENERIC_TITLES = {"home", "homepage", "home page", "benvenuti", "benvenuto", "welcome",
                   "sito ufficiale", "official site", "official website", "sito web", "index",
                   "pagina iniziale", "contatti", "contacts", "contact"}


def country_name(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("name") or value.get("@id") or ""
    value = clean_text(value if isinstance(value, str) else "")
    if not value:
        return ""
    low = value.lower()
    if low in COUNTRIES:
        return COUNTRIES[low][1]
    if low in COUNTRY_BY_NAME:
        return COUNTRIES[COUNTRY_BY_NAME[low]][1]
    return value


def _iter_nodes(data: Any):
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        yield data
        for key in ("@graph", "mainEntity", "publisher", "provider", "author", "brand", "organizer"):
            if key in data:
                yield from _iter_nodes(data[key])


def _types(node: dict) -> list[str]:
    t = node.get("@type", [])
    return [t] if isinstance(t, str) else [x for x in t if isinstance(x, str)]


def _first(value):
    if isinstance(value, list):
        return value[0] if value else ""
    return value


def extract_jsonld(soup: BeautifulSoup) -> dict[str, Any]:
    """Dati di organizzazione/attività da JSON-LD. Restituisce il nodo più completo."""
    best: dict[str, Any] = {}
    best_score = 0
    for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = script.string or script.get_text() or ""
        try:
            data = json.loads(raw.strip())
        except (ValueError, TypeError):
            continue
        for node in _iter_nodes(data):
            if not any(ORG_TYPES.search(t) for t in _types(node)):
                continue
            out: dict[str, Any] = {"type": ", ".join(_types(node))}
            out["name"] = clean_text(_first(node.get("name")) if isinstance(_first(node.get("name")), str) else "")
            for key, field in (("telephone", "phone"), ("email", "email"), ("vatID", "vat_id"),
                               ("taxID", "tax_id"), ("url", "url"), ("description", "description")):
                v = _first(node.get(key))
                if isinstance(v, str) and v.strip():
                    out[field] = clean_text(v)
            same = node.get("sameAs") or []
            out["same_as"] = [s for s in ([same] if isinstance(same, str) else same) if isinstance(s, str)]
            addr = _first(node.get("address"))
            if isinstance(addr, dict):
                out["address"] = clean_text(addr.get("streetAddress") if isinstance(addr.get("streetAddress"), str) else "")
                out["postal_code"] = clean_text(str(addr.get("postalCode") or ""))
                out["city"] = clean_text(addr.get("addressLocality") if isinstance(addr.get("addressLocality"), str) else "")
                out["region"] = clean_text(addr.get("addressRegion") if isinstance(addr.get("addressRegion"), str) else "")
                out["country"] = country_name(addr.get("addressCountry"))
            elif isinstance(addr, str):
                out["address_text"] = clean_text(addr)
            score = sum(1 for v in out.values() if v)
            if score > best_score:
                best, best_score = out, score
    return best


def extract_microdata(soup: BeautifulSoup) -> dict[str, str]:
    out = {}
    for prop, field in (("streetAddress", "address"), ("postalCode", "postal_code"),
                        ("addressLocality", "city"), ("addressRegion", "region"),
                        ("addressCountry", "country")):
        el = soup.find(attrs={"itemprop": prop})
        if el:
            value = clean_text(el.get("content") or el.get_text(" "))
            if value:
                out[field] = country_name(value) if field == "country" else value
    return out


def extract_meta(soup: BeautifulSoup) -> dict[str, str]:
    def meta(**attrs):
        tag = soup.find("meta", attrs=attrs)
        return clean_text(tag.get("content")) if tag and tag.get("content") else ""

    title = clean_text(soup.title.get_text()) if soup.title else ""
    return {
        "title": title,
        "description": meta(name=re.compile("^description$", re.I))
        or meta(property="og:description"),
        "site_name": meta(property="og:site_name"),
        "lang": (soup.html.get("lang", "") if soup.html else "")[:5],
    }


def extract_address(text: str) -> dict[str, str]:
    """Indirizzo italiano dal testo (es. footer). Solo se il pattern è riconosciuto."""
    for m in ADDRESS_RE.finditer(text):
        city, prov = _clean_city(m.group("city"))
        prov = m.group("prov") or prov
        if city and (not prov or prov in _PROVINCES):
            street = clean_text(m.group("street")).rstrip(" ,-")
            return {"address": street, "postal_code": m.group("cap"), "city": city,
                    "province": prov, "country": "Italia"}
    for m in CAP_CITY_RE.finditer(text):
        city, _ = _clean_city(m.group("city"))
        if city and m.group("prov") in _PROVINCES:
            return {"postal_code": m.group("cap"), "city": city,
                    "province": m.group("prov"), "country": "Italia"}
    return {}


def extract_vat(text: str) -> str:
    m = VAT_RE.search(text)
    return m.group(1) if m else ""


def company_name_from_title(title: str, domain: str | None = None) -> str:
    """Nome plausibile dall'<title>: scarta segmenti generici e il dominio."""
    title = clean_text(title)
    if not title:
        return ""
    segments = [s.strip() for s in _TITLE_SPLIT.split(title) if s and s.strip()]
    root = (domain or "").split(".")[0].replace("-", "").lower()
    good = [s for s in segments if s.lower() not in _GENERIC_TITLES
            and not re.fullmatch(r"[\w.-]+\.[a-z]{2,}", s.lower())]
    if not good:
        return ""
    if root:
        for s in good:  # preferisce il segmento che somiglia al dominio
            if root and root[:6] in re.sub(r"[^a-z0-9]", "", s.lower()):
                return s[:120]
    return good[0][:120]


_REGIONS = {
    "Abruzzo": "AQ CH PE TE", "Basilicata": "MT PZ", "Calabria": "CS CZ KR RC VV",
    "Campania": "AV BN CE NA SA", "Emilia-Romagna": "BO FC FE MO PC PR RA RE RN",
    "Friuli-Venezia Giulia": "GO PN TS UD", "Lazio": "FR LT RI RM VT", "Liguria": "GE IM SP SV",
    "Lombardia": "BG BS CO CR LC LO MB MI MN PV SO VA", "Marche": "AN AP FM MC PU",
    "Molise": "CB IS", "Piemonte": "AL AT BI CN NO TO VB VC", "Puglia": "BA BR BT FG LE TA",
    "Sardegna": "CA NU OR SS SU", "Sicilia": "AG CL CT EN ME PA RG SR TP",
    "Toscana": "AR FI GR LI LU MS PI PO PT SI", "Trentino-Alto Adige": "BZ TN",
    "Umbria": "PG TR", "Valle d'Aosta": "AO", "Veneto": "BL PD RO TV VE VI VR",
}
PROVINCE_REGION = {p: region for region, provs in _REGIONS.items() for p in provs.split()}


def region_from_province(prov: str) -> str:
    return PROVINCE_REGION.get((prov or "").upper(), "")
