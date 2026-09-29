"""Configurazione centrale.

Tutti i parametri operativi stanno qui. Ogni valore può essere sovrascritto
con una variabile d'ambiente con prefisso ``PS_`` (es. ``PS_MAX_WORKERS=3``).
"""

from __future__ import annotations

import os
from pathlib import Path


def _env(name: str, default):
    raw = os.environ.get(f"PS_{name}")
    if raw is None:
        return default
    if isinstance(default, bool):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(default, int):
        return int(raw)
    if isinstance(default, float):
        return float(raw)
    return raw


BASE_DIR = Path(__file__).resolve().parent.parent

# --- Percorsi ---------------------------------------------------------------
# Cartella dei dati: nell'app Mac è ~/Library/Application Support/Prospect Scraper
# (PS_HOME impostata da desktop.py); da sorgente è la cartella del progetto.
DATA_HOME = Path(_env("HOME", str(BASE_DIR)))
DB_PATH = Path(_env("DB_PATH", str(DATA_HOME / "data" / "prospects.db")))
LOG_DIR = Path(_env("LOG_DIR", str(DATA_HOME / "logs")))

# App desktop (finestra nativa): gli export vengono salvati direttamente in EXPORT_DIR.
DESKTOP = _env("DESKTOP", False)
EXPORT_DIR = Path(_env("EXPORT_DIR", str(Path.home() / "Downloads")))

# --- Ricerca ----------------------------------------------------------------
MAX_RESULTS = _env("MAX_RESULTS", 100)          # tetto massimo selezionabile in UI
DEFAULT_RESULTS = _env("DEFAULT_RESULTS", 20)
RESULT_OPTIONS = [10, 20, 30, 50, 100]
DEFAULT_LOCATION = _env("DEFAULT_LOCATION", "Italia")
DEFAULT_PHONE_REGION = _env("DEFAULT_PHONE_REGION", "IT")

# SearXNG (opzionale): URL di un'istanza propria con formato JSON abilitato,
# es. http://localhost:8888 . Se vuoto il provider è disattivato.
SEARXNG_URL = _env("SEARXNG_URL", "")

NOMINATIM_URL = _env("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
OVERPASS_URL = _env("OVERPASS_URL", "https://overpass-api.de/api/interpreter")
WIKIDATA_API_URL = _env("WIKIDATA_API_URL", "https://www.wikidata.org/w/api.php")
OVERPASS_TIMEOUT = _env("OVERPASS_TIMEOUT", 90)
NOMINATIM_MIN_INTERVAL = 1.1   # policy Nominatim: max 1 richiesta/secondo

# --- Crawling / enrichment ----------------------------------------------------
MAX_PAGES_PER_DOMAIN = _env("MAX_PAGES_PER_DOMAIN", 10)
REQUEST_TIMEOUT = _env("REQUEST_TIMEOUT", 10)
MAX_WORKERS = _env("MAX_WORKERS", 5)
REQUEST_DELAY = _env("REQUEST_DELAY", 1.0)        # pausa minima tra richieste allo stesso host
MAX_RETRIES = _env("MAX_RETRIES", 2)
DOMAIN_TIME_BUDGET = _env("DOMAIN_TIME_BUDGET", 90)  # secondi massimi per dominio
MAX_PAGE_BYTES = _env("MAX_PAGE_BYTES", 3_000_000)
RESPECT_ROBOTS = _env("RESPECT_ROBOTS", True)
# Domini arricchiti da meno di N giorni vengono riusati dalla cache del DB.
REENRICH_AFTER_DAYS = _env("REENRICH_AFTER_DAYS", 7)

# Playwright: usato solo se installato e se la home sembra richiedere JavaScript.
USE_PLAYWRIGHT = _env("USE_PLAYWRIGHT", True)
PLAYWRIGHT_TIMEOUT_MS = _env("PLAYWRIGHT_TIMEOUT_MS", 20000)
PLAYWRIGHT_EXECUTABLE = _env("PLAYWRIGHT_EXECUTABLE", "")  # opzionale: Chromium già installato
JS_MIN_TEXT_CHARS = 200   # sotto questa soglia di testo visibile la pagina è "vuota"

# User-agent identificabile. Aggiungi un contatto con PS_CONTACT se vuoi.
CONTACT = _env("CONTACT", "")
USER_AGENT = (
    "ProspectScraper/1.0 (personal B2B research tool; low-rate; respects robots.txt"
    + (f"; contact: {CONTACT}" if CONTACT else "")
    + ")"
)
ROBOTS_USER_AGENT = "ProspectScraper"

# --- Pagine da cercare nel sito ---------------------------------------------
# Parole chiave (in URL o anchor text) con priorità: più basso = più importante.
PAGE_KEYWORDS: dict[str, int] = {
    "contatti": 0, "contattaci": 0, "contact": 0, "contacts": 0, "contact-us": 0,
    "kontakt": 0, "contacto": 0, "scrivici": 0, "get in touch": 0, "reach us": 0,
    "richiedi informazioni": 1, "chi sono": 1, "la nostra storia": 2, "our story": 2, "dove-siamo": 1, "dove siamo": 1, "where": 2,
    "chi-siamo": 1, "chi siamo": 1, "about": 1, "about-us": 1, "azienda": 1,
    "company": 1, "team": 2, "staff": 3, "impressum": 1, "legal": 3,
    "note-legali": 3, "note legali": 3, "imprint": 1, "info": 2,
    "privacy": 4, "lavora-con-noi": 5, "press": 4, "stampa": 4,
}
# Percorsi provati "alla cieca" solo se i link non rivelano pagine utili.
FALLBACK_PATHS = ["/contatti", "/contact", "/chi-siamo", "/about"]
MAX_FALLBACK_PROBES = 2

# --- Domini da non trattare come sito aziendale -------------------------------
# Se una ricerca restituisce questi domini non sono il sito del prospect
# (portali, directory, social, marketplace).
NON_COMPANY_DOMAINS = {
    "booking.com", "tripadvisor.com", "tripadvisor.it", "expedia.com", "expedia.it",
    "hotels.com", "trivago.it", "trivago.com", "airbnb.com", "airbnb.it", "agoda.com",
    "google.com", "google.it", "goo.gl", "maps.app.goo.gl", "wikipedia.org",
    "wikidata.org", "facebook.com", "instagram.com", "linkedin.com", "twitter.com",
    "x.com", "youtube.com", "tiktok.com", "pinterest.com", "paginegialle.it",
    "paginebianche.it", "yelp.com", "yelp.it", "amazon.com", "amazon.it",
    "ebay.it", "ebay.com", "crunchbase.com", "glassdoor.com", "indeed.com",
    "virgilio.it", "subito.it", "trustpilot.com", "wa.me", "whatsapp.com",
    "linktr.ee", "t.me", "hrs.com", "lastminute.com", "venere.com",
}

# Prefissi email chiaramente tecnici da escludere.
TECHNICAL_EMAIL_PREFIXES = (
    "noreply", "no-reply", "no_reply", "donotreply", "do-not-reply", "do_not_reply",
    "mailer-daemon", "bounce", "bounces", "postmaster",
)
# Domini email segnaposto o di servizi tecnici.
JUNK_EMAIL_DOMAINS = {
    "example.com", "example.org", "example.it", "domain.com", "dominio.it",
    "email.com", "yourdomain.com", "tuodominio.it", "sentry.io", "wixpress.com",
    "sentry-next.wixpress.com", "sentry.wixpress.com", "ingest.sentry.io",
    "mysite.com", "company.com", "test.com", "esempio.it",
}
# Prefissi email preferiti come email principale (ordine = priorità).
PREFERRED_EMAIL_PREFIXES = (
    "info", "commerciale", "sales", "vendite", "marketing", "hello", "ciao",
    "contatti", "contact", "contacts", "booking", "reservations", "prenotazioni",
    "reception", "direzione", "office", "segreteria", "redazione", "business",
)
LOW_PRIORITY_EMAIL_PREFIXES = (
    "privacy", "dpo", "gdpr", "legal", "pec", "amministrazione", "webmaster",
    "admin", "hr", "careers", "jobs", "lavoro", "cv", "fatture", "billing",
)
