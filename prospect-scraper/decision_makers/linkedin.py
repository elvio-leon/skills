"""Profilo LinkedIn personale del decisore dai SOLI risultati di una ricerca web (URL e titolo).

Le pagine linkedin.com non vengono mai aperte (lo impedisce anche ``HttpClient``): una ricerca
``"Nome Cognome" "Agenzia" site:linkedin.com/in``, poi il primo risultato che è un profilo
``/in/`` e il cui titolo contiene il cognome. Confidenza "alta" se il titolo contiene anche il
nome dell'agenzia o il ruolo, altrimenti "media".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from decision_makers.extract import appears_in, fold
from decision_makers.models import CONF_HIGH, CONF_MEDIUM
from scrapers.http import describe_exception
from scrapers.web_search.base import WebSearchProvider
from utils.normalization import registrable_domain

MAX_RESULTS = 5
ROLE_WORDS = ("ceo", "founder", "cofounder", "co founder", "fondatore", "fondatrice", "titolare",
              "owner", "managing director", "amministratore", "presidente", "president", "partner",
              "socio", "direttore", "general manager", "md")
# parole che non identificano un'agenzia (non bastano per dire "il titolo contiene l'agenzia")
GENERIC_WORDS = {"agenzia", "agency", "web", "digital", "marketing", "comunicazione", "studio", "srl",
                 "s", "r", "l", "spa", "snc", "sas", "di", "e", "the", "and", "group", "italia",
                 "italy", "media", "design", "creative", "communication", "consulting", "home",
                 "homepage", "benvenuti", "welcome", "sito", "ufficiale", "il", "la", "lo", "le", "srls"}
_TITLE_SEPARATORS = re.compile(r"\s+[|–—:·•»-]\s+")


@dataclass
class LinkedInMatch:
    url: str = ""
    title: str = ""
    confidence: str = ""        # alta | media | "" (non trovato)
    calls: int = 0
    query: str = ""
    error: str = ""


def agency_name(company: str, domain: str | None) -> str:
    """Nome dell'agenzia da usare nella ricerca: il primo pezzo "significativo" del nome salvato
    (spesso è il titolo della home, es. "Home - Agenzia Rossi | Web Marketing")."""
    for part in _TITLE_SEPARATORS.split(company or ""):
        part = part.strip()
        if part and set(fold(part).split()) - GENERIC_WORDS:
            return part[:60]
    label = (registrable_domain(domain) or domain or "").split(".")[0]
    return label


def build_query(nome: str, cognome: str, company: str) -> str:
    name = f'"{nome} {cognome}"'
    return f'{name} "{company}" site:linkedin.com/in' if company else f"{name} site:linkedin.com/in"


def profile_url(url: str) -> str | None:
    """URL pulito se è un profilo personale linkedin.com/in/..., altrimenti None."""
    parts = urlsplit((url or "").strip())
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not (host == "linkedin.com" or host.endswith(".linkedin.com")):
        return None
    if not re.match(r"^/in/[^/]+", parts.path):
        return None
    return urlunsplit(("https", host, parts.path.rstrip("/"), "", ""))


def _mentions_agency(title_folded: str, company: str, domain: str | None) -> bool:
    words = [w for w in fold(company).split() if w not in GENERIC_WORDS and len(w) >= 3]
    if words and all(f" {w} " in f" {title_folded} " for w in words):
        return True
    label = fold((registrable_domain(domain) or "").split(".")[0]).replace(" ", "")
    return len(label) >= 4 and label in title_folded.replace(" ", "")


def _mentions_role(title_folded: str, ruolo: str) -> bool:
    hay = f" {title_folded} "
    if ruolo and appears_in(ruolo, title_folded):
        return True
    return any(f" {w} " in hay for w in ROLE_WORDS)


def pick_profile(results, cognome: str, company: str, ruolo: str,
                 domain: str | None) -> tuple[str, str, str] | None:
    """(url, titolo, confidenza) del primo profilo il cui titolo contiene il cognome, oppure None."""
    for r in results:
        url = profile_url(getattr(r, "url", ""))
        title = (getattr(r, "title", "") or "").strip()
        if not url or not title:
            continue
        # titolo tipico: "Nome Cognome - Ruolo - Azienda | LinkedIn". Il cognome va cercato nella parte
        # del nome (spesso è anche nel nome dell'agenzia: "Agenzia Rossi"), agenzia e ruolo nel resto.
        name_part, _, rest = _TITLE_SEPARATORS.sub("\x00", title, count=1).partition("\x00")
        if not appears_in(cognome, fold(name_part)):
            continue
        rest_folded = fold(rest)
        high = _mentions_agency(rest_folded, company, domain) or _mentions_role(rest_folded, ruolo)
        return url, title[:200], CONF_HIGH if high else CONF_MEDIUM
    return None


def find_linkedin(provider: WebSearchProvider, nome: str, cognome: str, company: str, ruolo: str,
                  domain: str | None) -> LinkedInMatch:
    """Una ricerca web; non solleva mai (l'errore finisce in ``error``)."""
    match = LinkedInMatch(query=build_query(nome, cognome, company))
    try:
        match.calls = 1
        results = provider.search_profiles(match.query, MAX_RESULTS, "linkedin.com")
    except Exception as exc:  # noqa: BLE001
        match.error = f"ricerca LinkedIn non riuscita: {describe_exception(exc)}"
        return match
    found = pick_profile(results, cognome, company, ruolo, domain)
    if found:
        match.url, match.title, match.confidence = found
    return match
