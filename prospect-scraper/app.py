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

from config import settings, user_settings
from core.pipeline import (AGENCY_CATEGORY, MODE_BOTH, MODE_ENRICH, MODE_SEARCH, MODES, SOURCE_AGENCY,
                           SOURCE_WEB, WEB_CATEGORY, Pipeline, RunParams)
from database.db import Database
from exporters.export import (prospects_to_dataframe, slugify, to_csv_bytes, to_xlsx_bytes,
                              to_xlsx_multi_bytes)
from qualify import config as qconfig
from qualify import llm as qllm
from qualify.diagnose import run_diagnosis
from scrapers import web_search
from scrapers.search import CATEGORY_PROVIDERS, PROVIDERS, available_providers, default_provider_names

CATEGORIES = list(CATEGORY_PROVIDERS)
# colonne visibili in tabella (l'export contiene tutte le colonne)
TABLE_COLUMNS = ["Company", "Website", "Country", "City", "Category", "Phone", "Email",
                 "LinkedIn", "Instagram", "Source", "Status", "Error"]
AGENCY_TABLE_COLUMNS = ["Score", "Motivo", "Company", "Website", "Is agency", "SEO level", "Servizi ricorrenti",
                        "Size", "Blog", "Servizi", "Verticali", "Note", "Email", "Phone", "LinkedIn",
                        "Instagram", "Country", "City", "Status", "Error"]
SRC_LOCAL, SRC_WEB, SRC_AGENCY = "Local (OSM + Wikidata)", "Web Search", "Agenzie"
# Scelte AI della ricerca Agenzie: chiave = voce di [llm] nei pesi (claude, claude_alt, openai, gemini)
AI_LABELS = {"claude": "Claude Haiku 4.5 (economico)", "claude_alt": "Claude Sonnet 5.5 (più accurato)",
             "openai": "OpenAI GPT-5.4 mini", "gemini": "Google Gemini 2.5 Flash"}
AI_HELP = {
    "claude": "Chiave Anthropic: https://platform.claude.com/settings/keys.",
    "openai": "Chiave OpenAI: https://platform.openai.com/api-keys",
    "gemini": "Chiave Google Gemini: https://aistudio.google.com/apikey",
}
EST_TOKENS_IN, EST_TOKENS_OUT, EST_TOKENS_OUT_THINKING = 8000, 800, 2000   # stima per agenzia
WEB_PROVIDER_LABELS = {"tavily": "Tavily (consigliato, gratuito)", "brave": "Brave Search",
                       "searxng": "SearXNG (istanza propria)"}
WEB_PROVIDER_HELP = {
    "tavily": "Crea un account gratuito su https://app.tavily.com (1000 ricerche/mese, senza carta di "
              "credito) e incolla qui la chiave API.",
    "brave": "https://api-dashboard.search.brave.com — 5$ di credito gratuito al mese (≈1000 ricerche), "
             "richiede carta di credito.",
    "searxng": "Indirizzo della tua istanza SearXNG con formato JSON abilitato, "
               "es. http://localhost:8888 (vedi README).",
}
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
    ss.setdefault("search_source", SRC_LOCAL)
    source = st.segmented_control("Fonte", [SRC_LOCAL, SRC_WEB, SRC_AGENCY], key="search_source") or SRC_LOCAL
    if source == SRC_LOCAL:
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
    elif source == SRC_WEB:
        category = WEB_CATEGORY
        keyword = st.text_input("Keyword", placeholder="es. SaaS B2B, startup fintech, magazine online",
                                key="web_keyword")
        location = st.text_input("Località / Paese", placeholder="es. Italia, Milano (facoltativo)",
                                 key="web_location")
        max_results = st.select_slider("Numero risultati", options=settings.RESULT_OPTIONS,
                                       value=settings.DEFAULT_RESULTS, key="web_max_results")
        enrich = st.checkbox("Visita i siti per trovare contatti (enrichment)", value=True,
                             key="web_enrich")
        mode = MODE_BOTH if enrich else MODE_SEARCH
        urls_text, providers, force_refresh = "", None, False

        saved_provider = user_settings.get("web_provider", "tavily")
        if saved_provider not in WEB_PROVIDER_LABELS:
            saved_provider = "tavily"
        with st.expander("Impostazioni Web Search",
                         expanded=not web_search.web_search_status(saved_provider)[0]):
            web_provider = st.selectbox(
                "Provider", list(WEB_PROVIDER_LABELS), index=list(WEB_PROVIDER_LABELS).index(saved_provider),
                format_func=WEB_PROVIDER_LABELS.get, key="web_provider_select")
            is_url = web_provider == "searxng"
            setting_key = "searxng_url" if is_url else f"{web_provider}_api_key"
            secret = st.text_input(
                "URL dell'istanza" if is_url else "Chiave API", value=user_settings.load().get(setting_key, ""),
                type="default" if is_url else "password", key=f"web_secret_{web_provider}")
            if st.button("Salva", key="web_save"):
                user_settings.save({"web_provider": web_provider, setting_key: secret})
                st.success("Impostazioni salvate.")
            web_ok, web_label = web_search.web_search_status(web_provider)
            st.write(f"{web_label}: " + ("✅ configurato" if web_ok else "⚠️ non configurato"))
            st.caption(WEB_PROVIDER_HELP[web_provider])
            st.caption(f"Ogni ricerca usa 1-{settings.WEB_MAX_API_CALLS} chiamate API (1 credito ciascuna).")
    else:
        category = AGENCY_CATEGORY
        keyword = st.text_input("Keyword", placeholder="es. agenzia web marketing, agenzia di comunicazione",
                                key="ag_keyword")
        location = st.text_input("Località", placeholder="es. Milano, Lombardia, Italia", key="ag_location")
        max_results = st.select_slider("Numero risultati", options=settings.RESULT_OPTIONS,
                                       value=settings.DEFAULT_RESULTS, key="ag_max_results")
        mode = MODE_BOTH
        urls_text, providers, force_refresh = "", None, False
        ag_web_ok, ag_web_label = web_search.web_search_status()
        scoring_cfg, scoring_error = qconfig.load_scoring_with_error()
        saved_llm = user_settings.get("llm_provider", "claude")
        saved_choice = ("claude_alt" if saved_llm == "claude"
                        and user_settings.get("claude_model") == scoring_cfg["llm"]["claude_alt"]
                        else saved_llm if saved_llm in AI_LABELS else "claude")
        saved_provider_ok = qllm.get_classifier(
            "claude" if saved_choice.startswith("claude") else saved_choice,
            model=scoring_cfg["llm"][saved_choice]).is_configured()
        with st.expander("Impostazioni Agenzie", expanded=not (ag_web_ok and saved_provider_ok)):
            st.write(f"Web Search ({ag_web_label}): " + ("✅ configurata" if ag_web_ok else "⚠️ non configurata"))
            if not ag_web_ok:
                st.caption("Configura la Web Search in Fonte → Web Search → «Impostazioni Web Search».")
            ai_choice = st.selectbox("Modello AI", list(AI_LABELS), index=list(AI_LABELS).index(saved_choice),
                                     format_func=AI_LABELS.get, key="ag_llm_choice")
            ai_provider = "claude" if ai_choice.startswith("claude") else ai_choice
            ai_model = scoring_cfg["llm"][ai_choice]
            ai_key_setting = qllm.KEY_SETTINGS[ai_provider]
            ai_secret = st.text_input("Chiave API", value=user_settings.load().get(ai_key_setting, ""),
                                      type="password", key=f"ag_secret_{ai_provider}")
            if st.button("Salva", key="ag_save"):
                user_settings.save({"llm_provider": ai_provider, ai_key_setting: ai_secret,
                                    **({"claude_model": ai_model} if ai_provider == "claude" else {})})
                st.success("Impostazioni salvate.")
            ai_ok = qllm.get_classifier(ai_provider, model=ai_model).is_configured()
            st.write(f"{AI_LABELS[ai_choice]}: " + ("✅ configurato" if ai_ok else "⚠️ chiave non configurata"))
            if st.button("Prova connessione AI", key="ag_test_ai",
                         help="Fa UNA chiamata di prova (costo < 0,01 $) con la chiave del campo qui sopra "
                              "e mostra la risposta grezza o l'errore completo."):
                with st.spinner("Chiamata di prova in corso..."):
                    report = run_diagnosis(qllm.CLASSIFIERS[ai_provider](ai_secret, ai_model))
                if report.get("esito") == "OK":
                    st.success("Connessione OK: il modello ha risposto con un JSON valido.")
                else:
                    st.error(f"Errore: {report.get('errore') or report.get('esito')}")
                st.json(report, expanded=True)
            st.caption(AI_HELP[ai_provider])
            price = scoring_cfg["prezzi"].get(ai_model)
            if price:
                out_tokens = EST_TOKENS_OUT_THINKING if ai_choice == "claude_alt" else EST_TOKENS_OUT
                est = (EST_TOKENS_IN * price[0] + out_tokens * price[1]) / 1_000_000
                st.caption(f"Costo stimato: ≈ {est:.3f} $ per agenzia ({EST_TOKENS_IN} token in + "
                           f"{out_tokens} out). I testi delle pagine vengono inviati al provider scelto.")
            ai_blacklist = st.text_area("Blacklist", value=qconfig.blacklist_text(), height=200, key="ag_blacklist",
                                        help="Sezioni [domini] e [frasi]; una voce per riga, # per i commenti.")
            if st.button("Salva blacklist", key="ag_save_blacklist"):
                qconfig.save_blacklist_text(ai_blacklist)
                st.success("Blacklist salvata.")
            if scoring_error:
                st.warning(f"Il file dei pesi non è valido, uso quelli predefiniti: {scoring_error}")
            ai_scoring = st.text_area("Pesi dello score", value=qconfig.scoring_text(), height=300,
                                      key="ag_scoring")
            if st.button("Salva pesi", key="ag_save_scoring"):
                try:
                    qconfig.save_scoring_text(ai_scoring)
                    st.success("Pesi salvati.")
                except ValueError as exc:
                    st.error(f"Pesi non salvati: {exc}")

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
    elif source == SRC_WEB and not web_search.web_search_status(web_provider)[0]:
        st.sidebar.error("Web Search non configurata: inserisci la chiave API in "
                         "«Impostazioni Web Search» e premi Salva.")
    elif source == SRC_AGENCY and not ag_web_ok:
        st.sidebar.error("Web Search non configurata: configurala in Fonte → Web Search.")
    elif source == SRC_AGENCY and not ai_ok:
        st.sidebar.error("Chiave AI non configurata: inseriscila in «Impostazioni Agenzie» e premi Salva.")
    elif source == SRC_LOCAL and mode != MODE_ENRICH and not providers:
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

            web_args = {"search_source": SOURCE_WEB, "web_provider": web_provider} if source == SRC_WEB else {}
            if source == SRC_AGENCY:
                web_args = {"search_source": SOURCE_AGENCY, "llm_provider": ai_provider, "llm_model": ai_model}
            params = RunParams(category=category, keyword=keyword.strip(), location=location.strip(),
                               max_results=max_results, mode=mode, providers=providers or None,
                               urls=urls, force_refresh=force_refresh, **web_args)
            result = Pipeline(db, on_message=on_message, on_progress=on_progress).run(params)
            if result.fatal_error:
                status.update(label="Errore", state="error", expanded=True)

        ss.run_ids = result.prospect_ids
        ss.run_messages = messages
        ss.run_log = result.log_text
        ss.run_had_errors = bool(result.fatal_error or result.n_failed or result.n_qual_failed
                                 or result.provider_errors)
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
agency_view = False   # True se i prospect mostrati vengono da una ricerca Agenzie (con qualifica)
agency_run_id = None  # id della ricerca Agenzie mostrata (per rilanciare la qualifica)
if view == VIEW_ALL:
    prospects = db.list_prospects()
    file_stem = "prospects-tutti"
elif view == VIEW_SAVED:
    if not runs:
        st.info("Nessuna ricerca salvata. Imposta la ricerca nella barra laterale e premi **CERCA PROSPECT**.")
        st.stop()
    col_run, col_all = st.columns([3, 1], vertical_alignment="bottom")
    chosen = col_run.selectbox("Ricerca", runs, format_func=run_label)
    agency_view = chosen.get("category") == AGENCY_CATEGORY
    agency_run_id = chosen["id"] if agency_view else None
    prospects = db.list_prospects(ids=db.run_prospect_ids(chosen["id"]))
    file_stem = slugify(run_title(chosen))
    def all_runs_xlsx() -> bytes:
        """Un file Excel con un foglio per ogni ricerca salvata."""
        def frame(r: dict) -> pd.DataFrame:
            items = db.list_prospects(ids=db.run_prospect_ids(r["id"]))
            quals = db.get_qualifications([p.id for p in items]) if r.get("category") == AGENCY_CATEGORY else None
            return prospects_to_dataframe(items, quals)

        return to_xlsx_multi_bytes({run_title(r): frame(r) for r in runs})

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
    agency_view = bool(last and last.get("category") == AGENCY_CATEGORY)
    agency_run_id = last["id"] if agency_view else None
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

quals = db.get_qualifications([p.id for p in prospects]) if agency_view else None
df = prospects_to_dataframe(prospects, quals)
df["Status"] = df["Status"].map(lambda s: STATUS_LABELS.get(s, s))
if agency_view:
    # esiti della qualifica nella tabella; l'export conserva lo status e l'errore originali
    df["_Status"], df["_Error"] = df["Status"], df["Error"]
    failed, excluded = df["Qualifica status"] == "failed", df["Qualifica status"] == "excluded"
    df.loc[failed, "Status"] = "⚠️ failed"
    df.loc[failed, "Error"] = "qualifica: " + df.loc[failed, "Qualifica errore"]
    df.loc[excluded, "Status"] = "🚫 esclusa"
    # "Motivo": perché manca lo score, ben visibile accanto allo score
    not_qualified = df["Qualifica status"] == ""
    df["Motivo"] = ""
    df.loc[failed, "Motivo"] = "qualifica fallita: " + df.loc[failed, "Qualifica errore"]
    df.loc[excluded, "Motivo"] = "esclusa: non è un'agenzia"
    df.loc[not_qualified, "Motivo"] = "non qualificata" + df.loc[not_qualified, "_Error"].map(
        lambda e: f" (sito: {e})" if e else "")
    df = df.sort_values("Score", ascending=False, na_position="last", kind="stable")   # Score decrescente

    if ss.get("rq_message"):
        level, text = ss.pop("rq_message")
        (st.success if level == "success" else st.warning)(text)
    n_failed = int(failed.sum())
    if n_failed:
        reasons = df.loc[failed, "Qualifica errore"].value_counts()
        lines = "\n".join(f"- {reason} — **{count}**" for reason, count in reasons.head(4).items())
        st.error(f"Qualifica fallita su **{n_failed} di {len(df)}** agenzie. Motivi:\n{lines}\n\n"
                 "Usa «Prova connessione AI» in «Impostazioni Agenzie» per verificare chiave e credito, "
                 "poi rilancia la qualifica qui sotto.")
    with st.expander("Rilancia la qualifica AI su questa ricerca", expanded=bool(n_failed)):
        st.caption("Rifà solo l'analisi AI e lo score, senza una nuova ricerca: riscarica le pagine dei siti "
                   "e usa il modello e la chiave salvati in «Impostazioni Agenzie».")
        rq_scope = st.radio("Agenzie da rianalizzare", ["Solo quelle senza score (fallite)", "Tutte"],
                            horizontal=True, key="rq_scope")
        if st.button("Rilancia qualifica", key="rq_run", type="primary"):
            target = df[failed] if rq_scope.startswith("Solo") else df
            ids = [int(i) for i in target["ID"].dropna()]
            if not ids:
                st.info("Nessuna agenzia da rianalizzare.")
            else:
                rq_messages: list[tuple[str, str]] = []
                with st.status("Qualifica in corso...", expanded=True) as rq_status:
                    rq_bar = st.empty()

                    def rq_msg(text: str, level: str = "info") -> None:
                        rq_messages.append((level, text))
                        if level in ("warning", "error"):
                            st.warning(text)
                        elif level != "success":
                            st.write(text)

                    def rq_progress(done: int, total: int, label: str = "") -> None:
                        rq_bar.progress(done / total, text=f"{done}/{total} · {label[:60]}")

                    rq_result = Pipeline(db, on_message=rq_msg, on_progress=rq_progress).requalify(
                        ids, agency_run_id)
                final = next((t for lvl, t in reversed(rq_messages) if lvl == "success"), None)
                ss.rq_message = ("success", final) if final else (
                    "warning", "; ".join(t for lvl, t in rq_messages if lvl in ("warning", "error"))
                    or rq_result.fatal_error or "Qualifica non eseguita")
                st.rerun()

c1, c2, c3, c4, c5 = st.columns([3, 2, 2, 2, 2])
query = c1.text_input("Cerca nella tabella", placeholder="nome, email, città, dominio...")
status_filter = c2.multiselect("Status", sorted(df["Status"].unique()))
city_filter = c3.multiselect("City", sorted(c for c in df["City"].unique() if c))
category_filter = c4.multiselect("Category", sorted(c for c in df["Category"].unique() if c))
with c5:
    only_email = st.checkbox("Solo con email")
    only_phone = st.checkbox("Solo con telefono")

view_df = df
if agency_view:
    f1, f2, _f3 = st.columns([2, 2, 6])
    min_score = f1.slider("Score minimo", 0, 100, 0)
    show_excluded = f2.checkbox("Mostra escluse", value=False)
    if not show_excluded:
        view_df = view_df[view_df["Qualifica status"] != "excluded"]
    if min_score > 0:
        view_df = view_df[view_df["Score"].fillna(-1) >= min_score]
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
    column_order=AGENCY_TABLE_COLUMNS if agency_view else TABLE_COLUMNS,
    column_config={
        **({"Score": st.column_config.NumberColumn("Score", format="%d"),
            "Is agency": st.column_config.TextColumn("Agenzia", width="small"),
            "SEO level": st.column_config.TextColumn("SEO", width="small"),
            "Servizi ricorrenti": st.column_config.TextColumn("Ricorrenti", width="small"),
            "Size": st.column_config.TextColumn("Team", width="small"),
            "Servizi": st.column_config.TextColumn("Servizi", width="medium"),
            "Verticali": st.column_config.TextColumn("Verticali", width="medium"),
            "Note": st.column_config.TextColumn("Nota", width="large"),
            "Motivo": st.column_config.TextColumn("Motivo", width="large")} if agency_view else {}),
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
if agency_view:
    export_df = export_df.assign(Status=export_df["_Status"], Error=export_df["_Error"]).drop(
        columns=["_Status", "_Error"])
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
