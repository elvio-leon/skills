"""Client HTTP finto per testare i provider senza rete."""

from scrapers.http import FetchError, HttpClient

NOMINATIM = {
    "italia": [{"osm_type": "relation", "osm_id": 365331, "lat": "42.6", "lon": "12.6",
                "category": "boundary", "type": "administrative", "addresstype": "country",
                "name": "Italia", "address": {"country": "Italia", "country_code": "it"}}],
    "palermo": [{"osm_type": "relation", "osm_id": 39150, "lat": "38.11", "lon": "13.35",
                 "category": "boundary", "type": "administrative", "addresstype": "city",
                 "name": "Palermo", "address": {"city": "Palermo", "state": "Sicilia",
                                                "country": "Italia", "country_code": "it"}}],
    "sicilia": [{"osm_type": "relation", "osm_id": 39152, "lat": "37.5", "lon": "14.1",
                 "category": "boundary", "type": "administrative", "addresstype": "state",
                 "name": "Sicilia", "address": {"state": "Sicilia", "country": "Italia",
                                                "country_code": "it"}}],
    # "boutique" trova un negozio, non un luogo: deve essere ignorato
    "boutique": [{"osm_type": "node", "osm_id": 1, "lat": "0", "lon": "0", "category": "shop",
                  "type": "boutique", "addresstype": "shop", "name": "Boutique",
                  "address": {"country_code": "it"}}],
}

OVERPASS = {"elements": [
    {"type": "node", "id": 101, "lat": 38.1, "lon": 13.3, "tags": {
        "name": "Grand Hotel Alfa", "tourism": "hotel", "stars": "4",
        "website": "https://www.hotelalfa.it/", "phone": "+39 091 123 4567",
        "addr:street": "Via Roma", "addr:housenumber": "10", "addr:postcode": "90133",
        "addr:city": "Palermo", "email": "info@hotelalfa.it"}},
    {"type": "way", "id": 202, "center": {"lat": 38.1, "lon": 13.3}, "tags": {
        "name": "Hotel Beta", "tourism": "hotel", "contact:website": "http://hotelbeta.it"}},
    {"type": "node", "id": 303, "tags": {"name": "Hotel Senza Sito", "tourism": "hotel",
                                          "phone": "091 765 4321"}},
    {"type": "node", "id": 404, "tags": {"tourism": "hotel"}},  # senza nome: scartato
    {"type": "node", "id": 505, "tags": {"name": "Hotel Social", "tourism": "hotel",
                                          "website": "https://www.facebook.com/hotelsocial"}},
]}

WD_SEARCH = {"query": {"search": [{"title": "Q1001"}, {"title": "Q1002"}, {"title": "Q1003"}]}}
WD_ENTITIES = {"entities": {
    "Q1001": {"labels": {"it": {"value": "Tech Magazine Italia"}},
              "descriptions": {"it": {"value": "rivista italiana di tecnologia"}},
              "claims": {
                  "P856": [{"rank": "normal", "mainsnak": {"datavalue": {"value": "https://www.techmag.it/"}}}],
                  "P17": [{"rank": "normal", "mainsnak": {"datavalue": {"value": {"id": "Q38"}}}}],
                  "P159": [{"rank": "normal", "mainsnak": {"datavalue": {"value": {"id": "Q490"}}}}],
                  "P31": [{"rank": "normal", "mainsnak": {"datavalue": {"value": {"id": "Q41298"}}}}],
                  "P2003": [{"rank": "normal", "mainsnak": {"datavalue": {"value": "techmagit"}}}],
              }},
    "Q1002": {"labels": {"it": {"value": "Rivista Chiusa"}}, "claims": {
        "P856": [{"rank": "normal", "mainsnak": {"datavalue": {"value": "https://chiusa.it"}}}],
        "P576": [{"rank": "normal", "mainsnak": {"datavalue": {"value": {"time": "+2010"}}}}]}},
    "Q1003": {"labels": {"en": {"value": "No Website Mag"}}, "claims": {}},
}}
WD_LABELS = {"entities": {"Q490": {"labels": {"it": {"value": "Milano"}}},
                          "Q41298": {"labels": {"it": {"value": "rivista"}}}}}

SEARX = {"results": [
    {"url": "https://www.hotelgamma.it/camere", "title": "Camere - Hotel Gamma | Palermo", "content": "..."},
    {"url": "https://www.booking.com/hotel/it/x.html", "title": "Booking", "content": ""},
    {"url": "https://hotelgamma.it/", "title": "Hotel Gamma", "content": "dup"},
    {"url": "https://blog.example.org/migliori-hotel", "title": "I 10 migliori hotel", "content": ""},
]}


class FakeClient(HttpClient):
    def __init__(self, fail: set[str] | None = None):
        super().__init__(delay=0, retries=0)
        self.calls: list[tuple] = []
        self.fail = fail or set()

    def get_json(self, url, *, params=None, data=None, min_interval=None, timeout=None):
        self.calls.append((url, params, data))
        for key in self.fail:
            if key in url:
                raise FetchError(f"timeout simulato su {key}")
        if "nominatim" in url:
            return NOMINATIM.get(params["q"].lower(), [])
        if "overpass" in url:
            return OVERPASS
        if "wikidata" in url:
            if params.get("list") == "search":
                return WD_SEARCH
            if params.get("props") == "labels":
                return WD_LABELS
            return WD_ENTITIES
        if "searx" in url:
            return SEARX if params["pageno"] == 1 else {"results": []}
        raise AssertionError(f"URL inatteso {url}")
