"""Interfaccia comune dei provider di Web Search (API di ricerca web)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from scrapers.http import HttpClient, default_client
from scrapers.search.base import SearchResult

# codice ISO2 -> nome inglese del paese (per le API che lo richiedono)
COUNTRY_NAMES_EN = {
    "it": "italy", "fr": "france", "de": "germany", "es": "spain", "ch": "switzerland",
    "at": "austria", "gb": "united kingdom", "us": "united states", "pt": "portugal",
    "nl": "netherlands", "be": "belgium",
}


@dataclass
class WebSearchReport:
    """Esito di una scoperta web: risultati unici per dominio + diagnostica."""

    results: list[SearchResult] = field(default_factory=list)
    raw_count: int = 0                                   # risultati grezzi prima dei filtri
    api_calls: int = 0                                   # chiamate API effettuate (= crediti)
    queries: list[str] = field(default_factory=list)     # query esatte inviate
    errors: list[str] = field(default_factory=list)
    provider: str = ""
    filtered: int = 0                                    # risultati scartati dal filtro extra (blacklist)


class WebSearchProvider(ABC):
    """Un provider = una API di ricerca web. Vedi ``scrapers.web_search`` per come aggiungerne uno."""

    name: str = "base"
    label: str = "Base"
    per_call: int = 10       # massimo di risultati per singola chiamata API
    max_pages: int = 1       # pagine supportate dall'API (1 = nessuna paginazione)

    def __init__(self, client: HttpClient | None = None, **config):
        self.client = client or default_client()
        self.config = config

    def is_configured(self) -> bool:
        return True

    @abstractmethod
    def search_page(self, query: str, count: int, page: int, country_code: str) -> list[SearchResult]:
        """Esattamente UNA chiamata API. ``page`` parte da 0. Solleva in caso di errore."""
