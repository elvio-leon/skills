"""Estrazione di email e numeri di telefono da pagine HTML."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote

import phonenumbers
from bs4 import BeautifulSoup

from config import settings

# --- Email --------------------------------------------------------------------

EMAIL_RE = re.compile(
    r"(?<![\w.+-])([a-z0-9][a-z0-9._%+-]{0,63}@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,24})(?![\w-])",
    re.I,
)
_FILE_EXT = re.compile(r"\.(png|jpe?g|gif|svg|webp|avif|bmp|ico|css|js|json|woff2?|ttf|mp4|pdf)$", re.I)


def clean_email(value: str) -> str | None:
    email = unquote(value or "").strip().strip(".,;:()[]<>\"'").lower()
    email = email.split("?")[0]
    if email.startswith("mailto:"):
        email = email[7:]
    m = EMAIL_RE.fullmatch(email)
    if not m:
        return None
    local, _, domain = email.rpartition("@")
    if _FILE_EXT.search(email) or re.search(r"@\d+x\.", email):   # es. logo@2x.png
        return None
    if domain in settings.JUNK_EMAIL_DOMAINS or domain.endswith(".wixpress.com"):
        return None
    if re.fullmatch(r"[0-9a-f]{16,}", local):   # hash tecnici (es. Sentry)
        return None
    if local.startswith(settings.TECHNICAL_EMAIL_PREFIXES):
        return None
    return email


def extract_emails(soup: BeautifulSoup, html: str) -> list[str]:
    """Email da link mailto:, testo visibile e attributi HTML. Ordine di apparizione."""
    found: list[str] = []

    def add(value):
        email = clean_email(value)
        if email and email not in found:
            found.append(email)

    for a in soup.select('a[href^="mailto:" i]'):
        for part in a.get("href", "")[7:].split("?")[0].split(","):
            add(part)
    for m in EMAIL_RE.finditer(soup.get_text(" ")):
        add(m.group(1))
    for m in EMAIL_RE.finditer(unquote(html)):
        add(m.group(1))
    return found


def email_rank(email: str, site_domain: str | None) -> tuple:
    """Chiave di ordinamento: prima il dominio del sito, poi i prefissi commerciali."""
    local, _, domain = email.partition("@")
    same = bool(site_domain) and (domain == site_domain or domain.endswith("." + site_domain)
                                  or site_domain.endswith("." + domain))
    pec = "pec" in domain.split(".") or domain.startswith(("pec.", "legalmail.")) or ".pec." in domain
    local_base = re.split(r"[._+-]", local)[0]
    if local_base in settings.PREFERRED_EMAIL_PREFIXES:
        prefix = settings.PREFERRED_EMAIL_PREFIXES.index(local_base)
    elif local_base in settings.LOW_PRIORITY_EMAIL_PREFIXES:
        prefix = 200
    else:
        prefix = 100
    return (pec, not same, prefix)


def sort_emails(emails: list[str], site_domain: str | None) -> list[str]:
    return sorted(emails, key=lambda e: email_rank(e, site_domain))


# --- Telefono -----------------------------------------------------------------

@dataclass
class Phone:
    e164: str
    international: str
    raw: str
    from_tel_link: bool = False


# Numeri preceduti da queste parole non sono telefoni (P.IVA, CF, REA, IBAN, CAP...).
_NOT_PHONE_CONTEXT = re.compile(
    r"(p\.?\s?iva|partita\s+iva|vat|c\.?\s?f\.?|codice\s+fiscale|fiscal|rea|iban|cap\.?|"
    r"capitale|c\.?c\.?i\.?a\.?a|n\.?\s?iscr|registro|reg\.?\s?imp|cod\.?|id|fax)\s*[:.nr°º#]*\s*(it)?\s*$",
    re.I,
)


def _parse(raw: str, region: str) -> phonenumbers.PhoneNumber | None:
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException:
        return None
    return num if phonenumbers.is_valid_number(num) else None


def _make(num, raw: str, tel: bool) -> Phone:
    return Phone(
        e164=phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164),
        international=phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        raw=raw.strip(),
        from_tel_link=tel,
    )


def extract_phones(soup: BeautifulSoup, text: str | None = None, region: str | None = None) -> list[Phone]:
    """Telefoni da link tel: (affidabili) e dal testo visibile (validati con libphonenumber)."""
    region = region or settings.DEFAULT_PHONE_REGION
    phones: dict[str, Phone] = {}
    for a in soup.select('a[href^="tel:" i], a[href^="callto:" i]'):
        raw = unquote(a.get("href", "").split(":", 1)[1])
        num = _parse(raw, region)
        if num:
            p = _make(num, a.get_text(" ", strip=True) or raw, True)
            phones.setdefault(p.e164, p)
    text = text if text is not None else soup.get_text(" ")
    try:
        matcher = phonenumbers.PhoneNumberMatcher(text, region, leniency=phonenumbers.Leniency.VALID,
                                                  max_tries=200)
        for match in matcher:
            before = text[max(0, match.start - 30):match.start]
            if _NOT_PHONE_CONTEXT.search(before):
                continue
            digits = re.sub(r"\D", "", match.raw_string)
            if len(digits) == 11 and digits.startswith("0") and " " not in match.raw_string.strip() \
                    and "-" not in match.raw_string and "." not in match.raw_string:
                continue  # 11 cifre attaccate con lo 0: tipico di P.IVA/codici, non di telefoni
            p = _make(match.number, match.raw_string, False)
            phones.setdefault(p.e164, p)
    except Exception:  # noqa: BLE001 - il matcher non deve mai bloccare il crawling
        pass
    # prima quelli dei link tel:, poi in ordine di apparizione
    return sorted(phones.values(), key=lambda p: not p.from_tel_link)


def normalize_phone(raw: str, region: str | None = None) -> Phone | None:
    """Normalizza un numero già noto (es. da OpenStreetMap). None se non valido."""
    if not raw:
        return None
    first = re.split(r"[;,/]| - ", raw)[0]
    num = _parse(first, region or settings.DEFAULT_PHONE_REGION)
    return _make(num, first, True) if num else None
