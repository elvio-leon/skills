"""Brave Search API: 5$ di credito gratuito al mese (circa 1000 ricerche), richiede una carta
di credito (https://api-dashboard.search.brave.com)."""

from __future__ import annotations

from config import settings
from scrapers.http import HttpClient
from scrapers.search.base import SearchResult
from scrapers.web_search.base import COUNTRY_NAMES_EN, WebSearchProvider


class BraveProvider(WebSearchProvider):
    name = "brave"
    label = "Brave Search"
    per_call = 20
    max_pages = 5

    def __init__(self, client: HttpClient | None = None, **config):
        super().__init__(client, **config)
        self.api_key = (config.get("api_key") or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_page(self, query: str, count: int, page: int, country_code: str) -> list[SearchResult]:
        params: dict = {"q": query, "count": max(1, min(count, self.per_call)),
                        "offset": max(0, min(page, 9))}
        code = (country_code or "").lower()
        if code in COUNTRY_NAMES_EN:
            params["country"] = code.upper()
        if code == "it":
            params["search_lang"] = "it"
        data = self.client.get_json(settings.BRAVE_API_URL, params=params,
                                    headers={"X-Subscription-Token": self.api_key,
                                             "Accept": "application/json"})
        items = ((data or {}).get("web") or {}).get("results") or []
        out = []
        for i, item in enumerate(items, start=1):
            url = (item.get("url") or "").strip()
            if not url:
                continue
            out.append(SearchResult(title=(item.get("title") or "").strip(), url=url,
                                    snippet=(item.get("description") or "").strip(), source=self.name,
                                    extra={"source_url": url, "rank": page * self.per_call + i}))
        return out
