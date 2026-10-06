"""Testi del sito per la qualifica: home + al più una pagina per gruppo (servizi, chi siamo,
portfolio) + stato del blog. Riusa i testi già raccolti dall'enrichment; le pagine mancanti
si scaricano con ``HttpClient.get(url, check_robots=True)`` (solo stesso sito, mai linkedin.com)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit

import requests

from qualify.blog import BlogInfo, HomeData, detect_blog
from scrapers.http import HttpClient, describe_exception, status_error
from scrapers.website import (_SKIP_EXT, EnrichmentResult, _canonical, _same_site, page_text_entry,
                              parse_page)
from utils.logging import get_logger
from utils.normalization import homepage_url, is_domain_in, normalize_domain

log = get_logger("qualify.pages")

PAGE_CHAR_CAP = 6000
TOTAL_CHAR_CAP = 20000
MAX_EXTRA_PAGES = 3
NEVER_FETCH = {"linkedin.com"}

# gruppo -> parole chiave (nell'ordine di priorità dei gruppi)
GROUPS: dict[str, tuple[str, ...]] = {
    "servizi": ("servizi", "services", "service", "cosa-facciamo", "cosa facciamo", "soluzioni",
                "solutions", "what-we-do", "competenze", "expertise"),
    "chi_siamo": ("chi-siamo", "chi siamo", "about", "team", "agenzia", "persone", "people",
                  "staff", "studio", "la-nostra-storia"),
    "portfolio": ("portfolio", "lavori", "progetti", "works", "work", "case-history",
                  "case history", "casi-studio", "casi studio", "case-study", "clienti", "clients",
                  "referenze"),
}
_BLOG_FIRST_SEGMENTS = {"blog", "news", "notizie", "articoli", "magazine", "journal", "insights",
                        "approfondimenti"}


@dataclass
class PageText:
    kind: str                 # home | servizi | chi_siamo | portfolio
    url: str
    title: str
    text: str
    truncated: bool = False


@dataclass
class SiteContent:
    domain: str
    home_url: str
    pages: list[PageText] = field(default_factory=list)
    blog: BlogInfo = field(default_factory=BlogInfo)
    errors: list[str] = field(default_factory=list)
    fetched: int = 0           # richieste HTTP effettuate (esclusi i testi riusati dall'enrichment)
    error: str = ""            # valorizzato se la home non è ottenibile: il sito va marcato fallito

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.pages)


def _words(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()) + " "


def _matches(keywords: tuple[str, ...], url: str, anchor: str) -> bool:
    hay = _words(f"{urlsplit(url).path} {anchor}")
    return any(_words(k) in hay for k in keywords)


def _depth(url: str) -> int:
    return len([s for s in urlsplit(url).path.split("/") if s])


def select_pages(links: list[tuple[str, str]], site_domain: str, home_url: str) -> dict[str, str]:
    """Un URL per gruppo (max 3), dal link meno profondo che contiene una parola chiave."""
    home_key = _canonical(home_url)
    candidates: list[tuple[str, str]] = []
    for url, anchor in links:
        url = url.split("#")[0]
        parts = urlsplit(url)
        if (parts.scheme not in ("http", "https") or _SKIP_EXT.search(parts.path)
                or not _same_site(url, site_domain)
                or is_domain_in(normalize_domain(url), NEVER_FETCH)
                or _canonical(url) == home_key):
            continue
        first = next((s for s in parts.path.lower().split("/") if s), "")
        if first in _BLOG_FIRST_SEGMENTS:       # gli articoli del blog non descrivono l'agenzia
            continue
        candidates.append((url, anchor))
    chosen: dict[str, str] = {}
    used: set[str] = set()
    for kind, keywords in GROUPS.items():
        if len(chosen) >= MAX_EXTRA_PAGES:
            break
        hits = [(_depth(u), i, u) for i, (u, a) in enumerate(candidates)
                if _canonical(u) not in used and _matches(keywords, u, a)]
        if hits:
            url = min(hits)[2]
            chosen[kind] = url
            used.add(_canonical(url))
    return chosen


def _fetch(client: HttpClient, url: str):
    """GET con robots.txt; se il certificato HTTPS non è valido riprova in http (come l'enrichment)."""
    try:
        return client.get(url, check_robots=True)
    except requests.exceptions.SSLError:
        if url.startswith("https://"):
            return client.get("http://" + url[len("https://"):], check_robots=True)
        raise


def _cap(text: str, limit: int) -> tuple[str, bool]:
    return (text, False) if len(text) <= limit else (text[:limit].rstrip(), True)


class _Budget:
    def __init__(self, seconds: float) -> None:
        self.start, self.seconds = time.monotonic(), seconds

    def exhausted(self) -> bool:
        return time.monotonic() - self.start > self.seconds


def _home_entry(website: str, client: HttpClient, enrichment: EnrichmentResult | None,
                content: SiteContent, home_url: str) -> dict | None:
    """Home dall'enrichment (se c'è) oppure scaricata. None se non ottenibile (errore in content)."""
    if enrichment is not None and enrichment.ok and enrichment.page_texts:
        return next(iter(enrichment.page_texts.values()))
    try:
        page = _fetch(client, home_url)
        content.fetched += 1
    except Exception as exc:  # noqa: BLE001
        content.error = describe_exception(exc)
        return None
    if page.status_code >= 400:
        content.error = str(status_error(page.status_code))
        return None
    if not page.is_html:
        content.error = f"contenuto non HTML ({page.content_type.split(';')[0]})"
        return None
    parsed = parse_page(page)
    site = normalize_domain(page.final_url) or ""
    if site != content.domain and is_domain_in(site, NEVER_FETCH):
        content.error = f"il sito reindirizza a {site}"
        return None
    return page_text_entry(parsed, home=True)


def _extra_entry(url: str, client: HttpClient, enrichment: EnrichmentResult | None,
                 content: SiteContent, site_domain: str) -> dict | None:
    cached = (enrichment.page_texts if enrichment is not None else {}).get(_canonical(url))
    if cached is not None:
        return cached
    try:
        page = _fetch(client, url)
        content.fetched += 1
    except Exception as exc:  # noqa: BLE001
        content.errors.append(f"{url}: {describe_exception(exc)}")
        return None
    if page.status_code >= 400:
        content.errors.append(f"{url}: {status_error(page.status_code)}")
        return None
    if not page.is_html:
        content.errors.append(f"{url}: non HTML")
        return None
    if not _same_site(page.final_url, site_domain):
        content.errors.append(f"{url}: redirect esterno")
        return None
    return page_text_entry(parse_page(page))


def collect_site_content(website: str, client: HttpClient, enrichment: EnrichmentResult | None = None,
                         time_budget: float = 45, today=None) -> SiteContent:
    """Home + pagine servizi/chi siamo/portfolio + blog. Se la home non è ottenibile,
    ``content.error`` spiega perché e ``pages`` resta vuota."""
    budget = _Budget(time_budget)
    home_url = homepage_url(website) or ""
    content = SiteContent(domain=normalize_domain(home_url) or "", home_url=home_url)
    if not home_url:
        content.error = "URL non valido"
        return content
    entry = _home_entry(website, client, enrichment, content, home_url)
    if entry is None:
        content.errors.append(content.error)
        return content
    site_domain = normalize_domain(entry["url"]) or content.domain
    total = 0

    def add(kind: str, e: dict) -> None:
        nonlocal total
        text, truncated = _cap(e.get("text", ""), PAGE_CHAR_CAP)
        remaining = TOTAL_CHAR_CAP - total
        if len(text) > remaining:
            text, truncated = text[:max(0, remaining)].rstrip(), True
        total += len(text)
        content.pages.append(PageText(kind, e["url"], e.get("title", ""), text, truncated))

    add("home", entry)
    links = list(entry.get("links", []))
    for kind, url in select_pages(links, site_domain, entry["url"]).items():
        if total >= TOTAL_CHAR_CAP:
            break
        if budget.exhausted():
            content.errors.append("budget di tempo esaurito")
            break
        e = _extra_entry(url, client, enrichment, content, site_domain)
        if e is not None:
            add(kind, e)

    if budget.exhausted():
        content.errors.append("blog non controllato: budget di tempo esaurito")
    else:
        try:
            content.blog = detect_blog(HomeData(entry["url"], links, list(entry.get("feeds", []))),
                                       client, today)
            content.fetched += content.blog.requests
        except Exception as exc:  # noqa: BLE001
            content.errors.append(f"blog: {describe_exception(exc)}")
    return content
