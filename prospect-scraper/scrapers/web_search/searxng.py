"""SearXNG per la Web Search: metaricerca su un'istanza propria (richiede Docker e il
formato JSON abilitato). Indipendente dal provider della ricerca locale."""

from __future__ import annotations

from scrapers.http import HttpClient
from scrapers.search.base import SearchResult
from scrapers.web_search.base import WebSearchProvider


class SearXNGWebProvider(WebSearchProvider):
    name = "searxng"
    label = "SearXNG"
    per_call = 10
    max_pages = 5

    def __init__(self, client: HttpClient | None = None, **config):
        super().__init__(client, **config)
        self.url = (config.get("url") or "").strip().rstrip("/")

    def is_configured(self) -> bool:
        return bool(self.url)

    def search_page(self, query: str, count: int, page: int, country_code: str) -> list[SearchResult]:
        params: dict = {"q": query, "format": "json", "pageno": page + 1}
        if (country_code or "").lower() == "it":
            params["language"] = "it-IT"
        data = self.client.get_json(f"{self.url}/search", params=params)
        out = []
        for i, item in enumerate((data or {}).get("results") or [], start=1):
            url = (item.get("url") or "").strip()
            if not url:
                continue
            out.append(SearchResult(title=(item.get("title") or "").strip(), url=url,
                                    snippet=(item.get("content") or "").strip(), source=self.name,
                                    extra={"source_url": url, "rank": page * self.per_call + i}))
        return out[:count]
