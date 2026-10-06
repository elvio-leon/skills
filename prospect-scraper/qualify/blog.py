"""Rilevamento deterministico del blog: link nella home -> data dell'ultimo articolo.

Al più UNA richiesta extra (il feed RSS/Atom se dichiarato nell'<head>, altrimenti la pagina
del blog), sempre tramite ``HttpClient.get(url, check_robots=True)``.
"""

from __future__ import annotations

import email.utils
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from scrapers.http import HttpClient
from scrapers.website import _same_site, feed_links, parse_page
from utils.logging import get_logger
from utils.normalization import normalize_domain

log = get_logger("qualify.blog")

BLOG_KEYWORDS = ("blog", "news", "magazine", "insights", "articoli", "approfondimenti", "journal",
                 "notizie")
ACTIVE_DAYS = 183           # ultimo articolo entro ~6 mesi = blog attivo
MIN_DATE = date(2000, 1, 1)
FUTURE_TOLERANCE_DAYS = 2

STATUS_ABSENT, STATUS_ACTIVE, STATUS_STALE, STATUS_UNKNOWN = (
    "assente", "attivo", "fermo", "non determinabile")

_MONTHS = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
    "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_MONTH_RE = "|".join(sorted(_MONTHS, key=len, reverse=True))
_NUM_DATE = re.compile(r"(?<!\d)(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})(?!\d)")
_DAY_MONTH_YEAR = re.compile(rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th|°|º)?\s+({_MONTH_RE})\s+(\d{{4}})(?!\d)", re.I)
_MONTH_DAY_YEAR = re.compile(rf"\b({_MONTH_RE})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})(?!\d)", re.I)
_URL_DATE = re.compile(r"/((?:19|20)\d{2})/(0[1-9]|1[0-2])(?:/|$)")


@dataclass
class BlogInfo:
    status: str = STATUS_ABSENT
    last_post: date | None = None
    url: str = ""
    source: str = ""            # feed | pagina | "" (nessun blog)
    requests: int = 0           # richieste HTTP fatte (0 o 1)


@dataclass
class HomeData:
    """Dati della home necessari al rilevamento (anche un ``ParsedPage`` va bene)."""

    url: str
    links: list[tuple[str, str]] = field(default_factory=list)
    feeds: list[str] = field(default_factory=list)


def _in_range(d: date, today: date) -> bool:
    return MIN_DATE <= d <= today + timedelta(days=FUTURE_TOLERANCE_DAYS)


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date_value(value: str) -> date | None:
    """Data da un valore RFC 2822 (RSS) o ISO 8601 (Atom, meta, JSON-LD)."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return email.utils.parsedate_to_datetime(value).date()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", value)
    return _safe_date(int(m[1]), int(m[2]), int(m[3])) if m else None


def dates_from_text(text: str) -> list[date]:
    out: list[date] = []
    for m in _NUM_DATE.finditer(text):
        d = _safe_date(int(m[3]), int(m[2]), int(m[1]))      # gg/mm/aaaa
        if d:
            out.append(d)
    for m in _DAY_MONTH_YEAR.finditer(text):
        d = _safe_date(int(m[3]), _MONTHS[m[2].lower()], int(m[1]))
        if d:
            out.append(d)
    for m in _MONTH_DAY_YEAR.finditer(text):
        d = _safe_date(int(m[3]), _MONTHS[m[1].lower()], int(m[2]))
        if d:
            out.append(d)
    return out


def _jsonld_dates(soup: BeautifulSoup) -> list[date]:
    found: list[date] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "datePublished" and isinstance(value, str):
                    d = parse_date_value(value)
                    if d:
                        found.append(d)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(tag.string or tag.get_text() or ""))
        except ValueError:
            continue
    return found


def dates_from_html(soup: BeautifulSoup, text: str, links: list[tuple[str, str]]) -> list[date]:
    """Tutte le date plausibili di una pagina blog: <time>, meta, JSON-LD, testo, URL degli articoli."""
    out: list[date] = []
    for t in soup.find_all("time"):
        d = parse_date_value(t.get("datetime", ""))
        if d:
            out.append(d)
    for meta in soup.find_all("meta", attrs={"property": "article:published_time"}):
        d = parse_date_value(meta.get("content", ""))
        if d:
            out.append(d)
    out += _jsonld_dates(soup)
    out += dates_from_text(text)
    for url, _ in links:
        m = _URL_DATE.search(urlsplit(url).path)
        if m:
            d = _safe_date(int(m[1]), int(m[2]), 1)
            if d:
                out.append(d)
    return out


def dates_from_feed(xml: str) -> list[date]:
    """Date degli articoli di un feed RSS (pubDate, dc:date) o Atom (published, updated)."""
    soup = BeautifulSoup(xml, "xml")
    out: list[date] = []
    for el in soup.find_all(True):
        local = (el.name or "").split(":")[-1].lower()
        if local in ("pubdate", "updated", "published", "date"):
            d = parse_date_value(el.get_text())
            if d:
                out.append(d)
    return out


def _words(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9]+", " ", text.lower()) + " "


def find_blog_link(links: list[tuple[str, str]], site_domain: str) -> str:
    """Link al blog (stesso sito): quello con il percorso meno profondo tra i candidati."""
    best: tuple[int, int, str] | None = None
    for i, (url, anchor) in enumerate(links):
        if not url.startswith(("http://", "https://")) or not _same_site(url, site_domain):
            continue
        path = urlsplit(url).path
        hay = _words(f"{path} {anchor}")
        if not any(f" {k} " in hay for k in BLOG_KEYWORDS):
            continue
        key = (len([s for s in path.split("/") if s]), i, url.split("#")[0])
        if best is None or key < best:
            best = key
    return best[2] if best else ""


def _feeds_of(home) -> list[str]:
    feeds = getattr(home, "feeds", None)
    if feeds is not None:
        return list(feeds)
    soup = getattr(home, "soup", None)
    return feed_links(soup, home.url) if soup is not None else []


def _status(dates: list[date], today: date) -> tuple[str, date | None]:
    valid = [d for d in dates if _in_range(d, today)]
    if not valid:
        return STATUS_UNKNOWN, None
    latest = max(valid)
    return (STATUS_ACTIVE if (today - latest).days <= ACTIVE_DAYS else STATUS_STALE), latest


def detect_blog(home, client: HttpClient, today: date | None = None) -> BlogInfo:
    """Stato del blog dal link nella home. ``home`` ha ``url``, ``links`` e (facoltativo) ``feeds``."""
    today = today or date.today()
    site = normalize_domain(home.url) or ""
    blog_url = find_blog_link(list(home.links), site)
    if not blog_url:
        return BlogInfo(STATUS_ABSENT)
    info = BlogInfo(STATUS_UNKNOWN, url=blog_url)
    feeds = [f for f in _feeds_of(home) if _same_site(f, site)]
    target, source = (feeds[0], "feed") if feeds else (blog_url, "pagina")
    info.source, info.requests = source, 1
    try:
        page = client.get(target, check_robots=True)
    except Exception as exc:  # noqa: BLE001 - il blog non deve mai far fallire la qualifica
        log.info("blog non leggibile %s: %s", target, exc)
        return info
    if page.status_code >= 400:
        return info
    if source == "feed":
        dates = dates_from_feed(page.content.decode("utf-8", errors="replace"))
    else:
        parsed = parse_page(page)
        dates = dates_from_html(parsed.soup, parsed.text, parsed.links)
    info.status, info.last_post = _status(dates, today)
    return info
