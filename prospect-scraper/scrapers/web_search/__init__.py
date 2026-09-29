"""Web Search: scoperta di aziende digitali (SaaS, startup, e-commerce, publisher) tramite
API di ricerca web. Indipendente dalla ricerca locale (``scrapers.search``, OSM + Wikidata).

Flusso: ``run_web_search`` -> provider (API) -> ``discovery.discover`` (paginazione, varianti,
filtro portali, dedup per dominio) -> ``WebSearchReport``.

Per aggiungere un provider:
  1. crea ``scrapers/web_search/<nome>.py`` con una sottoclasse di ``WebSearchProvider``
     (``name``, ``label``, ``per_call``, ``max_pages``, ``is_configured``, ``search_page``:
     una sola chiamata API, risultati come ``SearchResult`` con ``source=self.name``);
  2. registrala in ``WEB_PROVIDERS`` qui sotto;
  3. se serve una chiave, aggiungi la voce in ``config/user_settings.py`` e in
     ``_provider_config`` qui sotto (e il campo nell'interfaccia in ``app.py``).
"""

from __future__ import annotations

from config import settings, user_settings
from scrapers.http import HttpClient
from scrapers.web_search.base import WebSearchProvider, WebSearchReport
from scrapers.web_search.brave import BraveProvider
from scrapers.web_search.discovery import discover
from scrapers.web_search.searxng import SearXNGWebProvider
from scrapers.web_search.tavily import TavilyProvider

WEB_PROVIDERS: dict[str, type[WebSearchProvider]] = {
    "tavily": TavilyProvider,
    "brave": BraveProvider,
    "searxng": SearXNGWebProvider,
}

NOT_CONFIGURED_MESSAGE = ("Web Search non configurata: apri «Impostazioni Web Search» nella barra "
                          "laterale e inserisci la chiave API (Tavily è gratuito).")


def _provider_name(name: str | None) -> str:
    chosen = (name or user_settings.get("web_provider", "tavily")).strip().lower()
    return chosen if chosen in WEB_PROVIDERS else "tavily"


def _provider_config(name: str) -> dict:
    if name == "searxng":
        return {"url": user_settings.get("searxng_url")}
    return {"api_key": user_settings.get(f"{name}_api_key")}


def get_provider(name: str | None = None, client: HttpClient | None = None) -> WebSearchProvider:
    """Costruisce il provider (default: quello scelto nelle impostazioni) con chiave/URL salvati."""
    chosen = _provider_name(name)
    return WEB_PROVIDERS[chosen](client, **_provider_config(chosen))


def web_search_status(name: str | None = None) -> tuple[bool, str]:
    """(configurato?, etichetta leggibile del provider)."""
    provider = get_provider(name)
    return provider.is_configured(), provider.label


def run_web_search(keyword: str, location: str, max_results: int, provider_name: str | None = None,
                   client: HttpClient | None = None,
                   provider: WebSearchProvider | None = None) -> WebSearchReport:
    """Esegue la Web Search. Se il provider non è configurato non fa nessuna chiamata."""
    provider = provider or get_provider(provider_name, client)
    if not provider.is_configured():
        return WebSearchReport(provider=provider.name, errors=[NOT_CONFIGURED_MESSAGE])
    return discover(provider, keyword, location, max_results, settings.WEB_MAX_API_CALLS)
