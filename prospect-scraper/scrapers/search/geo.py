"""Geocoding delle località tramite Nominatim (OpenStreetMap), con cache in memoria.

Policy Nominatim: max 1 richiesta/secondo, user-agent identificabile, uso moderato.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from config import settings
from scrapers.http import HttpClient
from utils.logging import get_logger

log = get_logger("geo")

# ISO 3166-1 alpha-2 -> (QID Wikidata, nome italiano)
COUNTRIES = {
    "it": ("Q38", "Italia"), "fr": ("Q142", "Francia"), "de": ("Q183", "Germania"),
    "es": ("Q29", "Spagna"), "ch": ("Q39", "Svizzera"), "at": ("Q40", "Austria"),
    "gb": ("Q145", "Regno Unito"), "us": ("Q30", "Stati Uniti"), "pt": ("Q45", "Portogallo"),
    "nl": ("Q55", "Paesi Bassi"), "be": ("Q31", "Belgio"), "gr": ("Q41", "Grecia"),
    "mt": ("Q233", "Malta"), "sm": ("Q238", "San Marino"), "ie": ("Q27", "Irlanda"),
}
COUNTRY_BY_NAME = {
    "italia": "it", "italy": "it", "francia": "fr", "france": "fr", "germania": "de",
    "germany": "de", "spagna": "es", "spain": "es", "svizzera": "ch", "switzerland": "ch",
    "austria": "at", "regno unito": "gb", "uk": "gb", "united kingdom": "gb",
    "stati uniti": "us", "usa": "us", "portogallo": "pt", "portugal": "pt",
    "olanda": "nl", "paesi bassi": "nl", "belgio": "be", "grecia": "gr", "malta": "mt",
    "san marino": "sm", "irlanda": "ie",
}

_PLACE_CLASSES = {"boundary", "place"}


@dataclass
class Place:
    name: str
    osm_type: str        # "relation" | "way" | "node"
    osm_id: int
    lat: float
    lon: float
    country_code: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    level: str = ""      # "country" | "state" | "city" | altro

    @property
    def overpass_area_id(self) -> int | None:
        if self.osm_type == "relation":
            return 3_600_000_000 + self.osm_id
        if self.osm_type == "way":
            return 2_400_000_000 + self.osm_id
        return None


class Geocoder:
    def __init__(self, client: HttpClient):
        self.client = client
        self._cache: dict[tuple, Place | None] = {}
        self._lock = threading.Lock()

    def geocode(self, query: str, country_code: str = "") -> Place | None:
        key = (query.strip().lower(), country_code)
        if not key[0]:
            return None
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        params = {"q": query, "format": "jsonv2", "limit": 3, "addressdetails": 1,
                  "accept-language": "it"}
        if country_code:
            params["countrycodes"] = country_code
        data = self.client.get_json(f"{settings.NOMINATIM_URL}/search", params=params,
                                    min_interval=settings.NOMINATIM_MIN_INTERVAL)
        place = None
        for item in data or []:
            cls = item.get("category") or item.get("class")
            if cls not in _PLACE_CLASSES:
                continue
            addr = item.get("address") or {}
            addresstype = item.get("addresstype") or item.get("type") or ""
            if addresstype == "country":
                level = "country"
            elif addresstype in ("state", "region"):
                level = "state"
            elif addresstype in ("city", "town", "village", "municipality", "hamlet", "suburb"):
                level = "city"
            else:
                level = addresstype
            cc = (addr.get("country_code") or "").lower()
            place = Place(
                name=item.get("name") or query,
                osm_type=item.get("osm_type", ""),
                osm_id=int(item.get("osm_id", 0)),
                lat=float(item.get("lat", 0)),
                lon=float(item.get("lon", 0)),
                country_code=cc,
                country=COUNTRIES.get(cc, ("", addr.get("country", "")))[1] or addr.get("country", ""),
                region="" if level == "country" else addr.get("state", "") or addr.get("region", ""),
                city=(addr.get("city") or addr.get("town") or addr.get("village") or "")
                if level == "city" else "",
                level=level,
            )
            break
        log.info("geocode %r (cc=%s) -> %s", query, country_code, place)
        with self._lock:
            self._cache[key] = place
        return place


def country_code_from_text(text: str) -> str:
    return COUNTRY_BY_NAME.get((text or "").strip().lower(), "")


_PLACE_LEVELS = {"country", "state", "city", "county", "province"}
_geocoders: dict[int, Geocoder] = {}
_geocoders_lock = threading.Lock()


def get_geocoder(client: HttpClient) -> Geocoder:
    """Un geocoder (e una cache) per client HTTP, condiviso tra i provider."""
    with _geocoders_lock:
        geo = _geocoders.get(id(client))
        if geo is None or geo.client is not client:
            geo = _geocoders[id(client)] = Geocoder(client)
        return geo


def resolve_place(geocoder: Geocoder, words: list[str], location: str) -> tuple[Place | None, list[str]]:
    """Località della ricerca: campo Località (o default), ma se tra le parole residue
    della keyword c'è un luogo più specifico ("hotel 4 stelle Palermo") vince quello.
    Restituisce anche le parole residue senza quelle usate come luogo."""
    loc_text = (location or "").strip() or settings.DEFAULT_LOCATION
    base = geocoder.geocode(loc_text)
    cc = (base.country_code if base else "") or country_code_from_text(loc_text)
    words = [w for w in words if w.lower() != loc_text.lower()]
    if words:
        candidates = []
        for cand in (" ".join(words), " ".join(words[-2:]), words[-1], words[0]):
            if cand not in candidates:
                candidates.append(cand)
        for cand in candidates[:3]:
            place = geocoder.geocode(cand, cc)
            if place and place.level in _PLACE_LEVELS:
                used = set(cand.split())
                return place, [w for w in words if w not in used]
    return base, words
