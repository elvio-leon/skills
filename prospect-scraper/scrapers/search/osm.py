"""Provider OpenStreetMap: Nominatim (località) + Overpass API (attività).

Fonte aperta (ODbL) con accesso tramite API pubbliche consentito per uso moderato.
Molti elementi hanno già sito web, telefono, email e indirizzo.
"""

from __future__ import annotations

import re

from config import settings
from scrapers.http import FetchError
from scrapers.search.base import (SearchProvider, SearchRequest, SearchResult,
                                  leftover_words, remove_phrases)
from scrapers.search.geo import Place, get_geocoder, resolve_place
from utils.logging import get_logger

log = get_logger("search.osm")

HOSPITALITY = ['["tourism"~"^(hotel|guest_house|hostel|motel|apartment|chalet)$"]']

# (frasi nella keyword, selettori Overpass, etichetta categoria)
TERMS: list[tuple[tuple[str, ...], list[str], str]] = [
    # Hospitality
    (("boutique hotel", "hotel", "hotels", "albergo", "alberghi", "hôtel"), ['["tourism"="hotel"]'], "hotel"),
    (("resort",), ['["leisure"="resort"]', '["tourism"="hotel"]["name"~"resort",i]'], "resort"),
    (("b&b", "bnb", "bed and breakfast", "bed & breakfast", "affittacamere", "guest house",
      "guesthouse", "locanda", "locande"), ['["tourism"="guest_house"]'], "b&b"),
    (("agriturismo", "agriturismi"), ['["tourism"]["name"~"agritur",i]', '["tourism"="guest_house"]["guest_house"="agritourism"]'], "agriturismo"),
    (("ostello", "ostelli", "hostel"), ['["tourism"="hostel"]'], "ostello"),
    (("campeggio", "campeggi", "camping"), ['["tourism"="camp_site"]'], "campeggio"),
    (("casa vacanze", "case vacanze", "appartamenti", "holiday home"), ['["tourism"="apartment"]'], "casa vacanze"),
    (("motel",), ['["tourism"="motel"]'], "motel"),
    (("struttura ricettiva", "strutture ricettive", "hospitality", "ospitalità", "alloggi"), HOSPITALITY, "struttura ricettiva"),
    (("ristorante", "ristoranti", "restaurant", "trattoria", "trattorie", "osteria", "osterie"), ['["amenity"="restaurant"]'], "ristorante"),
    (("pizzeria", "pizzerie"), ['["amenity"="restaurant"]["cuisine"~"pizza"]'], "pizzeria"),
    (("bar", "caffè", "caffetteria", "cafe", "café"), ['["amenity"~"^(bar|cafe)$"]'], "bar"),
    (("pub",), ['["amenity"="pub"]'], "pub"),
    (("cantina", "cantine", "winery"), ['["craft"="winery"]'], "cantina"),
    (("stabilimento balneare", "lido", "lidi"), ['["leisure"="beach_resort"]'], "lido"),
    # Editoriale
    (("giornale", "giornali", "quotidiano", "quotidiani", "newspaper", "testata", "testate",
      "redazione"), ['["office"="newspaper"]'], "giornale"),
    (("editore", "editori", "casa editrice", "case editrici", "publisher", "editoria"), ['["office"="publisher"]'], "editore"),
    (("magazine", "rivista", "riviste"), ['["office"~"^(newspaper|publisher)$"]'], "editoria"),
    (("libreria", "librerie", "bookshop", "bookstore"), ['["shop"="books"]'], "libreria"),
    (("tipografia", "tipografie"), ['["craft"="printer"]', '["shop"="copyshop"]'], "tipografia"),
    # Digital / Startup
    (("software house", "software", "saas", "informatica", "sviluppo software", "web agency",
      "agenzia web", "digital agency", "startup", "start-up", "tech", "tecnologia", "ict"),
     ['["office"="it"]'], "IT / software"),
    (("agenzia marketing", "marketing agency", "agenzia di comunicazione", "agenzia pubblicitaria",
      "advertising", "comunicazione"), ['["office"="advertising_agency"]'], "agenzia"),
    (("coworking",), ['["amenity"="coworking_space"]', '["office"="coworking"]'], "coworking"),
    (("telecomunicazioni", "telecom"), ['["office"="telecommunication"]'], "telecomunicazioni"),
    (("consulenza", "consulting"), ['["office"="consulting"]'], "consulenza"),
    # Negozi / servizi
    (("arredamento", "mobili", "furniture", "arredo", "design d'interni"),
     ['["shop"="furniture"]', '["shop"="interior_decoration"]'], "arredamento"),
    (("abbigliamento", "moda", "fashion"), ['["shop"~"^(clothes|boutique)$"]'], "abbigliamento"),
    (("gioielleria", "gioiellerie", "gioielli"), ['["shop"="jewelry"]'], "gioielleria"),
    (("enoteca", "enoteche", "vino", "vini"), ['["shop"="wine"]'], "enoteca"),
    (("palestra", "palestre", "gym", "fitness"), ['["leisure"="fitness_centre"]'], "palestra"),
    (("studio legale", "avvocato", "avvocati"), ['["office"="lawyer"]'], "studio legale"),
    (("commercialista", "commercialisti"), ['["office"="accountant"]'], "commercialista"),
    (("architetto", "architetti", "studio di architettura"), ['["office"="architect"]'], "architettura"),
    (("agenzia immobiliare", "immobiliare", "immobiliari", "real estate"), ['["office"="estate_agent"]'], "immobiliare"),
    (("assicurazioni", "assicurazione"), ['["office"="insurance"]'], "assicurazioni"),
    (("dentista", "dentisti", "studio dentistico"), ['["amenity"="dentist"]'], "dentista"),
    (("azienda", "aziende", "impresa", "imprese"), ['["office"="company"]'], "azienda"),
]

CATEGORY_DEFAULTS = {
    "Hospitality": (HOSPITALITY, "struttura ricettiva"),
    "Editoriale": (['["office"~"^(newspaper|publisher)$"]'], "editoria"),
    "Digital / Startup": (['["office"="it"]'], "IT / software"),
}

# Parole senza valore per OSM (canali, non categorie).
NEUTRAL = ("ecommerce", "e-commerce", "online", "shop online", "negozio online", "sito",
           "siti", "italiana", "italiano", "italiane", "italiani", "lusso", "luxury")

_STARS_RE = re.compile(r"\b([1-5])\s*(?:stelle|stella|stars?|\*|★)", re.I)
WEBSITE_KEYS = ("website", "contact:website", "url")


GROUPS = {
    "Hospitality": {"hotel", "resort", "b&b", "agriturismo", "ostello", "campeggio", "casa vacanze",
                    "motel", "struttura ricettiva", "ristorante", "pizzeria", "bar", "pub",
                    "cantina", "lido"},
    "Editoriale": {"giornale", "editore", "editoria", "libreria", "tipografia"},
    "Digital / Startup": {"IT / software", "agenzia", "coworking", "telecomunicazioni", "consulenza"},
}


def _group_of(label: str) -> str:
    return next((g for g, labels in GROUPS.items() if label in labels), "Altro")


def _all_phrases() -> dict[str, tuple[list[str], str]]:
    out = {}
    for phrases, selectors, label in TERMS:
        for p in phrases:
            out.setdefault(p, (selectors, label))
    return out


_PHRASES = _all_phrases()


def parse_keyword(keyword: str, category: str = ""):
    """-> (selectors, labels, stars, parole residue).

    Se la keyword contiene termini di gruppi diversi ("magazine tecnologia") vale il
    gruppo della categoria scelta, altrimenti quello del primo termine (in italiano
    il nome principale viene prima: "magazine" e non "tecnologia").
    """
    text = keyword or ""
    stars = None
    m = _STARS_RE.search(text)
    if m:
        stars = m.group(1)
        text = _STARS_RE.sub(" ", text)
    low = f" {text.lower()} "
    _, found = remove_phrases(text, list(_PHRASES))
    found.sort(key=lambda ph: low.find(ph))
    groups = [_group_of(_PHRASES[ph][1]) for ph in found]
    if category in groups:
        keep = category
    else:
        keep = groups[0] if groups else None
    selectors, labels, used = [], [], []
    for phrase, group in zip(found, groups):
        sels, label = _PHRASES[phrase]
        if group != keep:
            continue  # termine di un altro gruppo: resta come parola libera
        used.append(phrase)
        for s in sels:
            if s not in selectors:
                selectors.append(s)
        if label not in labels:
            labels.append(label)
    rest, _ = remove_phrases(text, used + list(NEUTRAL))
    return selectors, labels, stars, leftover_words(rest)


def _escape_regex(text: str) -> str:
    return re.sub(r'([\\.^$|?*+()\[\]{}"])', r"\\\1", text)


class OSMProvider(SearchProvider):
    name = "osm"
    label = "OpenStreetMap"

    def __init__(self, client=None):
        super().__init__(client)
        self.geocoder = get_geocoder(self.client)

    # --- query ------------------------------------------------------------
    def build_query(self, selectors: list[str], place: Place, stars: str | None, limit: int) -> str:
        if place.overpass_area_id:
            header = f"area(id:{place.overpass_area_id})->.a;\n"
            scope = "(area.a)"
        else:
            header = ""
            scope = f"(around:15000,{place.lat},{place.lon})"
        star_filter = f'["stars"~"^{stars}"]' if stars else ""
        body = "\n".join(f"  nwr{sel}{star_filter}{scope};" for sel in selectors)
        web = '[~"^(website|contact:website|url)$"~"."]'
        return (
            f"[out:json][timeout:{settings.OVERPASS_TIMEOUT}];\n{header}"
            f"(\n{body}\n)->.all;\n"
            f"nwr.all{web}->.w;\n"
            f".w out tags center {limit};\n"
            f"(.all; - .w;)->.nw;\n"
            f".nw out tags center {limit};\n"
        )

    def search(self, request: SearchRequest) -> list[SearchResult]:
        selectors, labels, stars, words = parse_keyword(request.keyword, request.category)
        place, words = resolve_place(self.geocoder, words, request.location)
        if place is None:
            raise FetchError(f"località non trovata: {request.location or settings.DEFAULT_LOCATION}")
        if not selectors:
            default = CATEGORY_DEFAULTS.get(request.category)
            if default and not words:
                selectors, labels = list(default[0]), [default[1]]
            elif words:
                # Nessuna categoria riconosciuta: cerca per nome tra le attività con sito.
                rx = _escape_regex(" ".join(words))
                selectors = [f'["name"~"{rx}",i][~"^(website|contact:website)$"~"."]']
                labels = [" ".join(words)]
            elif default:
                selectors, labels = list(default[0]), [default[1]]
            else:
                log.info("OSM: nessun criterio utilizzabile per %r", request.keyword)
                return []
        limit = min(max(request.max_results * 2, 40), 400)
        query = self.build_query(selectors, place, stars, limit)
        log.info("Overpass query:\n%s", query)
        data = self._overpass(query)
        results = []
        for el in data.get("elements", []):
            r = self._to_result(el, place, labels)
            if r:
                results.append(r)
        results.sort(key=lambda r: 0 if r.url else 1)
        return results[: request.max_results]

    def _overpass(self, query: str) -> dict:
        """Esegue la query sul server principale; se è sovraccarico (504, 429, timeout)
        prova i server alternativi con gli stessi dati."""
        last_error: Exception | None = None
        for url in [settings.OVERPASS_URL, *settings.OVERPASS_MIRRORS]:
            try:
                data = self.client.get_json(url, data={"data": query},
                                            timeout=settings.OVERPASS_TIMEOUT + 15, min_interval=2)
            except Exception as exc:  # noqa: BLE001 - si prova il server successivo
                log.warning("Overpass %s non disponibile: %s", url, exc)
                last_error = exc
                continue
            if data.get("remark") and not data.get("elements"):
                log.warning("Overpass %s: %s", url, data["remark"][:200])
                last_error = FetchError(f"Overpass: {data['remark'][:120]}")
                continue
            return data
        raise last_error or FetchError("Overpass non disponibile")

    def _to_result(self, el: dict, place: Place, labels: list[str]) -> SearchResult | None:
        tags = el.get("tags") or {}
        name = tags.get("name") or tags.get("brand")
        if not name:
            return None
        website = next((tags[k] for k in WEBSITE_KEYS if tags.get(k)), "")
        kind = (tags.get("tourism") or tags.get("office") or tags.get("shop")
                or tags.get("amenity") or tags.get("craft") or tags.get("leisure") or "")
        street = " ".join(filter(None, [tags.get("addr:street"), tags.get("addr:housenumber")]))
        city = tags.get("addr:city") or place.city
        address = ", ".join(filter(None, [street, " ".join(filter(None, [tags.get("addr:postcode"), city]))]))
        osm_url = f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}"
        snippet = " · ".join(filter(None, [
            kind.replace("_", " "),
            f"{tags['stars']}★" if tags.get("stars") else "",
            address,
        ]))
        extra = {
            "company_name": name,
            "category_detail": kind or (labels[0] if labels else ""),
            "phone": tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile") or "",
            "email": tags.get("email") or tags.get("contact:email") or "",
            "city": city,
            "address": address,
            "postal_code": tags.get("addr:postcode", ""),
            "country": place.country,
            "region": place.region,
            "facebook": tags.get("contact:facebook") or tags.get("facebook") or "",
            "instagram": tags.get("contact:instagram") or tags.get("instagram") or "",
            "linkedin": tags.get("contact:linkedin") or "",
            "source_url": osm_url,
            "osm": {k: v for k, v in tags.items() if not k.startswith("name:")},
        }
        return SearchResult(title=name, url=website, snippet=snippet, source=self.name, extra=extra)
