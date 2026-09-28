"""Deduplicazione dei prospect.

Chiave primaria: dominio normalizzato. Se il dominio manca: nome normalizzato + città.
"""

from __future__ import annotations

from models.prospect import Prospect
from utils.normalization import normalize_name


def dedup_key(domain: str | None, company_name: str | None, city: str | None) -> str | None:
    if domain:
        return f"d:{domain}"
    name = normalize_name(company_name)
    if not name:
        return None
    return f"n:{name}|{normalize_name(city)}"


def merge_prospects(base: Prospect, other: Prospect) -> Prospect:
    """Completa ``base`` con i campi non vuoti di ``other`` (``base`` ha la precedenza)."""
    for field in Prospect.MERGE_FIELDS:
        if not getattr(base, field) and getattr(other, field):
            setattr(base, field, getattr(other, field))
    sources = [s for s in (base.source or "").split(", ") if s]
    for s in (other.source or "").split(", "):
        if s and s not in sources:
            sources.append(s)
    base.source = ", ".join(sources)
    for key, value in (other.raw_data or {}).items():
        base.raw_data.setdefault(key, value)
    return base


def deduplicate(prospects: list[Prospect]) -> list[Prospect]:
    """Unisce i prospect con la stessa chiave mantenendo l'ordine di prima apparizione."""
    unique: dict[str, Prospect] = {}
    for p in prospects:
        key = p.dedup_key
        if key is None:
            continue
        if key in unique:
            merge_prospects(unique[key], p)
        else:
            unique[key] = p
    return list(unique.values())
