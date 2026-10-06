"""Accesso al database SQLite locale."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import settings
from decision_makers.models import OUTREACH_STATES, DecisionMaker
from models.prospect import Prospect
from qualify.models import Qualification
from utils.deduplication import dedup_key

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

PROSPECT_COLUMNS = [
    "company_name", "domain", "website", "category", "country", "region", "city", "address",
    "postal_code", "vat_id", "phone", "phones", "phone_raw", "email", "emails", "linkedin",
    "instagram", "facebook", "youtube", "twitter", "page_title", "description", "source",
    "source_url", "search_query", "status", "error_message", "raw_data", "first_seen",
    "last_seen", "enriched_at",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or settings.DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- prospect -------------------------------------------------------------
    @staticmethod
    def _row_to_prospect(row: sqlite3.Row) -> Prospect:
        data = dict(row)
        data.pop("dedup_key", None)
        try:
            data["raw_data"] = json.loads(data.get("raw_data") or "{}")
        except ValueError:
            data["raw_data"] = {}
        return Prospect(**{k: ("" if v is None and k not in ("id", "domain", "first_seen",
                                                             "last_seen", "enriched_at") else v)
                           for k, v in data.items()})

    def find_existing(self, p: Prospect) -> Prospect | None:
        """Prospect già salvato con la stessa chiave. Se il nuovo ha un dominio, cerca
        anche un record senza dominio con lo stesso nome+città (e lo "promuove")."""
        key = p.dedup_key
        if not key:
            return None
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM prospects WHERE dedup_key = ?", (key,)).fetchone()
            if row is None and p.domain and p.company_name:
                name_key = dedup_key(None, p.company_name, p.city)
                row = conn.execute(
                    "SELECT * FROM prospects WHERE dedup_key = ? AND domain IS NULL", (name_key,)
                ).fetchone()
        return self._row_to_prospect(row) if row else None

    def save(self, p: Prospect) -> int:
        """Inserisce o aggiorna (per id). Restituisce l'id."""
        now = now_iso()
        p.first_seen = p.first_seen or now
        p.last_seen = now
        values = {c: getattr(p, c) for c in PROSPECT_COLUMNS}
        values["raw_data"] = json.dumps(p.raw_data or {}, ensure_ascii=False, default=str)
        values["dedup_key"] = p.dedup_key
        with self.connect() as conn:
            if p.id:
                sets = ", ".join(f"{c} = :{c}" for c in values)
                conn.execute(f"UPDATE prospects SET {sets} WHERE id = :id", {**values, "id": p.id})
            else:
                cols = ", ".join(values)
                params = ", ".join(f":{c}" for c in values)
                cur = conn.execute(f"INSERT INTO prospects ({cols}) VALUES ({params})", values)
                p.id = cur.lastrowid
        return p.id

    def get(self, prospect_id: int) -> Prospect | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM prospects WHERE id = ?", (prospect_id,)).fetchone()
        return self._row_to_prospect(row) if row else None

    def list_prospects(self, ids: list[int] | None = None, statuses: list[str] | None = None,
                       with_website: bool = False, limit: int | None = None) -> list[Prospect]:
        sql, params = "SELECT * FROM prospects WHERE 1=1", []
        if ids is not None:
            if not ids:
                return []
            sql += f" AND id IN ({','.join('?' * len(ids))})"
            params += ids
        if statuses:
            sql += f" AND status IN ({','.join('?' * len(statuses))})"
            params += statuses
        if with_website:
            sql += " AND website IS NOT NULL AND website != ''"
        sql += " ORDER BY id"
        if limit:
            sql += " LIMIT ?"
            params.append(limit)
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_prospect(r) for r in rows]

    def recently_enriched(self, domain: str, days: int | None = None) -> Prospect | None:
        days = settings.REENRICH_AFTER_DAYS if days is None else days
        if not domain or days <= 0:
            return None
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(microsecond=0).isoformat()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM prospects WHERE domain = ? AND status = 'enriched' AND enriched_at >= ?",
                (domain, cutoff),
            ).fetchone()
        return self._row_to_prospect(row) if row else None

    def delete(self, ids: list[int]) -> None:
        if not ids:
            return
        with self.connect() as conn:
            conn.execute(f"DELETE FROM prospects WHERE id IN ({','.join('?' * len(ids))})", ids)

    def count(self) -> int:
        with self.connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]

    # --- runs -----------------------------------------------------------------
    def start_run(self, **fields) -> int:
        fields = {**fields, "started_at": now_iso()}
        cols = ", ".join(fields)
        with self.connect() as conn:
            cur = conn.execute(f"INSERT INTO runs ({cols}) VALUES ({', '.join('?' * len(fields))})",
                               list(fields.values()))
            return cur.lastrowid

    def finish_run(self, run_id: int, **fields) -> None:
        fields = {**fields, "finished_at": now_iso()}
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.connect() as conn:
            conn.execute(f"UPDATE runs SET {sets} WHERE id = ?", [*fields.values(), run_id])

    def link_run(self, run_id: int, prospect_id: int) -> None:
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO run_prospects (run_id, prospect_id) VALUES (?, ?)",
                         (run_id, prospect_id))

    def run_prospect_ids(self, run_id: int) -> list[int]:
        with self.connect() as conn:
            rows = conn.execute("SELECT prospect_id FROM run_prospects WHERE run_id = ? ORDER BY prospect_id",
                                (run_id,)).fetchall()
        return [r[0] for r in rows]

    def list_runs(self, limit: int = 200) -> list[dict]:
        """Ricerche salvate (più recenti prima) con il numero di prospect collegati."""
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT r.*, COUNT(rp.prospect_id) AS n_prospects
                   FROM runs r JOIN run_prospects rp ON rp.run_id = r.id
                   GROUP BY r.id ORDER BY r.id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # --- qualifica agenzie ------------------------------------------------------
    def save_qualification(self, prospect_id: int, run_id: int | None, q: Qualification) -> None:
        """Inserisce o sostituisce la qualifica del prospect."""
        row = {**q.to_row(), "prospect_id": prospect_id, "run_id": run_id}
        cols = ", ".join(row)
        with self.connect() as conn:
            conn.execute(f"INSERT OR REPLACE INTO agency_qualifications ({cols}) "
                         f"VALUES ({', '.join(':' + c for c in row)})", row)

    def get_qualifications(self, ids: list[int]) -> dict[int, Qualification]:
        if not ids:
            return {}
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM agency_qualifications WHERE prospect_id IN ({','.join('?' * len(ids))})",
                list(ids)).fetchall()
        return {r["prospect_id"]: Qualification.from_row(dict(r)) for r in rows}

    # --- decisori e outreach ------------------------------------------------------
    def save_decision_maker(self, prospect_id: int, dm: DecisionMaker) -> None:
        row = {**dm.to_row(), "prospect_id": prospect_id}
        cols = ", ".join(row)
        with self.connect() as conn:
            conn.execute(f"INSERT OR REPLACE INTO decision_makers ({cols}) "
                         f"VALUES ({', '.join(':' + c for c in row)})", row)

    def get_decision_makers(self, ids: list[int]) -> dict[int, DecisionMaker]:
        if not ids:
            return {}
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM decision_makers WHERE prospect_id IN ({','.join('?' * len(ids))})",
                list(ids)).fetchall()
        return {r["prospect_id"]: DecisionMaker.from_row(dict(r)) for r in rows}

    def set_outreach(self, prospect_id: int, stato: str) -> None:
        if stato not in OUTREACH_STATES:
            raise ValueError(f"stato outreach non valido: {stato}")
        with self.connect() as conn:
            conn.execute("INSERT OR REPLACE INTO outreach (prospect_id, stato, updated_at) VALUES (?, ?, ?)",
                         (prospect_id, stato, now_iso()))

    def get_outreach(self, ids: list[int]) -> dict[int, str]:
        if not ids:
            return {}
        with self.connect() as conn:
            rows = conn.execute(
                f"SELECT prospect_id, stato FROM outreach WHERE prospect_id IN ({','.join('?' * len(ids))})",
                list(ids)).fetchall()
        return {r["prospect_id"]: r["stato"] for r in rows}
