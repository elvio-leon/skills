"""Provider Wikidata (API MediaWiki ufficiale, dati CC0).

Utile per testate, editori, software house e aziende note. Restituisce solo
elementi con sito ufficiale (P856) e non cessati.
"""

from __future__ import annotations

from config import settings
from scrapers.search.base import (SearchProvider, SearchRequest, SearchResult,
                                  leftover_words, remove_phrases)
from scrapers.search.geo import COUNTRIES, get_geocoder, resolve_place
from utils.logging import get_logger

log = get_logger("search.wikidata")

# Parole della keyword -> classi Wikidata (P31)
CLASS_TERMS: dict[tuple[str, ...], list[str]] = {
    ("magazine", "rivista", "riviste", "periodico", "periodici"): ["Q41298"],
    ("giornale", "giornali", "quotidiano", "quotidiani", "newspaper", "testata", "testate"): ["Q11032", "Q1153191"],
    ("giornale online", "testata online", "news", "notizie"): ["Q1153191"],
    ("editore", "editori", "casa editrice", "case editrici", "publisher", "editoria"): ["Q2085381"],
    ("software house", "software", "saas", "sviluppo software"): ["Q1058914"],
    ("hotel", "albergo", "alberghi"): ["Q27686"],
}
CATEGORY_CLASSES = {
    "Editoriale": ["Q41298", "Q11032", "Q1153191", "Q2085381"],
    "Digital / Startup": ["Q1058914"],
    "Hospitality": ["Q27686"],
}
NEUTRAL = ("startup", "start-up", "azienda", "aziende", "company", "companies", "online",
           "italiana", "italiano", "italiane", "italiani", "digital")

SOCIAL_PROPS = {
    "linkedin": ("P4264", "https://www.linkedin.com/company/{}"),
    "instagram": ("P2003", "https://www.instagram.com/{}"),
    "facebook": ("P2013", "https://www.facebook.com/{}"),
    "twitter": ("P2002", "https://x.com/{}"),
    "youtube": ("P2397", "https://www.youtube.com/channel/{}"),
}
_QID_TO_COUNTRY = {qid: name for qid, name in COUNTRIES.values()}


def _claims(entity: dict, pid: str) -> list:
    out = []
    for claim in entity.get("claims", {}).get(pid, []):
        if claim.get("rank") == "deprecated":
            continue
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if value is None:
            continue
        out.append(value["id"] if isinstance(value, dict) and "id" in value else value)
    return out


def _label(entity: dict, kind: str = "labels") -> str:
    values = entity.get(kind) or {}
    for lang in ("it", "en"):
        if lang in values:
            return values[lang].get("value", "")
    return next((v.get("value", "") for v in values.values()), "")


class WikidataProvider(SearchProvider):
    name = "wikidata"
    label = "Wikidata"

    def __init__(self, client=None):
        super().__init__(client)
        self.geocoder = get_geocoder(self.client)

    def build_search(self, request: SearchRequest) -> str | None:
        phrases = {p: qids for terms, qids in CLASS_TERMS.items() for p in terms}
        rest, found = remove_phrases(request.keyword, list(phrases))
        rest, _ = remove_phrases(rest, list(NEUTRAL))
        classes: list[str] = []
        for p in found:
            for q in phrases[p]:
                if q not in classes:
                    classes.append(q)
        if not classes:
            classes = list(CATEGORY_CLASSES.get(request.category, []))
        words = leftover_words(rest)
        place, words = resolve_place(self.geocoder, words, request.location)
        if not words and not classes:
            return None  # ricerca troppo generica
        parts = [" ".join(words), "haswbstatement:P856"]
        if classes:
            parts.append("haswbstatement:" + "|".join(f"P31={q}" for q in classes))
        country_qid = COUNTRIES.get(place.country_code, ("",))[0] if place else ""
        if country_qid:
            parts.append(f"haswbstatement:P17={country_qid}|P495={country_qid}")
        return " ".join(p for p in parts if p)

    def search(self, request: SearchRequest) -> list[SearchResult]:
        srsearch = self.build_search(request)
        if not srsearch:
            log.info("Wikidata: keyword troppo generica, salto")
            return []
        log.info("Wikidata srsearch: %s", srsearch)
        wanted = min(request.max_results * 2, 200)
        ids: list[str] = []
        offset = 0
        while len(ids) < wanted:
            data = self.client.get_json(settings.WIKIDATA_API_URL, params={
                "action": "query", "list": "search", "srsearch": srsearch, "srnamespace": 0,
                "srlimit": min(50, wanted - len(ids)), "sroffset": offset, "format": "json",
            })
            hits = data.get("query", {}).get("search", [])
            ids.extend(h["title"] for h in hits if h.get("title", "").startswith("Q"))
            offset = data.get("continue", {}).get("sroffset")
            if not hits or offset is None:
                break
        entities = self._entities(ids, "labels|descriptions|claims")
        # etichette di sede, classe e paese in un'unica chiamata
        ref_ids = set()
        for ent in entities.values():
            for pid in ("P159", "P131", "P31"):
                ref_ids.update(_claims(ent, pid)[:1])
        labels = {qid: _label(e) for qid, e in self._entities(sorted(ref_ids), "labels").items()}

        results = []
        for qid in ids:
            ent = entities.get(qid)
            if not ent or _claims(ent, "P576") or _claims(ent, "P2669"):
                continue  # cessato/chiuso
            websites = _claims(ent, "P856")
            name = _label(ent)
            if not websites or not name:
                continue
            country = next((_QID_TO_COUNTRY[q] for q in _claims(ent, "P17") + _claims(ent, "P495")
                            if q in _QID_TO_COUNTRY), "")
            hq = next(iter(_claims(ent, "P159") or _claims(ent, "P131")), None)
            kind = next(iter(_claims(ent, "P31")), None)
            extra = {
                "company_name": name,
                "category_detail": labels.get(kind, "") if kind else "",
                "country": country,
                "city": labels.get(hq, "") if hq else "",
                "phone": next(iter(_claims(ent, "P1329")), ""),
                "email": next((e.removeprefix("mailto:") for e in _claims(ent, "P968")), ""),
                "source_url": f"https://www.wikidata.org/wiki/{qid}",
                "wikidata_id": qid,
            }
            for field, (pid, template) in SOCIAL_PROPS.items():
                value = next(iter(_claims(ent, pid)), "")
                if value:
                    extra[field] = template.format(value)
            results.append(SearchResult(title=name, url=websites[0], snippet=_label(ent, "descriptions"),
                                        source=self.name, extra=extra))
            if len(results) >= request.max_results:
                break
        return results

    def _entities(self, ids: list[str], props: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(ids), 50):
            data = self.client.get_json(settings.WIKIDATA_API_URL, params={
                "action": "wbgetentities", "ids": "|".join(ids[i:i + 50]), "props": props,
                "languages": "it|en", "format": "json",
            })
            out.update({k: v for k, v in data.get("entities", {}).items() if "missing" not in v})
        return out
