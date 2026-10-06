"""Email del decisore: prima quella nominativa trovata sul sito (verificata), altrimenti l'ipotesi
``nome@dominio`` da verificare. Nessuna verifica SMTP, nessun servizio esterno."""

from __future__ import annotations

import re

from decision_makers.extract import fold
from utils.normalization import registrable_domain


def _compact(name: str) -> str:
    """"Gian Marco" -> "gianmarco", "D'Angelo" -> "dangelo"."""
    return fold(name).replace(" ", "")


def local_patterns(nome: str, cognome: str) -> tuple[list[str], list[str]]:
    """(forme che contengono nome e cognome, forme con solo nome o solo cognome)."""
    n, c = _compact(nome), _compact(cognome)
    if not n or not c:
        return [], []
    first = fold(nome).split()[0]
    i, ci = n[0], c[0]
    strong = []
    for nn in dict.fromkeys([n, first]):
        strong += [f"{nn}.{c}", f"{nn}{c}", f"{nn}_{c}", f"{nn}-{c}", f"{c}.{nn}", f"{c}{nn}",
                   f"{c}_{nn}", f"{nn}.{ci}"]
    strong += [f"{i}.{c}", f"{i}{c}", f"{i}_{c}", f"{c}.{i}", f"{c}{i}"]
    weak = list(dict.fromkeys([n, first, c]))
    return list(dict.fromkeys(strong)), weak


def nominative_email(emails: list[str], nome: str, cognome: str, site_domain: str | None) -> str | None:
    """Email del sito che corrisponde alla persona. Le forme con nome e cognome valgono su qualsiasi
    dominio; quelle con solo nome o solo cognome solo sul dominio dell'agenzia."""
    strong, weak = local_patterns(nome, cognome)
    site = registrable_domain(site_domain)
    candidates = []
    for email in emails:
        email = (email or "").strip().lower()
        if "@" not in email:
            continue
        local, dom = email.rsplit("@", 1)
        local = re.sub(r"\+.*$", "", local)
        if local in strong:
            candidates.append((0, strong.index(local), email))
        elif local in weak and site and registrable_domain(dom) == site:
            candidates.append((1, weak.index(local), email))
    return min(candidates)[2] if candidates else None


def guess_email(nome: str, site_domain: str | None) -> str:
    """Ipotesi più probabile: nome@dominio (da verificare)."""
    site = registrable_domain(site_domain)
    first = _compact(nome)
    return f"{first}@{site}" if first and site else ""
