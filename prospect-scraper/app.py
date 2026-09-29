"""Prospect Scraper: interfaccia Streamlit.

Avvio: doppio clic su "Avvia Prospect Scraper" (vedi README) oppure ``streamlit run app.py``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from config import settings
from core.pipeline import MODE_BOTH, MODE_ENRICH, MODES, Pipeline, RunParams
from database.db import Database
from exporters.export import (prospects_to_dataframe, slugify, to_csv_bytes, to_xlsx_bytes,
                              to_xlsx_multi_bytes)
from scrapers.search import CATEGORY_PROVIDERS, PROVIDERS, available_providers, default_provider_names

CATEGORIES = list(CATEGORY_PROVIDERS)
# colonne visibili in tabella (l'export contiene tutte le colonne)
TABLE_COLUMNS = ["Company", "Website", "Country", "City", "Category", "Phone", "Email",
                 "LinkedIn", "Instagram", "Source", "Status", "Error"]
STATUS_LABELS = {"enriched": "✅ enriched", "found": "🔎 found", "no_website": "➖ no website",
                 "failed": "⚠️ failed"}

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

st.set_page_config(page_title="Prospect Scraper", page_icon="🔎", layout="wide")


def run_label(run: dict) -> str:
    try:
        when = datetime.fromisoformat(run["started_at"]).astimezone().strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        when = ""
    what = " · ".join(filter(None, [run.get("keyword") or "Arricchimento siti", run.get("location")]))
    return f"{when} — {what} ({run['n_prospects']} prospect)"


def run_title(run: dict) -> str:
    return " ".join(filter(None, [run.get("keyword") or "arricchimento", run.get("location")]))


def save_export(data: bytes, filename: str) -> Path:
    """App desktop: salva il file direttamente nella cartella degli export (Download)."""
    folder = settings.EXPORT_DIR
    folder.mkdir(parents=True, exist_ok=True)
    stem, suffix = Path(filename).stem, Path(filename).suffix
    path, n = folder / filename, 2
    while path.exists():
        path, n = folder / f"{stem} ({n}){suffix}", n + 1
    path.write_bytes(data)
    return path


def reveal(path: Path) -> None:
    """Mostra il file nel Finder / Esplora file."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        elif os.name == "nt":
            subprocess.Popen(["explorer", "/select,", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        pass


def export_button(label: str, make_data, filename: str, key: str, primary: bool = False,
                  mime: str = "application/octet-stream", container=st) -> None:
    """Da browser: download classico. Nell'app desktop: salva in Download e lo dice."""
    kind = "primary" if primary else "secondary"
    if not settings.DESKTOP:
        container.download_button(label, make_data(), file_name=filename, mime=mime,
                                  width="stretch", type=kind, key=key)
        return
    if container.button(label, width="stretch", type=kind, key=key):
        ss.last_export = str(save_export(make_data(), filename))


def shutdown_server() -> None:
    """Chiude il server dell'app (usato dal pulsante "Chiudi app")."""
    def _stop():
        os.kill(os.getpid(), signal.SIGTERM)
    threading.Timer(1.0, _stop).start()


@st.cache_resource
def get_db() -> Database:
    return Database()


db = get_db()
ss = st.session_state
ss.setdefault("run_ids", None)
ss.setdefault("run_messages", [])
ss.setdefault("run_log", "")
ss.setdefault("run_had_errors", False)

# ---------------------------------------------------------------- sidebar ---
with st.sidebar:
    st.header("Ricerca")
    category = st.selectbox("Tipo di ricerca", CATEGORIES, index=0)
    keyword = st.text_input("Keyword", placeholder="es. hotel 4 stelle Palermo, SaaS Italia")
    location = st.text_input("Località", placeholder=f"es. Sicilia, Milano (default: {settings.DEFAULT_LOCATION})")
    max_results = st.select_slider("Numero risultati", options=settings.RESULT_OPTIONS,
                                   value=settings.DEFAULT_RESULTS)
    mode = st.selectbox("Modalità", MODES, index=MODES.index(MODE_BOTH))
    urls_text = ""
    if mode == MODE_ENRICH:
        urls_text = st.text_area(
            "Siti da arricchire (uno per riga)", height=120,
            help="Lascia vuoto per arricchire i prospect già nel database non ancora arricchiti.")

    avail = available_providers()
    with st.expander("Opzioni avanzate"):
        providers = st.multiselect(
            "Fonti", options=list(avail), default=default_provider_names(category),
            format_func=lambda n: PROVIDERS[n].label,
            help="Le fonti predefinite dipendono dal tipo di ricerca.")
        force_refresh = st.checkbox(
            "Ri-visita anche i siti arricchiti di recente",
            help=f"Di default i siti arricchiti negli ultimi {settings.REENRICH_AFTER_DAYS} giorni vengono riusati.")
        if "searxng" not in avail:
            st.caption("Ricerca web generica non attiva: imposta `PS_SEARXNG_URL` (vedi README).")
        st.caption(f"Max {settings.MAX_PAGES_PER_DOMAIN} pagine/sito · {settings.MAX_WORKERS} siti in parallelo "
                   f"· timeout {settings.REQUEST_TIMEOUT}s · pausa {settings.REQUEST_DELAY}s")

    run_clicked = st.button("CERCA PROSPECT", type="primary", width="stretch")

    st.divider()
    if not settings.DESKTOP and st.button("Chiudi app", width="stretch",
                                          help="Spegne l'app. I dati restano salvati."):
        st.success("App chiusa. Puoi chiudere questa finestra; i dati restano salvati.")
        shutdown_server()
        st.stop()

# ------------------------------------------------------------------- main ---
st.title("🔎 Prospect Scraper")
st.caption("Ricerca prospect da fonti pubbliche e raccolta dei contatti pubblicati sui loro siti.")

if run_clicked:
    urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
    if mode != MODE_ENRICH and not keyword.strip():
        st.sidebar.error("Inserisci una keyword.")
    elif mode != MODE_ENRICH and not providers:
        st.sidebar.error("Seleziona almeno una fonte.")
    else:
        messages: list[tuple[str, str]] = []
        with st.status("Ricerca in corso...", expanded=True) as status:
            progress_bar = st.empty()

            def on_message(text: str, level: str = "info") -> None:
                messages.append((level, text))
                if level == "warning":
                    st.warning(text)
                elif level == "error":
                    st.error(text)
                elif level == "success":
                    has_warnings = any(lvl in ("warning", "error") for lvl, _ in messages)
                    status.update(label=text, state="complete", expanded=has_warnings)
                else:
                    st.write(text)

            def on_progress(done: int, total: int, label: str = "") -> None:
                progress_bar.progress(done / total, text=f"{done}/{total} · {label[:60]}")

            params = RunParams(category=category, keyword=keyword.strip(), location=location.strip(),
                               max_results=max_results, mode=mode, providers=providers or None,
                               urls=urls, force_refresh=force_refresh)
            result = Pipeline(db, on_message=on_message, on_progress=on_progress).run(params)
            if result.fatal_error:
                status.update(label="Errore", state="error", expanded=True)

        ss.run_ids = result.prospect_ids
        ss.run_messages = messages
        ss.run_log = result.log_text
        ss.run_had_errors = bool(result.fatal_error or result.n_failed or result.provider_errors)
        ss.pop("all_runs_xlsx", None)   # l'export di tutte le ricerche va rigenerato
        ss.pop("last_export", None)
        ss["view"] = "Ultima ricerca"

# log dell'ultima operazione (sopravvive ai rerun, es. dopo un download)
if ss.run_messages and not run_clicked:
    with st.expander("Log ultima operazione" + (" ⚠️" if ss.run_had_errors else ""), expanded=False):
        for level, text in ss.run_messages:
            (st.warning if level == "warning" else st.error if level == "error" else st.write)(text)
        if ss.run_log:
            st.download_button("Scarica log tecnico", ss.run_log.encode("utf-8"),
                               file_name=f"prospect-log-{datetime.now():%Y%m%d-%H%M%S}.txt",
                               mime="text/plain")

# -------------------------------------------------------------- risultati ---
st.subheader("Risultati")
runs = db.list_runs()
VIEW_LAST, VIEW_SAVED, VIEW_ALL = "Ultima ricerca", "Ricerche salvate", "Tutto il database"
ss.setdefault("view", VIEW_LAST)
view = st.segmented_control("Mostra", [VIEW_LAST, VIEW_SAVED, VIEW_ALL],
                            label_visibility="collapsed", key="view") or VIEW_LAST

file_stem = "prospects"
if view == VIEW_ALL:
    prospects = db.list_prospects()
    file_stem = "prospects-tutti"
elif view == VIEW_SAVED:
    if not runs:
        st.info("Nessuna ricerca salvata. Imposta la ricerca nella barra laterale e premi **CERCA PROSPECT**.")
        st.stop()
    col_run, col_all = st.columns([3, 1], vertical_alignment="bottom")
    chosen = col_run.selectbox("Ricerca", runs, format_func=run_label)
    prospects = db.list_prospects(ids=db.run_prospect_ids(chosen["id"]))
    file_stem = slugify(run_title(chosen))
    def all_runs_xlsx() -> bytes:
        """Un file Excel con un foglio per ogni ricerca salvata."""
        return to_xlsx_multi_bytes({
            run_title(r): prospects_to_dataframe(db.list_prospects(ids=db.run_prospect_ids(r["id"])))
            for r in runs})

    all_name = f"prospects-tutte-le-ricerche-{datetime.now():%Y%m%d}.xlsx"
    with col_all:
        if settings.DESKTOP:
            export_button("Excel con tutte le ricerche", all_runs_xlsx, all_name, key="exp_all")
        else:  # nel browser il file va preparato prima del download
            if st.button("Prepara export di tutte le ricerche", width="stretch",
                         help="Un file Excel con un foglio per ogni ricerca salvata."):
                ss.all_runs_xlsx = all_runs_xlsx()
            if ss.get("all_runs_xlsx"):
                st.download_button("DOWNLOAD XLSX (tutte)", ss.all_runs_xlsx, file_name=all_name,
                                   mime=XLSX_MIME, width="stretch", type="primary")
else:  # ultima ricerca: quella appena fatta o, ad app appena aperta, l'ultima salvata
    last = runs[0] if runs else None
    if ss.run_ids is not None:
        prospects = db.list_prospects(ids=ss.run_ids)
    else:
        prospects = db.list_prospects(ids=db.run_prospect_ids(last["id"])) if last else []
    if last:
        st.caption(run_label(last))
        file_stem = slugify(run_title(last))

if not prospects:
    st.info("Nessun prospect. Imposta la ricerca nella barra laterale e premi **CERCA PROSPECT**.")
    st.stop()

df = prospects_to_dataframe(prospects)
df["Status"] = df["Status"].map(lambda s: STATUS_LABELS.get(s, s))

c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
query = c1.text_input("Cerca nella tabella", placeholder="nome, email, città, dominio...")
status_filter = c2.multiselect("Status", sorted(df["Status"].unique()))
city_filter = c3.multiselect("City", sorted(c for c in df["City"].unique() if c))
category_filter = c4.multiselect("Category", sorted(c for c in df["Category"].unique() if c))
with c5:
    only_email = st.checkbox("Solo con email")
    only_phone = st.checkbox("Solo con telefono")

view_df = df
if query:
    mask = view_df.astype(str).apply(lambda col: col.str.contains(query, case=False, regex=False)).any(axis=1)
    view_df = view_df[mask]
if status_filter:
    view_df = view_df[view_df["Status"].isin(status_filter)]
if city_filter:
    view_df = view_df[view_df["City"].isin(city_filter)]
if category_filter:
    view_df = view_df[view_df["Category"].isin(category_filter)]
if only_email:
    view_df = view_df[view_df["Email"] != ""]
if only_phone:
    view_df = view_df[view_df["Phone"] != ""]
view_df = view_df.reset_index(drop=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Prospect", len(view_df))
m2.metric("Con email", int((view_df["Email"] != "").sum()))
m3.metric("Con telefono", int((view_df["Phone"] != "").sum()))
m4.metric("Falliti", int(view_df["Status"].str.contains("failed").sum()))

export_bar = st.container()   # pulsanti di export sopra la tabella, riempiti dopo la selezione

link = st.column_config.LinkColumn
event = st.dataframe(
    view_df,
    column_order=TABLE_COLUMNS,
    column_config={
        "Website": link("Website", display_text=r"https?://(?:www\.)?([^/]+)"),
        "LinkedIn": link("LinkedIn", display_text=r"https?://[^/]+/(?:company/|in/)?([^/?]+)"),
        "Instagram": link("Instagram", display_text=r"https?://[^/]+/([^/?]+)"),
        "Company": st.column_config.TextColumn("Company", width="medium"),
        "Error": st.column_config.TextColumn("Error", width="medium"),
    },
    hide_index=True,
    width="stretch",
    height=min(38 + 35 * len(view_df), 600),
    on_select="rerun",
    selection_mode="multi-row",
    key="results_table",
)

selected = event.selection.rows if event and event.selection else []
export_df = view_df.iloc[selected] if selected else view_df
export_df = export_df.assign(Status=export_df["Status"].map(
    lambda s: next((k for k, v in STATUS_LABELS.items() if v == s), s)))
scope = f"{len(selected)} righe selezionate" if selected else f"{len(export_df)} righe (filtri applicati)"
name = f"{file_stem}-{datetime.now():%Y%m%d-%H%M}"
with export_bar:
    b1, b2, b3 = st.columns([1, 1, 4], vertical_alignment="center")
    export_button("DOWNLOAD CSV", lambda: to_csv_bytes(export_df), f"{name}.csv", key="exp_csv",
                  mime="text/csv", container=b1)
    export_button("DOWNLOAD XLSX", lambda: to_xlsx_bytes(export_df), f"{name}.xlsx", key="exp_xlsx",
                  primary=True, mime=XLSX_MIME, container=b2)
    b3.caption(f"Export: {scope}. Seleziona righe nella tabella per esportare solo quelle; "
               "il file include tutte le colonne.")

# App desktop: conferma del salvataggio (vale anche per l'export di tutte le ricerche)
if settings.DESKTOP and ss.get("last_export"):
    saved = Path(ss.last_export)
    with export_bar:
        c_msg, c_btn = st.columns([4, 1], vertical_alignment="center")
        c_msg.success(f"Salvato in **{saved.parent.name}**: {saved.name}")
        if c_btn.button("Mostra nel Finder" if sys.platform == "darwin" else "Apri cartella",
                        key="reveal", width="stretch"):
            reveal(saved)
