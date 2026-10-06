"""Schema JSON unico per tutti i provider AI + validazione con pydantic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

SERVIZI = ["siti_web", "ecommerce", "social", "adv", "branding", "contenuti", "seo", "app",
           "video_foto", "grafica", "email_marketing", "consulenza_marketing", "altro"]
IS_AGENCY = ["si", "no", "dubbio"]
SEO_LEVELS = ["assente", "accennata", "strutturata"]
SI_NO = ["si", "no"]
SIZES = ["1", "2-5", "6-20", "20+", "non determinabile"]

MAX_EVIDENCE = 300
MAX_NOTE = 400
MAX_VERTICALI = 8

# Solo parole chiave accettate dalle modalità "strict" dei provider: niente minLength, pattern, format...
SCHEMA: dict = {
    "type": "object",
    "properties": {
        "is_agency": {"type": "string", "enum": IS_AGENCY},
        "is_agency_evidence": {"type": "string"},
        "servizi": {"type": "array", "items": {"type": "string", "enum": SERVIZI}},
        "servizi_altro": {"type": "string"},
        "seo_level": {"type": "string", "enum": SEO_LEVELS},
        "seo_evidence": {"type": "string"},
        "servizi_ricorrenti": {"type": "string", "enum": SI_NO},
        "ricorrenti_evidence": {"type": "string"},
        "verticali": {"type": "array", "items": {"type": "string"}},
        "size_signal": {"type": "string", "enum": SIZES},
        "size_evidence": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["is_agency", "is_agency_evidence", "servizi", "servizi_altro", "seo_level",
                 "seo_evidence", "servizi_ricorrenti", "ricorrenti_evidence", "verticali",
                 "size_signal", "size_evidence", "note"],
    "additionalProperties": False,
}


class AgencyAnalysis(BaseModel):
    """Risposta attesa dal modello (stessi campi dello schema)."""

    model_config = ConfigDict(extra="ignore")

    is_agency: Literal["si", "no", "dubbio"]
    is_agency_evidence: str
    servizi: list[Literal["siti_web", "ecommerce", "social", "adv", "branding", "contenuti", "seo",
                          "app", "video_foto", "grafica", "email_marketing",
                          "consulenza_marketing", "altro"]]
    servizi_altro: str
    seo_level: Literal["assente", "accennata", "strutturata"]
    seo_evidence: str
    servizi_ricorrenti: Literal["si", "no"]
    ricorrenti_evidence: str
    verticali: list[str]
    size_signal: Literal["1", "2-5", "6-20", "20+", "non determinabile"]
    size_evidence: str
    note: str


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def validate_analysis(data: object) -> dict:
    """Valida (solleva ``pydantic.ValidationError``/``ValueError``) e normalizza la risposta:
    stringhe di prova a 300 caratteri, nota a 400, al più 8 verticali, servizi senza doppioni."""
    if not isinstance(data, dict):
        raise ValueError("la risposta non è un oggetto JSON")
    out = AgencyAnalysis.model_validate(data).model_dump()
    for key in ("is_agency_evidence", "seo_evidence", "ricorrenti_evidence", "size_evidence",
                "servizi_altro"):
        out[key] = _clip(out[key], MAX_EVIDENCE)
    out["note"] = _clip(out["note"], MAX_NOTE)
    out["servizi"] = list(dict.fromkeys(out["servizi"]))
    verticali = [_clip(v, 80) for v in out["verticali"] if v and v.strip()]
    out["verticali"] = list(dict.fromkeys(verticali))[:MAX_VERTICALI]
    return out
