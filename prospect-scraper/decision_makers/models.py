"""Esito della ricerca del decisore di un'agenzia (dataclass leggera, usata anche dal database)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields

STATUS_FOUND = "trovato"
STATUS_NOT_FOUND = "non_trovato"
STATUS_FAILED = "fallito"

EMAIL_SITE = "sito"
EMAIL_GUESS = "ipotesi"

CONF_HIGH, CONF_MEDIUM = "alta", "media"
LINKEDIN_NOT_FOUND = "non trovato"
LINKEDIN_NOT_SEARCHED = "non cercato"

OUTREACH_STATES = ["da contattare", "contattato", "risposto", "call", "no"]
OUTREACH_DEFAULT = OUTREACH_STATES[0]

_JSON_FIELDS = ("pages_used",)
_INT_FIELDS = ("input_tokens", "output_tokens", "web_calls")
_FLOAT_FIELDS = ("cost_usd", "latency_s")


@dataclass
class DecisionMaker:
    status: str = STATUS_FAILED          # trovato | non_trovato | fallito
    error: str = ""
    nome: str = ""
    cognome: str = ""
    ruolo: str = ""
    source_url: str = ""                 # pagina del sito in cui compare
    evidence: str = ""                   # citazione letterale dal sito
    linkedin_url: str = ""
    linkedin_title: str = ""             # titolo del risultato di ricerca (unica cosa letta)
    linkedin_confidence: str = ""        # alta | media | non trovato | non cercato (motivo)
    email: str = ""
    email_source: str = ""               # sito | ipotesi
    email_verified: bool = False         # True solo se trovata sul sito
    pages_used: list[str] = field(default_factory=list)
    llm_provider: str = ""
    llm_model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    web_calls: int = 0                   # ricerche web usate (crediti)
    found_at: str = ""

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.nome, self.cognome) if p)

    def to_row(self) -> dict:
        row = {f.name: getattr(self, f.name) for f in fields(self)}
        for name in _JSON_FIELDS:
            row[name] = json.dumps(row[name], ensure_ascii=False)
        row["email_verified"] = int(bool(row["email_verified"]))
        return row

    @classmethod
    def from_row(cls, row: dict) -> "DecisionMaker":
        data = {}
        for f in fields(cls):
            value = row.get(f.name)
            if f.name in _JSON_FIELDS:
                try:
                    value = json.loads(value) if value else []
                except (TypeError, ValueError):
                    value = []
            elif f.name == "email_verified":
                value = bool(value)
            elif f.name in _INT_FIELDS:
                value = int(value or 0)
            elif f.name in _FLOAT_FIELDS:
                value = float(value or 0.0)
            elif value is None:
                value = ""
            data[f.name] = value
        return cls(**data)
