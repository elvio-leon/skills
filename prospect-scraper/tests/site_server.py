"""Server HTTP locale che simula diversi siti aziendali (uno per IP di loopback).

Uso: ``with SiteServer() as srv: srv.url("127.0.0.2")``. Eseguibile anche da solo
per provare la UI: ``python -m tests.site_server`` (espone un finto SearXNG).
"""

from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ALFA_HOME = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<title>Home | Hotel Alfa Palermo</title>
<meta name="description" content="Hotel 4 stelle nel cuore di Palermo">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Hotel","name":"Hotel Alfa",
"address":{"@type":"PostalAddress","streetAddress":"Via Roma 10","postalCode":"90133",
"addressLocality":"Palermo","addressCountry":"IT"},"sameAs":["https://www.instagram.com/hotelalfa/"]}</script>
</head><body>
<nav><a href="/">Home</a><a href="/camere">Camere</a><a href="/chi-siamo/">Chi siamo</a>
<a href="/contatti">Contatti</a><a href="/privacy">Privacy</a><a href="/brochure.pdf">Brochure</a>
<a href="https://www.booking.com/hotel/alfa">Prenota</a></nav>
<p>Benvenuti all'Hotel Alfa, un hotel elegante nel centro storico. """ + "Lorem ipsum " * 40 + """</p>
<footer>Hotel Alfa S.r.l. - Via Roma, 10 - 90133 Palermo (PA) - P.IVA 01234567890
<a href="https://www.facebook.com/HotelAlfaPalermo">Facebook</a>
<a href="https://www.facebook.com/sharer/sharer.php?u=x">Condividi</a></footer>
</body></html>"""

ALFA_CONTATTI = """<html><head><title>Contatti - Hotel Alfa</title></head><body>
<h1>Contatti</h1><p>Scrivici a <a href="mailto:info@hotelalfa.it">info@hotelalfa.it</a>
oppure prenotazioni@hotelalfa.it. Telefono: <a href="tel:+390911234567">091 123 4567</a>,
WhatsApp 333 765 4321.</p><a href="https://www.linkedin.com/company/hotel-alfa/">LinkedIn</a>
<a href="mailto:noreply@hotelalfa.it">x</a></body></html>"""

ALFA_CHI = """<html><body><h1>Chi siamo</h1><p>Dal 1950 ospitalità siciliana.</p>
<a href="/team">Il team</a></body></html>"""

SPA_HOME = """<!doctype html><html><head><title>SpaCo</title></head><body>
<noscript>Please enable JavaScript to use this app.</noscript><div id="root"></div>
<script>document.getElementById('root').innerHTML =
'<h1>SpaCo SaaS</h1><p>Scrivici: <a href="mailto:hello@spaco.io">hello@spaco.io</a> tel +39 02 1234 5678</p>' +
'<a href="https://www.linkedin.com/company/spaco">in</a><p>' + 'testo '.repeat(80) + '</p>';</script>
<script>/* analytics */</script><script>/* vendor */</script></body></html>"""

REDIR_HOME = """<html><head><title>Benvenuti | Studio Beta</title>
<meta property="og:site_name" content="Studio Beta"></head><body>
<p>""" + "Consulenza per aziende. " * 30 + """</p>
<a href="/it/pagina-17">Scrivici</a> <a href="/it/pagina-18">Il nostro studio</a>
<p>Viale Europa 5/A, 20121 Milano MI</p></body></html>"""

REDIR_CONTACT = """<html><body><p>Contattaci: <a href="mailto:commerciale@studiobeta.it">email</a></p>
<p>Tel. 02 8765 4321 - P.IVA 09876543210</p><a href="https://x.com/studiobeta">X</a></body></html>"""

CAPTCHA = """<html><head><title>Just a moment...</title></head><body>
<div id="challenge-platform">Checking your browser</div></body></html>"""


def _site(host: str, path: str):
    """-> (status, headers, body) oppure None (404)."""
    html = {"Content-Type": "text/html; charset=utf-8"}
    if host == "127.0.0.2":  # sito completo
        pages = {"/": ALFA_HOME, "/contatti": ALFA_CONTATTI, "/chi-siamo/": ALFA_CHI,
                 "/team": "<html><body>Team: mario@hotelalfa.it</body></html>",
                 "/camere": "<html><body>Camere</body></html>",
                 "/privacy": "<html><body>privacy@hotelalfa.it</body></html>",
                 "/robots.txt": "User-agent: *\nDisallow: /privacy\n"}
        if path in pages:
            ct = {"Content-Type": "text/plain"} if path.endswith(".txt") else html
            return 200, ct, pages[path]
        return None
    if host == "127.0.0.3":  # robots.txt vieta tutto
        if path == "/robots.txt":
            return 200, {"Content-Type": "text/plain"}, "User-agent: *\nDisallow: /\n"
        return 200, html, "<html><body>info@vietato.it</body></html>"
    if host == "127.0.0.4":  # anti-bot
        if path == "/robots.txt":
            return None
        return 403, {**html, "cf-mitigated": "challenge"}, CAPTCHA
    if host == "127.0.0.5":  # lentissimo -> timeout
        if path == "/robots.txt":
            return None
        time.sleep(4)
        return 200, html, "<html><body>tardi</body></html>"
    if host == "127.0.0.6":  # SPA: contenuto solo via JavaScript
        return (200, html, SPA_HOME) if path == "/" else None
    if host == "127.0.0.7":  # redirect + link trovabili solo tramite anchor text
        if path == "/":
            return 301, {"Location": "/it/"}, ""
        pages = {"/it/": REDIR_HOME, "/it/pagina-17": REDIR_CONTACT,
                 "/it/pagina-18": "<html><body>Studio fondato nel 1990</body></html>"}
        return (200, html, pages[path]) if path in pages else None
    if host == "127.0.0.8":  # robots.txt in errore 500 -> tutto vietato (RFC 9309)
        if path == "/robots.txt":
            return 500, html, "error"
        return 200, html, "<html><body>ok</body></html>"
    if host == "127.0.0.9":  # home 404
        return None
    if host.startswith("127.0.1."):  # siti generici per i test di carico
        n = host.rsplit(".", 1)[1]
        pages = {
            "/": f"<html><head><title>Azienda {n} | Home</title></head><body><p>{'Testo. ' * 60}</p>"
                 f"<a href='/contatti'>Contatti</a><a href='/chi-siamo'>Chi siamo</a></body></html>",
            "/contatti": f"<html><body>info@azienda{n}.it - Tel. 091 555 {int(n):04d}"
                         f"<a href='https://www.instagram.com/azienda{n}'>ig</a></body></html>",
            "/chi-siamo": "<html><body>Via Roma 1, 90100 Palermo (PA)</body></html>",
        }
        return (200, html, pages[path]) if path in pages else None
    if host == "127.0.0.10":  # non HTML
        return (200, {"Content-Type": "application/pdf"}, "%PDF-1.4") if path == "/" else None
    return None


SEARX_RESULTS = [
    ("Hotel Alfa Palermo - Sito ufficiale", "127.0.0.2", "/"),
    ("Hotel Alfa | Camere", "127.0.0.2", "/camere"),
    ("SpaCo - SaaS", "127.0.0.6", "/"),
    ("Studio Beta", "127.0.0.7", "/"),
    ("Sito vietato", "127.0.0.3", "/"),
    ("Sito protetto", "127.0.0.4", "/"),
    ("Sito lento", "127.0.0.5", "/"),
    ("Pagina inesistente", "127.0.0.9", "/"),
    ("Booking", None, "https://www.booking.com/hotel/x"),
]


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):  # noqa: N802
        host = self.headers.get("Host", "").split(":")[0]
        path = self.path.split("?")[0]
        if path == "/search" and host == "127.0.0.1":  # finto SearXNG
            port = self.server.server_address[1]
            results = [{"title": t, "url": (f"http://{h}:{port}{p}" if h else p), "content": "demo"}
                       for t, h, p in SEARX_RESULTS]
            page = 1 if "pageno=1&" in self.path + "&" else int(self.path.split("pageno=")[1].split("&")[0])
            if "q=stress" in self.path:  # 120 siti generici, 20 per pagina
                results = [{"title": f"Azienda {i}", "url": f"http://127.0.1.{i}:{port}/", "content": ""}
                           for i in range(1, 121)][(page - 1) * 20: page * 20]
            elif page > 1:
                results = []
            body = json.dumps({"results": results})
            return self._send(200, {"Content-Type": "application/json"}, body)
        res = _site(host, path)
        if res is None:
            return self._send(404, {"Content-Type": "text/html"}, "<html><body>404</body></html>")
        self._send(*res)

    def _send(self, status, headers, body):
        data = body.encode("utf-8")
        try:
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


class SiteServer:
    def __init__(self, port: int = 0):
        if not port:
            with socket.socket() as s:
                s.bind(("127.0.0.1", 0))
                port = s.getsockname()[1]
        self.port = port
        self.httpd = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
        self.httpd.daemon_threads = True

    def url(self, host: str, path: str = "/") -> str:
        return f"http://{host}:{self.port}{path}"

    def __enter__(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    with SiteServer(port) as srv:
        print(f"Siti demo attivi. SearXNG finto: PS_SEARXNG_URL=http://127.0.0.1:{port}")
        threading.Event().wait()
