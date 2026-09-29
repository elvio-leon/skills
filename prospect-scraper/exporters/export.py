"""Export dei prospect in CSV (UTF-8) e XLSX (intestazioni leggibili, filtri,
prima riga bloccata, larghezze colonne ragionevoli)."""

from __future__ import annotations

import io
import re

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from models.prospect import Prospect

# (campo, intestazione leggibile) nell'ordine di esportazione
COLUMNS: list[tuple[str, str]] = [
    ("company_name", "Company"), ("website", "Website"), ("domain", "Domain"),
    ("country", "Country"), ("region", "Region"), ("city", "City"), ("address", "Address"),
    ("postal_code", "Postal code"), ("category", "Category"), ("phone", "Phone"),
    ("phones", "All phones"), ("email", "Email"), ("emails", "All emails"),
    ("linkedin", "LinkedIn"), ("instagram", "Instagram"), ("facebook", "Facebook"),
    ("youtube", "YouTube"), ("twitter", "X / Twitter"), ("vat_id", "VAT ID"),
    ("description", "Description"), ("source", "Source"), ("source_url", "Source URL"),
    ("search_query", "Search query"), ("status", "Status"), ("error_message", "Error"),
    ("first_seen", "First seen"), ("last_seen", "Last seen"), ("id", "ID"),
]
LABELS = dict(COLUMNS)
URL_LABELS = {"Website", "LinkedIn", "Instagram", "Facebook", "YouTube", "X / Twitter", "Source URL"}

_PHONE_LIKE = re.compile(r"^\+[\d\s().;/-]+$")


def prospects_to_dataframe(prospects: list[Prospect]) -> pd.DataFrame:
    rows = [{label: getattr(p, field) or "" for field, label in COLUMNS} for p in prospects]
    df = pd.DataFrame(rows, columns=[label for _, label in COLUMNS])
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").astype("Int64")
    return df


def _safe_cell(value):
    """Evita che un testo raccolto dal web venga interpretato come formula (CSV injection)."""
    if not isinstance(value, str) or not value:
        return value
    if value[0] in ("=", "@", "\t", "\r") or (value[0] in "+-" and not _PHONE_LIKE.match(value)):
        return "'" + value
    return value


def _sanitize(df: pd.DataFrame) -> pd.DataFrame:
    # vale sia per dtype object (pandas 2) sia per dtype str (pandas 3)
    return df.apply(lambda col: col if pd.api.types.is_numeric_dtype(col) else col.map(_safe_cell))


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    # UTF-8 con BOM: Excel riconosce correttamente accenti e caratteri speciali.
    return _sanitize(df).to_csv(index=False).encode("utf-8-sig")


def to_xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Prospects") -> bytes:
    return to_xlsx_multi_bytes({sheet_name: df})


def to_xlsx_multi_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Un file XLSX con un foglio per ogni DataFrame (es. un foglio per ricerca)."""
    wb = Workbook()
    wb.remove(wb.active)
    used: set[str] = set()
    for name, df in sheets.items():
        _write_sheet(wb.create_sheet(_sheet_title(name, used)), _sanitize(df))
    if not wb.worksheets:
        _write_sheet(wb.create_sheet("Prospects"), _sanitize(pd.DataFrame(columns=list(LABELS.values()))))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _sheet_title(name: str, used: set[str]) -> str:
    """Nome foglio valido per Excel: max 31 caratteri, senza []:*?/\\ e unico."""
    base = re.sub(r"[\[\]:*?/\\]", " ", name or "Prospects").strip()[:31] or "Prospects"
    title, n = base, 2
    while title.lower() in used:
        suffix = f" ({n})"
        title, n = base[: 31 - len(suffix)] + suffix, n + 1
    used.add(title.lower())
    return title


def _write_sheet(ws, df: pd.DataFrame) -> None:
    headers = list(df.columns)
    ws.append(headers)
    for row in df.itertuples(index=False):
        ws.append([None if (v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA) else v
                   for v in row])

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="305496")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(vertical="center")

    link_font = Font(color="0563C1", underline="single")
    for idx, header in enumerate(headers, start=1):
        letter = get_column_letter(idx)
        values = [str(v) for v in df[header].tolist() if v is not None and not pd.isna(v) and v != ""]
        lengths = sorted(len(v) for v in values)
        typical = lengths[int(len(lengths) * 0.9)] if lengths else 0
        ws.column_dimensions[letter].width = max(10, min(50, max(len(header), typical) + 2))
        if header in URL_LABELS:
            for cell in ws[letter][1:]:
                if isinstance(cell.value, str) and cell.value.startswith(("http://", "https://")):
                    cell.hyperlink = cell.value
                    cell.font = link_font

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def slugify(text: str, max_len: int = 50) -> str:
    """Testo -> parte di nome file ("hotel 4 stelle | Palermo" -> "hotel-4-stelle-palermo")."""
    import unicodedata

    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:max_len].rstrip("-") or "prospects"
