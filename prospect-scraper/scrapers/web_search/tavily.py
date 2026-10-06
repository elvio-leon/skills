"""Tavily: API di ricerca pensata per applicazioni AI. Piano gratuito: 1000 crediti/mese,
senza carta di credito (https://app.tavily.com). Una ricerca "basic" costa 1 credito."""

from __future__ import annotations

from config import settings
from scrapers.http import HttpClient
from scrapers.search.base import SearchResult
from scrapers.web_search.base import COUNTRY_NAMES_EN, WebSearchProvider

MAX_EXCLUDED = 50   # limite ragionevole di exclude_domains inviati all'API (il resto lo filtra discovery)


class TavilyProvider(WebSearchProvider):
    name = "tavily"
    label = "Tavily"
    per_call = 20
    max_pages = 1     # niente paginazione: altri risultati si ottengono con varianti della query

    def __init__(self, client: HttpClient | None = None, **config):
        super().__init__(client, **config)
        self.api_key = (config.get("api_key") or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def search_page(self, query: str, count: int, page: int, country_code: str) -> list[SearchResult]:
        payload: dict = {
            "query": query,
            "max_results": max(1, min(count, self.per_call)),
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "exclude_domains": sorted(settings.WEB_EXCLUDED_DOMAINS)[:MAX_EXCLUDED],
        }
        country = COUNTRY_NAMES_EN.get((country_code or "").lower())
        if country:
            payload["country"] = country
        data = self.client.post_json(settings.TAVILY_API_URL, payload,
                                     headers={"Authorization": f"Bearer {self.api_key}"})
        out = []
        for i, item in enumerate((data or {}).get("results") or [], start=1):
            url = (item.get("url") or "").strip()
            if not url:
                continue
            out.append(SearchResult(title=(item.get("title") or "").strip(), url=url,
                                    snippet=(item.get("content") or "").strip(), source=self.name,
                                    extra={"source_url": url, "rank": page * self.per_call + i}))
        return out

    def search_profiles(self, query: str, count: int = 5, domain: str = "linkedin.com") -> list[SearchResult]:
        # qui i domini esclusi dalla Web Search (fra cui linkedin.com) non vanno inviati
        payload = {"query": query, "max_results": max(1, min(count, self.per_call)),
                   "search_depth": "basic", "include_answer": False, "include_raw_content": False,
                   "include_images": False, "include_domains": [domain]}
        data = self.client.post_json(settings.TAVILY_API_URL, payload,
                                     headers={"Authorization": f"Bearer {self.api_key}"})
        return [SearchResult(title=(item.get("title") or "").strip(), url=(item.get("url") or "").strip(),
                             snippet="", source=self.name, extra={"rank": i})
                for i, item in enumerate((data or {}).get("results") or [], start=1) if item.get("url")]
