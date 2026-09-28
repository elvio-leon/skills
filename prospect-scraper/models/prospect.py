"""Modello dati del prospect."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, ClassVar

from utils.normalization import normalize_domain

STATUS_FOUND = "found"            # trovato in ricerca, non ancora arricchito
STATUS_NO_WEBSITE = "no_website"  # nessun sito associabile: niente enrichment
STATUS_ENRICHED = "enriched"
STATUS_FAILED = "failed"


@dataclass
class Prospect:
    company_name: str = ""
    domain: str | None = None
    website: str = ""
    category: str = ""
    country: str = ""
    region: str = ""
    city: str = ""
    address: str = ""
    postal_code: str = ""
    vat_id: str = ""
    phone: str = ""
    phones: str = ""          # tutti i numeri (E.164), separati da "; "
    phone_raw: str = ""       # formato originale del telefono principale
    email: str = ""
    emails: str = ""          # tutte le email, separate da "; "
    linkedin: str = ""
    instagram: str = ""
    facebook: str = ""
    youtube: str = ""
    twitter: str = ""
    page_title: str = ""
    description: str = ""
    source: str = ""
    source_url: str = ""
    search_query: str = ""
    status: str = STATUS_FOUND
    error_message: str = ""
    raw_data: dict[str, Any] = field(default_factory=dict)
    id: int | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    enriched_at: str | None = None

    # Campi che la deduplicazione completa quando vuoti.
    MERGE_FIELDS: ClassVar[tuple[str, ...]] = (
        "company_name", "website", "category", "country", "region", "city",
        "address", "postal_code", "vat_id", "phone", "phones", "phone_raw",
        "email", "emails", "linkedin", "instagram", "facebook", "youtube",
        "twitter", "page_title", "description", "source_url", "search_query",
    )

    def __post_init__(self):
        if self.website and not self.domain:
            self.domain = normalize_domain(self.website)

    @property
    def dedup_key(self) -> str | None:
        from utils.deduplication import dedup_key

        return dedup_key(self.domain, self.company_name, self.city)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
