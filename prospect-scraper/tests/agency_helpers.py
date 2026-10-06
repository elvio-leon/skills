"""Strumenti di test per la qualifica agenzie: client HTTP finto, classificatore finto, provider web finto."""

from __future__ import annotations

from scrapers.http import FetchError, HttpClient, Page
from scrapers.search.base import SearchResult
from scrapers.web_search.base import WebSearchProvider
from qualify.llm import Classifier, ClassifyError, ClassifyResult, _Raw


def analysis(**over) -> dict:
    """Risposta valida del modello (si può sovrascrivere ogni campo)."""
    data = {
        "is_agency": "si", "is_agency_evidence": "agenzia web e SEO",
        "servizi": ["siti_web", "seo"], "servizi_altro": "",
        "seo_level": "accennata", "seo_evidence": "SEO, social media",
        "servizi_ricorrenti": "si", "ricorrenti_evidence": "canone mensile",
        "verticali": ["vino"], "size_signal": "2-5", "size_evidence": "team di 4 persone",
        "note": "Ha realizzato il sito di Cantine Rossi.",
    }
    data.update(over)
    return data


class FakePagesClient(HttpClient):
    """HttpClient senza rete: ``pages[url] = (status, content_type, body)``; registra le GET e le POST."""

    def __init__(self, pages: dict | None = None):
        super().__init__(delay=0, retries=0)
        self.pages = pages or {}
        self.gets: list[str] = []
        self.posts: list[dict] = []
        self.post_responses: list = []          # dict da restituire o eccezione da sollevare, in ordine

    def get(self, url, *, params=None, check_robots=False, **kw):
        self.gets.append(url)
        status, ctype, body = self.pages.get(url, (404, "text/html", ""))
        return Page(url=url, final_url=url, status_code=status, content=body.encode("utf-8"),
                    content_type=ctype)

    def post_json(self, url, payload, *, headers=None, min_interval=None, timeout=None):
        self.posts.append({"url": url, "payload": payload, "headers": headers, "timeout": timeout})
        response = self.post_responses.pop(0) if self.post_responses else {}
        if isinstance(response, Exception):
            raise response
        return response


class FakeClassifier(Classifier):
    """Classificatore finto: ``behaviors[dominio]`` = dict di risposta o eccezione; registra le chiamate."""

    name = "fake"
    label = "Fake"

    def __init__(self, behaviors: dict | None = None, configured: bool = True, model: str = "fake-model"):
        super().__init__("key", model)
        self.behaviors = behaviors or {}
        self.configured = configured
        self.calls: list[tuple[str, str]] = []

    def is_configured(self) -> bool:
        return self.configured

    def _call(self, system, user) -> _Raw:  # non usato: classify è ridefinito
        raise NotImplementedError

    def classify(self, system: str, user: str) -> ClassifyResult:
        self.calls.append((system, user))
        domain = user.splitlines()[0].replace("Dominio:", "").strip()
        behavior = self.behaviors.get(domain, analysis())
        if isinstance(behavior, Exception):
            raise behavior
        return ClassifyResult(behavior, input_tokens=8000, output_tokens=800, latency_s=0.5)


class FakeWebProvider(WebSearchProvider):
    name = "fake"
    label = "Fake"

    def __init__(self, items: list[tuple[str, str]], per_call: int = 20):
        super().__init__(HttpClient(delay=0, retries=0))
        self.items, self.per_call = items, per_call
        self.calls: list[tuple] = []

    def search_page(self, query, count, page, country_code):
        self.calls.append((query, count, page, country_code))
        if page > 0:
            return []
        return [SearchResult(title=t, url=u, snippet=f"snippet {t}", source=self.name,
                             extra={"source_url": u, "rank": i}) for i, (u, t) in enumerate(self.items, 1)]
