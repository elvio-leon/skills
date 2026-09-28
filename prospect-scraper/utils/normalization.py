"""Normalizzazione di URL, domini e testi."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit, urlunsplit

_WWW_RE = re.compile(r"^www\d*\.")
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*://", re.I)
_NON_WEB_RE = re.compile(r"^(mailto|tel|callto|sms|fax|skype|whatsapp|javascript|data|file|ftp):", re.I)


def _split(url: str):
    url = (url or "").strip()
    if not url or _NON_WEB_RE.match(url):
        return None
    if url.startswith("//"):
        url = "https:" + url
    elif not _SCHEME_RE.match(url):
        url = "https://" + url
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        return None
    if "@" in parts.netloc:  # credenziali nell'URL: non è un sito da visitare
        return None
    return parts


def _idna(host: str) -> str:
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError:
        return host


def normalize_domain(url_or_domain: str | None) -> str | None:
    """Restituisce il dominio canonico (senza schema, www, porta, path).

    >>> normalize_domain("https://www.hotel-example.it/")
    'hotel-example.it'
    """
    parts = _split(url_or_domain or "")
    if not parts:
        return None
    host = parts.hostname.lower().strip(".")
    host = _idna(host)
    host = _WWW_RE.sub("", host)
    if "." not in host and host != "localhost":
        return None
    return host or None


def normalize_url(url: str | None) -> str | None:
    """URL pulito: schema minuscolo, host minuscolo, niente frammento.

    Mantiene path e query (servono per visitare la pagina).
    """
    parts = _split(url or "")
    if not parts:
        return None
    host = _idna(parts.hostname.lower().strip("."))
    netloc = host
    if parts.port and not (
        (parts.scheme == "http" and parts.port == 80)
        or (parts.scheme == "https" and parts.port == 443)
    ):
        netloc = f"{host}:{parts.port}"
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))


def homepage_url(url: str | None) -> str | None:
    """URL della home del sito (schema + host)."""
    norm = normalize_url(url)
    if not norm:
        return None
    parts = urlsplit(norm)
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


def is_domain_in(domain: str | None, domains: set[str]) -> bool:
    """True se ``domain`` è uno dei domini dati o un loro sottodominio."""
    if not domain:
        return False
    return any(domain == d or domain.endswith("." + d) for d in domains)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(name: str | None) -> str:
    """Chiave di confronto per nomi aziendali (minuscolo, senza accenti/punteggiatura
    e senza forme societarie)."""
    text = unicodedata.normalize("NFKD", clean_text(name).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    text = re.sub(
        r"\b(s ?r ?l ?s?|s ?p ?a|s ?n ?c|s ?a ?s|srl|spa|ltd|llc|gmbh|inc|snc|sas)\b",
        " ",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()
