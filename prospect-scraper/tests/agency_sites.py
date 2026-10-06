"""Server HTTP locale con finti siti di agenzie (127.0.0.11-14, un IP per sito) per i test della
qualifica. Su macOS gli alias di loopback 127.0.0.2-15 vanno creati (vedi il workflow Mac).

Uso: ``with AgencySites() as srv: srv.url("127.0.0.11")``; ``srv.hits`` elenca le richieste
(host, percorso) ricevute, ``srv.hosts_hit()`` gli host contattati.
"""

from __future__ import annotations

import socket
import threading
from datetime import date, timedelta
from email.utils import format_datetime
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST_ROSSO, HOST_BLU, HOST_VERDE, HOST_GRIGIO = "127.0.0.11", "127.0.0.12", "127.0.0.13", "127.0.0.14"
HOST_OTHER = "127.0.0.15"        # sito "esterno" linkato dalla home di Rosso: non va mai visitato
LOREM = "Lavoriamo con aziende e professionisti con metodo e trasparenza. " * 6


def _html(title: str, body: str, head: str = "") -> str:
    return (f'<!doctype html><html lang="it"><head><meta charset="utf-8"><title>{title}</title>{head}'
            f"</head><body>{body}</body></html>")


def _rosso_home(port: int) -> str:
    nav = ('<nav><a href="/servizi">Servizi</a> <a href="/servizi/seo-roma">SEO a Roma</a> '
           '<a href="/chi-siamo">Chi siamo</a> <a href="/portfolio">Portfolio</a> '
           '<a href="/blog">Blog</a> <a href="/contatti">Contatti</a> '
           '<a href="https://www.linkedin.com/company/studio-rosso">LinkedIn</a> '
           f'<a href="http://{HOST_OTHER}:{port}/servizi">Servizi dei partner</a></nav>')
    head = ('<link rel="alternate" type="application/rss+xml" title="Commenti" href="/comments/feed.xml">'
            '<link rel="alternate" type="application/rss+xml" title="Blog" href="/feed.xml">')
    return _html("Studio Rosso | Agenzia web e SEO", nav + f"<h1>Studio Rosso</h1><p>{LOREM}</p>", head)


def _rss(latest: date) -> str:
    def item(d: date, title: str) -> str:
        dt = datetime(d.year, d.month, d.day, 9, 0, tzinfo=timezone.utc)
        return f"<item><title>{title}</title><pubDate>{format_datetime(dt)}</pubDate></item>"
    return ('<?xml version="1.0"?><rss version="2.0"><channel><title>Blog</title>'
            f"{item(latest, 'Ultimo articolo')}{item(latest - timedelta(days=90), 'Articolo vecchio')}"
            "</channel></rss>")


def _site(host: str, path: str, port: int):
    """-> (status, content-type, body) oppure None (404)."""
    ct_html, ct_txt, ct_xml = "text/html; charset=utf-8", "text/plain", "application/rss+xml"
    if host == HOST_ROSSO:
        pages = {
            "/": _rosso_home(port),
            "/servizi": _html("Servizi", f"<h1>I nostri servizi</h1><p>SEO, social media management e "
                                         f"manutenzione siti con canone mensile. {LOREM}</p>"),
            "/servizi/seo-roma": _html("SEO a Roma", "<p>Pagina SEO locale.</p>"),
            "/chi-siamo": _html("Chi siamo", f"<h1>Chi siamo</h1><p>Un team di 4 persone. {LOREM}</p>"),
            "/portfolio": _html("Portfolio", f"<h1>Portfolio</h1><p>Progetti per Cantine Rossi e Hotel Sole. {LOREM}</p>"),
            "/contatti": _html("Contatti", '<p>Scrivi a <a href="mailto:info@studiorosso.it">info@studiorosso.it</a></p>'),
            "/blog": _html("Blog", "<h1>Blog</h1>"),
            "/robots.txt": "User-agent: *\nDisallow: /riservato\n",
        }
        if path in pages:
            return 200, ct_txt if path.endswith(".txt") else ct_html, pages[path]
        if path == "/feed.xml":
            return 200, ct_xml, _rss(date.today() - timedelta(days=10))
        if path == "/comments/feed.xml":
            return 200, ct_xml, _rss(date(2001, 1, 1))
        return None
    if host == HOST_BLU:
        head = ""
        nav = ('<nav><a href="/servizi">Servizi</a> <a href="/chi-siamo">Chi siamo</a> '
               '<a href="/portfolio">Lavori</a> <a href="/news">News</a> <a href="/newsletter">Newsletter</a></nav>')
        pages = {
            "/": _html("Web Agency Blu", nav + f"<p>{LOREM}</p>", head),
            "/servizi": _html("Servizi", f"<p>Siti web ed e-commerce. {LOREM}</p>"),
            "/chi-siamo": _html("Chi siamo", f"<p>Siamo in 12. {LOREM}</p>"),
            "/portfolio": _html("Lavori", "<p>Non dovrebbe essere letta.</p>"),
            "/news": _html("News", '<article><time datetime="2021-03-12">12 marzo 2021</time></article>'
                                   "<article>Pubblicato il 3 gennaio 2020</article>"),
            "/robots.txt": "User-agent: *\nDisallow: /portfolio\n",
        }
        if path in pages:
            return 200, ct_txt if path.endswith(".txt") else ct_html, pages[path]
        return None
    if host == HOST_VERDE:
        pages = {
            "/": _html("Verde Shop", f'<a href="/chi-siamo">Chi siamo</a><p>Negozio online di piante. {LOREM}</p>'),
            "/chi-siamo": _html("Chi siamo", "<p>Vivaio a conduzione familiare.</p>"),
        }
        return (200, ct_html, pages[path]) if path in pages else None
    if host == HOST_GRIGIO:
        pages = {"/": _html("Grigio Studio", f'<a href="/servizi">Servizi</a><p>{LOREM}</p>'),
                 "/servizi": _html("Servizi", "<p>Grafica e branding.</p>")}
        return (200, ct_html, pages[path]) if path in pages else None
    if host == HOST_OTHER:
        return 200, ct_html, _html("Altro sito", "<p>Non dovrebbe essere visitato.</p>")
    return None


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802
        host = self.headers.get("Host", "").split(":")[0]
        path = self.path.split("?")[0]
        self.server.hits.append((host, path))                      # type: ignore[attr-defined]
        res = _site(host, path, self.server.server_address[1])
        status, ctype, body = res if res else (404, "text/html", "<html><body>404</body></html>")
        data = body.encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


class AgencySites:
    def __init__(self) -> None:
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.httpd = ThreadingHTTPServer(("0.0.0.0", self.port), _Handler)
        self.httpd.daemon_threads = True
        self.httpd.hits = []                                       # type: ignore[attr-defined]

    @property
    def hits(self) -> list[tuple[str, str]]:
        return list(self.httpd.hits)                               # type: ignore[attr-defined]

    def hosts_hit(self) -> set[str]:
        return {h for h, _ in self.hits}

    def paths_hit(self, host: str) -> list[str]:
        return [p for h, p in self.hits if h == host and p != "/robots.txt"]

    def url(self, host: str, path: str = "/") -> str:
        return f"http://{host}:{self.port}{path}"

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
