"""Website enrichment: visita la home e le pagine utili (contatti, chi siamo, ...)
ed estrae contatti, social e dati aziendali.

Regole: robots.txt rispettato, massimo ``MAX_PAGES_PER_DOMAIN`` pagine, budget di
tempo per dominio, nessun tentativo di superare login/CAPTCHA/anti-bot.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from config import settings
from scrapers import company, contacts, social
from scrapers.http import FetchError, HttpClient, Page, default_client, describe_exception, status_error
from utils.logging import get_logger
from utils.normalization import clean_text, homepage_url, is_domain_in, normalize_domain, normalize_url

log = get_logger("website")

_SKIP_EXT = re.compile(r"\.(pdf|jpe?g|png|gif|svg|webp|zip|rar|docx?|xlsx?|pptx?|mp4|mp3|avi|mov|"
                       r"ics|xml|rss|css|js|json)$", re.I)
_CAPTCHA_MARKERS = ("cf-chl", "challenge-platform", "just a moment...", "attention required",
                    "captcha-delivery", "px-captcha", "are you a robot", "verify you are human",
                    "ddos-guard", "_incapsula_resource", "sgcaptcha")
_TLD_REGION = {"it": "IT", "fr": "FR", "de": "DE", "es": "ES", "ch": "CH", "at": "AT",
               "uk": "GB", "pt": "PT", "nl": "NL", "be": "BE", "gr": "GR", "mt": "MT",
               "sm": "SM", "ie": "IE", "us": "US"}
_playwright_lock = threading.Lock()


@dataclass
class EnrichmentResult:
    website: str
    ok: bool = False
    error: str = ""
    final_url: str = ""
    pages_visited: list[str] = field(default_factory=list)
    pages_failed: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    company_name: str = ""
    company_name_source: str = ""   # schema.org | og:site_name | title
    page_title: str = ""
    description: str = ""
    address: str = ""
    postal_code: str = ""
    city: str = ""
    region: str = ""
    country: str = ""
    country_source: str = ""
    vat_id: str = ""
    emails: list[str] = field(default_factory=list)
    phones: list[contacts.Phone] = field(default_factory=list)
    socials: dict[str, list[str]] = field(default_factory=dict)
    jsonld: dict = field(default_factory=dict)
    rendered_js: bool = False


@dataclass
class ParsedPage:
    url: str
    soup: BeautifulSoup
    html: str
    text: str
    links: list[tuple[str, str]]  # (url assoluto, anchor text)


def looks_like_captcha(page: Page, text: str) -> bool:
    low_html = page.content[:200_000].decode("utf-8", errors="ignore").lower()
    if page.headers.get("cf-mitigated", "").lower() == "challenge":
        return True
    if page.status_code in (403, 429, 503) and any(m in low_html for m in _CAPTCHA_MARKERS):
        return True
    # pagina 200 quasi vuota che contiene solo una verifica
    return len(text) < 400 and any(m in low_html for m in _CAPTCHA_MARKERS + ("g-recaptcha", "hcaptcha"))


def needs_javascript(soup: BeautifulSoup, text: str) -> bool:
    if len(text) >= settings.JS_MIN_TEXT_CHARS:
        return False
    if not soup.find("script"):
        return False
    noscript = " ".join(n.get_text(" ") for n in soup.find_all("noscript")).lower()
    root = soup.find(id=re.compile(r"^(root|app|__next|__nuxt|svelte|main-app)$"))
    return "javascript" in noscript or root is not None or len(soup.find_all("script")) >= 3


def parse_page(page: Page) -> ParsedPage:
    charset = None
    m = re.search(r"charset=([\w-]+)", page.content_type or "", re.I)
    if m:
        charset = m.group(1)
    soup = BeautifulSoup(page.content, "lxml", from_encoding=charset)
    encoding = soup.original_encoding or charset or "utf-8"
    try:
        html = page.content.decode(encoding, errors="replace")
    except LookupError:
        html = page.content.decode("utf-8", errors="replace")
    base = page.final_url
    base_tag = soup.find("base", href=True)
    if base_tag:
        base = urljoin(base, base_tag["href"])
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "javascript:")):
            continue
        try:
            links.append((urljoin(base, href), clean_text(a.get_text(" "))[:80]))
        except ValueError:
            continue
    # testo visibile: senza script/stili (le email nei JSON vengono prese dall'HTML grezzo)
    text_soup = BeautifulSoup(str(soup.body or soup), "lxml")
    for tag in text_soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    text = clean_text(text_soup.get_text(" "))
    return ParsedPage(url=page.final_url, soup=soup, html=html, text=text, links=links)


def render_with_playwright(url: str) -> Page | None:
    """Renderizza la pagina con Chromium headless (solo se Playwright è installato)."""
    if not settings.USE_PLAYWRIGHT:
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    with _playwright_lock:  # un browser alla volta: è costoso
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True, executable_path=settings.PLAYWRIGHT_EXECUTABLE or None)
                try:
                    ctx = browser.new_context(user_agent=settings.USER_AGENT)
                    pg = ctx.new_page()
                    resp = pg.goto(url, timeout=settings.PLAYWRIGHT_TIMEOUT_MS, wait_until="networkidle")
                    html = pg.content()
                    return Page(url=url, final_url=pg.url, status_code=resp.status if resp else 200,
                                content=html.encode("utf-8"),
                                content_type="text/html; charset=utf-8", rendered=True)
                finally:
                    browser.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("Playwright fallito su %s: %s", url, exc)
            return None


def _link_priority(url: str, anchor: str) -> int | None:
    path = urlsplit(url).path.lower()
    haystack = f"{path} {anchor.lower()}"
    best = None
    for kw, prio in settings.PAGE_KEYWORDS.items():
        if kw in haystack and (best is None or prio < best):
            best = prio
    return best


def _same_site(url: str, site_domain: str) -> bool:
    d = normalize_domain(url)
    return bool(d) and (d == site_domain or d.endswith("." + site_domain) or site_domain.endswith("." + d))


def _canonical(url: str) -> str:
    parts = urlsplit(url)
    path = re.sub(r"/{2,}", "/", parts.path or "/").rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, "", ""))


class WebsiteCrawler:
    def __init__(self, client: HttpClient | None = None, max_pages: int | None = None,
                 time_budget: float | None = None):
        self.client = client or default_client()
        self.max_pages = max_pages or settings.MAX_PAGES_PER_DOMAIN
        self.time_budget = time_budget or settings.DOMAIN_TIME_BUDGET

    # --- fetch con fallback http se il certificato non è valido ---------------
    def _fetch(self, url: str) -> Page:
        try:
            return self.client.get(url, check_robots=True)
        except requests.exceptions.SSLError:
            if url.startswith("https://"):
                alt = "http://" + url[len("https://"):]
                log.info("SSL non valido su %s, riprovo in http", url)
                page = self.client.get(alt, check_robots=True)
                return page
            raise

    def enrich(self, website: str) -> EnrichmentResult:
        start = time.monotonic()
        res = EnrichmentResult(website=website)
        home = homepage_url(website)
        if not home:
            res.error = "URL non valido"
            return res
        try:
            page = self._fetch(home)
        except FetchError as exc:
            res.error = str(exc)
            return res
        except Exception as exc:  # noqa: BLE001
            log.info("home non raggiungibile %s: %s", home, exc)
            res.error = describe_exception(exc)
            return res

        if page.status_code >= 400:
            parsed_err_text = page.content[:5000].decode("utf-8", errors="ignore")
            if looks_like_captcha(page, parsed_err_text):
                res.error = "protezione anti-bot/CAPTCHA (non aggirata)"
            else:
                res.error = str(status_error(page.status_code))
            return res
        if not page.is_html:
            res.error = f"contenuto non HTML ({page.content_type.split(';')[0]})"
            return res

        res.final_url = page.final_url
        site_domain = normalize_domain(page.final_url) or normalize_domain(home)
        if site_domain != normalize_domain(home):
            res.warnings.append(f"redirect a {site_domain}")
            if is_domain_in(site_domain, settings.NON_COMPANY_DOMAINS):
                res.error = f"il sito reindirizza a {site_domain}"
                return res

        parsed = parse_page(page)
        if looks_like_captcha(page, parsed.text):
            res.error = "protezione anti-bot/CAPTCHA (non aggirata)"
            return res
        if needs_javascript(parsed.soup, parsed.text):
            rendered = render_with_playwright(page.final_url)
            if rendered is not None:
                parsed = parse_page(rendered)
                res.rendered_js = True
                log.info("home renderizzata con Playwright: %s", page.final_url)
            else:
                res.warnings.append("la pagina richiede JavaScript (Playwright non disponibile)")

        pages = [parsed]
        res.pages_visited.append(parsed.url)
        visited = {_canonical(parsed.url), _canonical(home)}

        # --- pagine candidate: link della home (per URL o anchor text) ---
        queue: list[tuple[int, int, str, str]] = []  # (priorità, ordine, canonico, url)
        order = 0

        def enqueue(links):
            nonlocal order
            for url, anchor in links:
                if not url.startswith(("http://", "https://")) or _SKIP_EXT.search(urlsplit(url).path):
                    continue
                if not _same_site(url, site_domain):
                    continue
                prio = _link_priority(url, anchor)
                can = _canonical(url)
                if prio is None or can in visited or any(q[2] == can for q in queue):
                    continue
                queue.append((prio, order, can, url.split("#")[0]))
                order += 1

        enqueue(parsed.links)
        if sum(1 for q in queue if q[0] <= 1) < 1:
            root = f"{urlsplit(parsed.url).scheme}://{urlsplit(parsed.url).netloc}"
            probes = [(root + p, "") for p in settings.FALLBACK_PATHS[: settings.MAX_FALLBACK_PROBES]]
            enqueue(probes)

        while queue and len(res.pages_visited) < self.max_pages:
            if time.monotonic() - start > self.time_budget:
                res.warnings.append("budget di tempo esaurito")
                break
            queue.sort()
            prio, _, can, url = queue.pop(0)
            visited.add(can)
            try:
                sub = self.client.get(url, check_robots=True)
            except FetchError as exc:
                res.pages_failed[url] = str(exc)
                continue
            except Exception as exc:  # noqa: BLE001
                res.pages_failed[url] = describe_exception(exc)
                continue
            if sub.status_code >= 400 or not sub.is_html:
                res.pages_failed[url] = f"HTTP {sub.status_code}" if sub.status_code >= 400 else "non HTML"
                continue
            if not _same_site(sub.final_url, site_domain):
                res.pages_failed[url] = "redirect esterno"
                continue
            sp = parse_page(sub)
            pages.append(sp)
            res.pages_visited.append(sp.url)
            visited.add(_canonical(sp.url))
            if prio <= 1:
                enqueue(sp.links)  # es. "contatti" linkata solo da "chi siamo"

        self._extract(res, pages, site_domain)
        res.ok = True
        return res

    # --- estrazione aggregata -------------------------------------------------
    def _extract(self, res: EnrichmentResult, pages: list[ParsedPage], site_domain: str) -> None:
        tld = site_domain.rsplit(".", 1)[-1]
        region = _TLD_REGION.get(tld, settings.DEFAULT_PHONE_REGION)
        emails: list[str] = []
        phones: dict[str, contacts.Phone] = {}
        social_urls: list[str] = []
        home = pages[0]

        # le pagine contatti vengono prima per indirizzo/telefono
        ordered = sorted(pages[1:], key=lambda p: _link_priority(p.url, "") or 9) + [home]
        for p in pages:
            for e in contacts.extract_emails(p.soup, p.html):
                if e not in emails:
                    emails.append(e)
            social_urls.extend(u for u, _ in p.links)
        for p in ordered:
            for ph in contacts.extract_phones(p.soup, p.text, region):
                if ph.e164 not in phones or (ph.from_tel_link and not phones[ph.e164].from_tel_link):
                    phones[ph.e164] = ph

        ld = {}
        for p in pages:
            candidate = company.extract_jsonld(p.soup)
            if len([v for v in candidate.values() if v]) > len([v for v in ld.values() if v]):
                ld = candidate
        res.jsonld = ld
        social_urls.extend(ld.get("same_as", []))
        if ld.get("email"):
            e = contacts.clean_email(ld["email"])
            if e and e not in emails:
                emails.append(e)
        if ld.get("phone"):
            for ph in contacts.extract_phones(BeautifulSoup("", "lxml"), ld["phone"], region):
                phones.setdefault(ph.e164, ph)

        res.emails = contacts.sort_emails(emails, site_domain)
        res.phones = sorted(phones.values(), key=lambda p: not p.from_tel_link)
        res.socials = social.extract_socials(social_urls)

        meta = company.extract_meta(home.soup)
        res.page_title = meta["title"]
        res.description = (meta["description"] or ld.get("description", ""))[:500]
        for name, source in ((ld.get("name"), "schema.org"), (meta["site_name"], "og:site_name"),
                             (company.company_name_from_title(meta["title"], site_domain), "title")):
            if name:
                res.company_name, res.company_name_source = name, source
                break

        micro: dict[str, str] = {}
        addr: dict[str, str] = {}
        for p in ordered:
            micro = micro or company.extract_microdata(p.soup)
            addr = addr or company.extract_address(p.text)
            res.vat_id = res.vat_id or company.extract_vat(p.text) or ld.get("vat_id", "")
        res.vat_id = re.sub(r"\D", "", res.vat_id)[-11:] if res.vat_id else ""

        res.address = ld.get("address") or micro.get("address") or addr.get("address", "")
        res.postal_code = ld.get("postal_code") or micro.get("postal_code") or addr.get("postal_code", "")
        res.city = ld.get("city") or micro.get("city") or addr.get("city", "")
        ld_region = ld.get("region", "")
        res.region = (company.region_from_province(addr.get("province", ""))
                      or company.region_from_province(ld_region)
                      or (ld_region if len(ld_region) > 2 else "")
                      or micro.get("region", ""))

        for value, source in ((ld.get("country"), "schema.org"), (micro.get("country"), "microdata"),
                              (addr.get("country"), "indirizzo")):
            if value:
                res.country, res.country_source = value, source
                break
        if not res.country and res.phones and all(p.e164.startswith("+39") for p in res.phones):
            res.country, res.country_source = "Italia", "prefisso telefonico"
