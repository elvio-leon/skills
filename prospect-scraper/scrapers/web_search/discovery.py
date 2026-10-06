"""Scoperta di aziende via Web Search: query -> paginazione/varianti -> filtro dei portali
-> un solo risultato per dominio registrabile. Non solleva mai: gli errori finiscono nel report."""

from __future__ import annotations

from typing import Callable

from config import settings
from scrapers.http import describe_exception
from scrapers.search.base import SearchResult
from scrapers.search.geo import country_code_from_text
from scrapers.web_search.base import WebSearchProvider, WebSearchReport
from utils.logging import get_logger
from utils.normalization import is_domain_in, normalize_domain, registrable_domain

log = get_logger("web_search")

QUERY_VARIANTS = (" azienda", " sito ufficiale", " company")
_STOP_MARKERS = ("401", "403", "429")   # chiave non valida / limite raggiunto: inutile riprovare


def build_query(keyword: str, location: str) -> tuple[str, str]:
    """Restituisce (query base, codice paese). Il luogo entra nel testo della query."""
    keyword = (keyword or "").strip()
    location = (location or "").strip() or settings.DEFAULT_LOCATION
    country = country_code_from_text(location) or "it"
    query = keyword
    if location and location.lower() not in keyword.lower():
        query = f"{keyword} {location}".strip()
    return query, country


ExtraFilter = Callable[[SearchResult], "str | None"]   # motivo dello scarto, o None se il risultato va tenuto


def is_excluded(url: str) -> bool:
    """True se l'URL è un portale/directory/social e non il sito di un'azienda."""
    excluded = settings.NON_COMPANY_DOMAINS | settings.WEB_EXCLUDED_DOMAINS
    host = normalize_domain(url)
    reg = registrable_domain(url)
    return is_domain_in(reg, excluded) or is_domain_in(host, excluded)


def _stops_run(message: str) -> bool:
    return any(marker in message for marker in _STOP_MARKERS)


class _Collector:
    """Raccoglie i risultati unici per dominio registrabile, in ordine di ranking."""

    def __init__(self, extra_filter: ExtraFilter | None = None) -> None:
        self.by_domain: dict[str, SearchResult] = {}
        self.raw_count = 0
        self.extra_filter = extra_filter
        self.filtered_urls: set[str] = set()   # risultati scartati dal filtro extra (senza doppioni)

    def add(self, results: list[SearchResult], query: str) -> int:
        """Aggiunge i risultati di una chiamata; restituisce quanti domini nuovi."""
        self.raw_count += len(results)
        new = 0
        for r in results:
            domain = registrable_domain(r.url)
            if not domain:
                continue
            if self.extra_filter is not None and self.extra_filter(r):
                self.filtered_urls.add(r.url)      # scartato PRIMA di contare per max_results
                continue
            if is_excluded(r.url):
                continue
            kept = self.by_domain.get(domain)
            if kept is None:
                r.extra = {**(r.extra or {}), "query": query}
                self.by_domain[domain] = r
                new += 1
            elif r.url != kept.url:
                others = kept.extra.setdefault("other_urls", [])
                if r.url not in others:
                    others.append(r.url)
        return new


def discover(provider: WebSearchProvider, keyword: str, location: str, max_results: int,
             max_calls: int | None = None, extra_filter: ExtraFilter | None = None) -> WebSearchReport:
    """Cerca aziende sul web con ``provider`` e restituisce al più ``max_results`` domini unici.

    ``extra_filter`` (facoltativo, es. la blacklist delle agenzie) riceve ogni risultato e
    restituisce il motivo dello scarto oppure None: i risultati scartati non contano per
    ``max_results`` e la paginazione continua."""
    max_calls = settings.WEB_MAX_API_CALLS if max_calls is None else max_calls
    base, country = build_query(keyword, location)
    report = WebSearchReport(provider=provider.name)
    found = _Collector(extra_filter)

    # 1) pagine della query base, 2) varianti della query (una chiamata ciascuna)
    steps: list[tuple[str, int, bool]] = [(base, p, False) for p in range(max(1, provider.max_pages))]
    steps += [(base + v, 0, True) for v in QUERY_VARIANTS]

    skip_pages = False
    for query, page, is_variant in steps:
        if len(found.by_domain) >= max_results or report.api_calls >= max_calls:
            break
        if skip_pages and not is_variant:
            continue
        report.api_calls += 1
        if query not in report.queries:
            report.queries.append(query)
        try:
            results = provider.search_page(query, provider.per_call, page, country)
        except Exception as exc:  # noqa: BLE001 - la ricerca non deve mai far fallire l'app
            message = describe_exception(exc)
            log.warning("web search %s: %s", provider.name, message)
            if message not in report.errors:
                report.errors.append(message)
            if _stops_run(message):
                break
            skip_pages = True          # la paginazione è compromessa: prova le varianti
            continue
        filtered_before = len(found.filtered_urls)
        new = found.add(results, query)
        if new == 0 and len(found.filtered_urls) == filtered_before:   # nessun risultato utile né scartato
            if is_variant:
                break
            skip_pages = True          # pagina esaurita: passa alle varianti

    report.raw_count = found.raw_count
    report.filtered = len(found.filtered_urls)
    report.results = list(found.by_domain.values())[:max(0, max_results)]
    return report
