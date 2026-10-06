"""Esito della qualifica di un'agenzia (dataclass leggera, usata anche dal database)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields

STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_EXCLUDED = "excluded"

_JSON_FIELDS = ("servizi", "verticali", "score_breakdown", "evidence", "pages_used")


@dataclass
class Qualification:
    status: str = STATUS_FAILED          # ok | failed | excluded
    error: str = ""
    is_agency: str = ""                  # si | no | dubbio
    servizi: list[str] = field(default_factory=list)
    servizi_altro: str = ""
    seo_level: str = ""
    servizi_ricorrenti: str = ""
    verticali: list[str] = field(default_factory=list)
    size_signal: str = ""
    blog_status: str = ""
    blog_last_post: str = ""             # data ISO o ""
    note: str = ""
    score: int | None = None
    score_breakdown: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)   # agenzia, seo, ricorrenti, team
    pages_used: list[str] = field(default_factory=list)
    llm_provider: str = ""
    llm_model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    qualified_at: str = ""

    def to_row(self) -> dict:
        """Valori pronti per SQLite (liste e dizionari come JSON)."""
        row = {f.name: getattr(self, f.name) for f in fields(self)}
        for name in _JSON_FIELDS:
            row[name] = json.dumps(row[name], ensure_ascii=False)
        return row

    @classmethod
    def from_row(cls, row: dict) -> "Qualification":
        data = {}
        known = {f.name: f for f in fields(cls)}
        for name, f in known.items():
            value = row.get(name)
            if name in _JSON_FIELDS:
                try:
                    value = json.loads(value) if value else None
                except (TypeError, ValueError):
                    value = None
                value = value if value is not None else ({} if "breakdown" in name or name == "evidence" else [])
            elif value is None:
                value = None if name == "score" else (0 if "tokens" in name else
                                                      0.0 if name in ("cost_usd", "latency_s") else "")
            data[name] = value
        return cls(**data)
