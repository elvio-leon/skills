"""Client HTTP condiviso: user-agent identificabile, timeout, retry limitati,
pausa minima per host, robots.txt e classificazione degli errori."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import settings
from utils.logging import get_logger

log = get_logger("http")

# Siti che il programma non apre MAI (si usano solo URL e titoli dei risultati di ricerca).
NEVER_OPEN = ("linkedin.com",)


def never_open(url: str) -> bool:
    host = (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in NEVER_OPEN)


class FetchError(Exception):
    """Errore di rete/HTTP con messaggio leggibile per l'utente."""


@dataclass
class Page:
    url: str                   # URL richiesto
    final_url: str             # URL dopo eventuali redirect
    status_code: int
    content: bytes
    content_type: str = ""
    headers: dict = field(default_factory=dict)
    rendered: bool = False     # True se ottenuta tramite Playwright

    @property
    def is_html(self) -> bool:
        ct = self.content_type.lower()
        return not ct or "html" in ct or "xml" in ct

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def describe_exception(exc: Exception) -> str:
    """Traduce un'eccezione di rete in un messaggio breve e comprensibile."""
    if isinstance(exc, FetchError):
        return str(exc)
    msg = str(exc)
    if isinstance(exc, requests.exceptions.SSLError):
        return "SSL error (certificato non valido)"
    if isinstance(exc, (requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout,
                        requests.exceptions.Timeout)):
        return "timeout"
    if isinstance(exc, requests.exceptions.TooManyRedirects):
        return "troppi redirect"
    if isinstance(exc, requests.exceptions.RetryError):
        if "429" in msg:
            return "rate limit (HTTP 429)"
        return "errore del server dopo i retry"
    if isinstance(exc, requests.exceptions.ConnectionError):
        low = msg.lower()
        if "timed out" in low or "timeout" in low:
            return "timeout"
        if any(k in low for k in ("name or service not known", "nodename nor servname",
                                  "getaddrinfo failed", "name resolution",
                                  "no address associated", "failed to resolve")):
            return "DNS failure (dominio inesistente)"
        if "refused" in low:
            return "connessione rifiutata"
        return "sito non raggiungibile"
    if isinstance(exc, requests.exceptions.InvalidURL):
        return "URL non valido"
    return f"errore: {type(exc).__name__}"


def _http_status_message(code: int) -> str:
    return {
        401: "HTTP 401 (richiede autenticazione)",
        403: "HTTP 403 (accesso negato)",
        404: "HTTP 404 (pagina non trovata)",
        410: "HTTP 410 (pagina rimossa)",
        429: "rate limit (HTTP 429)",
    }.get(code, f"HTTP {code}")


def _api_status_message(code: int) -> str:
    """Messaggi per le API con chiave: distingue chiave non valida e limite raggiunto."""
    if code in (401, 403):
        return f"chiave API non valida (HTTP {code})"
    if code == 429:
        return "limite di ricerche raggiunto (HTTP 429)"
    return _http_status_message(code)


class HttpClient:
    """Thread-safe: può essere condiviso dai worker dell'enrichment."""

    def __init__(
        self,
        timeout: float | None = None,
        delay: float | None = None,
        retries: int | None = None,
        user_agent: str | None = None,
        respect_robots: bool | None = None,
    ):
        self.timeout = settings.REQUEST_TIMEOUT if timeout is None else timeout
        self.delay = settings.REQUEST_DELAY if delay is None else delay
        self.respect_robots = settings.RESPECT_ROBOTS if respect_robots is None else respect_robots
        self.user_agent = user_agent or settings.USER_AGENT
        retries = settings.MAX_RETRIES if retries is None else retries

        self._retry = Retry(
            total=retries,
            connect=retries,
            read=1,
            status=retries,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD", "POST"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self._local = threading.local()
        self._host_lock = threading.Lock()
        self._next_slot: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | str] = {}
        self._robots_lock = threading.Lock()

    # -- sessione per thread (requests.Session non è garantita thread-safe) --
    @property
    def session(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            adapter = HTTPAdapter(max_retries=self._retry, pool_maxsize=10)
            s.mount("http://", adapter)
            s.mount("https://", adapter)
            s.headers.update({
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "it-IT,it;q=0.9,en;q=0.8",
            })
            self._local.session = s
        return s

    # -- rate limit per host --
    def throttle(self, url: str, min_interval: float | None = None) -> None:
        host = (urlsplit(url).hostname or "").lower()
        interval = self.delay if min_interval is None else min_interval
        if interval <= 0:
            return
        with self._host_lock:
            now = time.monotonic()
            slot = max(now, self._next_slot.get(host, 0.0))
            self._next_slot[host] = slot + interval
        wait = slot - now
        if wait > 0:
            time.sleep(wait)

    # -- robots.txt (RFC 9309) --
    def robots_allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        with self._robots_lock:
            parser = self._robots.get(base)
        if parser is None:
            parser = self._load_robots(base)
            with self._robots_lock:
                self._robots[base] = parser
        if parser == "allow":
            return True
        if parser == "deny":
            return False
        return parser.can_fetch(settings.ROBOTS_USER_AGENT, url)  # type: ignore[union-attr]

    def _load_robots(self, base: str):
        robots_url = base + "/robots.txt"
        try:
            self.throttle(robots_url)
            r = self.session.get(robots_url, timeout=self.timeout, allow_redirects=True)
        except requests.exceptions.SSLError:
            raise
        except requests.RequestException as exc:
            log.info("robots.txt non raggiungibile per %s: %s", base, exc)
            raise FetchError(describe_exception(exc)) from exc
        if 400 <= r.status_code < 500:
            return "allow"   # RFC 9309: robots.txt assente/non accessibile -> consentito
        if r.status_code >= 500:
            return "deny"    # RFC 9309: errore server -> considerare tutto vietato
        parser = RobotFileParser()
        parser.parse(r.text.splitlines())
        return parser

    # -- GET --
    def get(
        self,
        url: str,
        *,
        params: dict | None = None,
        check_robots: bool = False,
        min_interval: float | None = None,
        max_bytes: int | None = None,
        headers: dict | None = None,
        timeout: float | None = None,
    ) -> Page:
        if never_open(url):
            raise FetchError("le pagine linkedin.com non vengono mai aperte")
        if check_robots and not self.robots_allowed(url):
            raise FetchError("bloccato da robots.txt")
        self.throttle(url, min_interval)
        max_bytes = max_bytes or settings.MAX_PAGE_BYTES
        log.debug("GET %s", url)
        with self.session.get(url, params=params, timeout=timeout or self.timeout,
                              allow_redirects=True, stream=True, headers=headers) as r:
            chunks, size = [], 0
            for chunk in r.iter_content(chunk_size=65536):
                chunks.append(chunk)
                size += len(chunk)
                if size >= max_bytes:
                    log.info("pagina troncata a %d byte: %s", size, url)
                    break
            return Page(
                url=url,
                final_url=r.url,
                status_code=r.status_code,
                content=b"".join(chunks),
                content_type=r.headers.get("Content-Type", ""),
                headers=dict(r.headers),
            )

    def get_json(self, url: str, *, params: dict | None = None, data: dict | None = None,
                 min_interval: float | None = None, timeout: float | None = None,
                 headers: dict | None = None):
        """Chiamata ad API JSON (GET, o POST se ``data`` è valorizzato)."""
        if never_open(url):
            raise FetchError("le pagine linkedin.com non vengono mai aperte")
        self.throttle(url, min_interval)
        log.debug("API %s %s", url, params or "")
        if data is not None:
            r = self.session.post(url, data=data, timeout=timeout or self.timeout, headers=headers)
        else:
            r = self.session.get(url, params=params, timeout=timeout or self.timeout, headers=headers)
        if r.status_code != 200:
            describe = _http_status_message if headers is None else _api_status_message
            raise FetchError(f"{describe(r.status_code)} da {urlsplit(url).hostname}")
        try:
            return r.json()
        except ValueError as exc:
            raise FetchError(f"risposta non JSON da {urlsplit(url).hostname}") from exc

    def post_json(self, url: str, payload: dict, *, headers: dict | None = None,
                  min_interval: float | None = None, timeout: float | None = None):
        """POST con corpo JSON a un'API (es. Tavily). Gli header (chiavi API) non vengono loggati."""
        self.throttle(url, min_interval)
        log.debug("API POST %s", url)
        r = self.session.post(url, json=payload, timeout=timeout or self.timeout, headers=headers)
        if r.status_code != 200:
            raise FetchError(f"{_api_status_message(r.status_code)} da {urlsplit(url).hostname}")
        try:
            return r.json()
        except ValueError as exc:
            raise FetchError(f"risposta non JSON da {urlsplit(url).hostname}") from exc


def status_error(code: int) -> FetchError:
    return FetchError(_http_status_message(code))


_default_client: HttpClient | None = None
_default_lock = threading.Lock()


def default_client() -> HttpClient:
    global _default_client
    with _default_lock:
        if _default_client is None:
            _default_client = HttpClient()
        return _default_client
