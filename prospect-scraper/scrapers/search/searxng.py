"""Provider SearXNG (opzionale): ricerca web generica tramite un'istanza SearXNG propria.

Richiede ``PS_SEARXNG_URL`` (es. http://localhost:8888) e il formato JSON abilitato
nelle impostazioni dell'istanza (``search.formats: [html, json]``).
"""

from __future__ import annotations

from config import settings
from scrapers.search.base import SearchProvider, SearchRequest, SearchResult
from scrapers.search.geo import country_code_from_text
from utils.logging import get_logger
from utils.normalization import is_domain_in, normalize_domain

log = get_logger("search.searxng")


class SearXNGProvider(SearchProvider):
    name = "searxng"
    label = "Web (SearXNG)"

    def __init__(self, client=None, base_url: str | None = None):
        super().__init__(client)
        self.base_url = (base_url if base_url is not None else settings.SEARXNG_URL).rstrip("/")

    def is_available(self) -> bool:
        return bool(self.base_url)

    def search(self, request: SearchRequest) -> list[SearchResult]:
        query = request.keyword
        loc = (request.location or "").strip()
        if loc and loc.lower() not in query.lower():
            query = f"{query} {loc}"
        cc = country_code_from_text(loc) or ("it" if not loc else "")
        results: list[SearchResult] = []
        seen: set[str] = set()
        for page in range(1, 6):
            params = {"q": query, "format": "json", "pageno": page, "safesearch": 1}
            if cc == "it" or not loc:
                params["language"] = "it-IT"
            data = self.client.get_json(f"{self.base_url}/search", params=params, min_interval=1.5)
            items = data.get("results", [])
            if not items:
                break
            for item in items:
                url = item.get("url", "")
                domain = normalize_domain(url)
                if not domain or domain in seen or is_domain_in(domain, settings.NON_COMPANY_DOMAINS):
                    continue
                seen.add(domain)
                results.append(SearchResult(
                    title=item.get("title", ""), url=url, snippet=item.get("content", ""),
                    source=self.name, extra={"source_url": url, "engine": item.get("engine", "")},
                ))
                if len(results) >= request.max_results:
                    return results
        return results
