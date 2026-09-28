"""Motore di ricerca modulare.

Interfaccia principale::

    search(query, max_results, location=..., category=...) -> list[dict]

Ogni risultato: ``{"title", "url", "snippet", "source", "extra"}``.
Per aggiungere una fonte: creare una sottoclasse di ``SearchProvider`` e
registrarla in ``PROVIDERS``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scrapers.http import HttpClient, default_client, describe_exception
from scrapers.search.base import SearchProvider, SearchRequest, SearchResult
from scrapers.search.osm import OSMProvider
from scrapers.search.searxng import SearXNGProvider
from scrapers.search.wikidata import WikidataProvider
from utils.logging import get_logger

log = get_logger("search")

PROVIDERS: dict[str, type[SearchProvider]] = {
    OSMProvider.name: OSMProvider,
    WikidataProvider.name: WikidataProvider,
    SearXNGProvider.name: SearXNGProvider,
}

# Fonti predefinite per tipo di ricerca (quelle non disponibili vengono saltate).
CATEGORY_PROVIDERS = {
    "Hospitality": ["osm", "searxng"],
    "Editoriale": ["wikidata", "osm", "searxng"],
    "Digital / Startup": ["wikidata", "osm", "searxng"],
    "Custom": ["osm", "wikidata", "searxng"],
}


@dataclass
class SearchReport:
    results: list[SearchResult] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)       # provider -> messaggio
    counts: dict[str, int] = field(default_factory=dict)       # provider -> n risultati


def available_providers(client: HttpClient | None = None) -> dict[str, SearchProvider]:
    client = client or default_client()
    out = {}
    for name, cls in PROVIDERS.items():
        provider = cls(client)
        if provider.is_available():
            out[name] = provider
    return out


def default_provider_names(category: str, client: HttpClient | None = None) -> list[str]:
    avail = available_providers(client)
    return [p for p in CATEGORY_PROVIDERS.get(category, CATEGORY_PROVIDERS["Custom"]) if p in avail]


def run_search(request: SearchRequest, provider_names: list[str] | None = None,
               client: HttpClient | None = None) -> SearchReport:
    """Interroga i provider scelti; l'errore di un provider non blocca gli altri."""
    avail = available_providers(client)
    names = provider_names or default_provider_names(request.category, client)
    report = SearchReport()
    for name in names:
        provider = avail.get(name)
        if provider is None:
            report.errors[name] = "provider non disponibile/configurato"
            continue
        try:
            found = provider.search(request)
        except Exception as exc:  # noqa: BLE001 - un provider non deve fermare la ricerca
            log.exception("provider %s fallito", name)
            report.errors[name] = describe_exception(exc)
            continue
        report.counts[name] = len(found)
        report.results.extend(found)
    return report


def search(query: str, max_results: int = 20, *, location: str = "", category: str = "Custom",
           providers: list[str] | None = None, client: HttpClient | None = None) -> list[dict]:
    """Interfaccia semplice: restituisce una lista di dict normalizzati."""
    request = SearchRequest(keyword=query, location=location, category=category, max_results=max_results)
    return [r.to_dict() for r in run_search(request, providers, client).results]


__all__ = ["search", "run_search", "SearchRequest", "SearchResult", "SearchProvider",
           "SearchReport", "PROVIDERS", "CATEGORY_PROVIDERS", "available_providers",
           "default_provider_names"]
