"""Orchestrazione: ricerca -> normalizzazione -> deduplicazione -> salvataggio ->
website enrichment concorrente -> aggiornamento DB. Indipendente dalla UI."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlsplit

from config import settings, user_settings
from database.db import Database, now_iso
from decision_makers import finder as dm_finder
from decision_makers.models import STATUS_FOUND as DM_FOUND
from decision_makers.models import STATUS_NOT_FOUND as DM_NOT_FOUND
from models.prospect import STATUS_ENRICHED, STATUS_FAILED, STATUS_FOUND, STATUS_NO_WEBSITE, Prospect
from qualify import config as qconfig
from qualify import llm as qllm
from qualify import qualifier as qqualifier
from scrapers import contacts, social, web_search
from scrapers.company import company_name_from_title
from scrapers.http import HttpClient, default_client
from scrapers.search import PROVIDERS, SearchRequest, SearchResult, run_search
from scrapers.website import EnrichmentResult, WebsiteCrawler
from utils.deduplication import deduplicate, merge_prospects
from utils.logging import RunLogCapture, get_logger
from utils.normalization import (clean_text, homepage_url, is_domain_in, normalize_domain,
                                 normalize_url, registrable_domain)

log = get_logger("pipeline")

MODE_SEARCH = "Search"
MODE_ENRICH = "Website enrichment"
MODE_BOTH = "Search + enrichment"
MODES = [MODE_SEARCH, MODE_ENRICH, MODE_BOTH]

# Fonte della ricerca: locale (OSM + Wikidata) oppure Web Search (API di ricerca web)
SOURCE_LOCAL = "local"
SOURCE_WEB = "web"
WEB_CATEGORY = "Web Search"
# Agenzie italiane da qualificare con l'AI (Web Search + blacklist + qualifica)
SOURCE_AGENCY = "agency"
AGENCY_CATEGORY = "Agenzie"
MAX_QUALIFY_WORKERS = 3

_SOCIAL_FIELDS = ("linkedin", "instagram", "facebook", "twitter", "youtube")
_EXTRA_FIELDS = ("city", "address", "postal_code", "country", "region", "email", *_SOCIAL_FIELDS)


@dataclass
class RunParams:
    category: str = "Custom"
    keyword: str = ""
    location: str = ""
    max_results: int = settings.DEFAULT_RESULTS
    mode: str = MODE_BOTH
    providers: list[str] | None = None
    urls: list[str] = field(default_factory=list)   # per la modalità Website enrichment
    force_refresh: bool = False
    search_source: str = SOURCE_LOCAL
    web_provider: str | None = None     # solo per SOURCE_WEB (None = quello nelle impostazioni)
    llm_provider: str | None = None     # solo per SOURCE_AGENCY (None = quello nelle impostazioni)
    llm_model: str | None = None        # solo per SOURCE_AGENCY (None = il modello delle impostazioni)
    qualify: bool = True                # solo per SOURCE_AGENCY: False = niente qualifica con l'AI


@dataclass
class RunResult:
    run_id: int | None = None
    prospect_ids: list[int] = field(default_factory=list)
    n_found: int = 0
    n_unique: int = 0
    n_enriched: int = 0
    n_failed: int = 0
    n_cached: int = 0
    provider_errors: dict[str, str] = field(default_factory=dict)
    log_text: str = ""
    fatal_error: str = ""
    n_qualified: int = 0        # agenzie qualificate (ricerca Agenzie)
    n_qual_failed: int = 0
    n_excluded: int = 0         # non sono agenzie (is_agency = no)
    llm_cost_usd: float = 0.0


@dataclass
class ContactsResult:
    """Esito di «Trova contatti» (decisori delle agenzie)."""

    n_targets: int = 0          # agenzie elaborate
    n_found: int = 0            # decisore trovato
    n_not_found: int = 0
    n_failed: int = 0
    n_linkedin: int = 0         # profili LinkedIn trovati
    n_email_site: int = 0       # email nominative trovate sul sito
    n_email_guess: int = 0      # email ipotizzate (da verificare)
    n_skipped_not_agency: int = 0
    n_skipped_done: int = 0     # già cercate (senza "ricalcola")
    web_calls: int = 0
    llm_cost_usd: float = 0.0
    log_text: str = ""
    fatal_error: str = ""


MessageFn = Callable[[str, str], None]          # (testo, livello: info|warning|error|success)
ProgressFn = Callable[[int, int, str], None]    # (fatti, totale, etichetta)


def result_to_prospect(r: SearchResult, params: RunParams) -> Prospect:
    """Converte un risultato di ricerca in prospect senza inventare nulla."""
    extra = dict(r.extra or {})
    p = Prospect(source=r.source, search_query=" | ".join(filter(None, [params.keyword, params.location])))
    url = (r.url or "").strip()
    if url:
        domain = normalize_domain(url)
        soc = social.normalize_social_url(url)
        if soc:
            extra.setdefault(soc[0], soc[1])          # la "homepage" è un profilo social
            p.raw_data["website_was_social"] = url
        elif domain and is_domain_in(domain, settings.NON_COMPANY_DOMAINS):
            p.raw_data["non_company_url"] = url       # portale/directory: non è il sito
        elif domain:
            p.website = homepage_url(url) or ""
            p.domain = domain
    p.company_name = (extra.get("company_name") or company_name_from_title(r.title, p.domain)
                      or r.title or p.domain or "").strip()[:200]
    # nome da dati strutturati (OSM/Wikidata) = affidabile; da titolo = provvisorio
    p.raw_data["name_source"] = "provider" if extra.get("company_name") else "title"
    detail = extra.get("category_detail", "")
    p.category = f"{params.category} · {detail}" if detail else params.category
    for f in _EXTRA_FIELDS:
        value = (extra.get(f) or "").strip()
        if not value or f == "email":
            continue
        if f in _SOCIAL_FIELDS:
            if not value.startswith("http") and f in ("facebook", "instagram"):
                value = f"https://www.{f}.com/{value.strip('@/')}"  # tag OSM con il solo username
            norm = social.normalize_social_url(value)
            if not norm:
                continue
            value = norm[1]
        setattr(p, f, value)
    if extra.get("email"):
        p.email = contacts.clean_email(extra["email"]) or ""
        p.emails = p.email
    if extra.get("phone"):
        ph = contacts.normalize_phone(extra["phone"])
        if ph:
            p.phone, p.phones, p.phone_raw = ph.international, ph.international, extra["phone"]
    p.source_url = extra.get("source_url") or url
    p.status = STATUS_FOUND if p.website else STATUS_NO_WEBSITE
    p.raw_data["search"] = {"title": r.title, "snippet": r.snippet, "url": r.url,
                            **{k: v for k, v in extra.items() if k not in _EXTRA_FIELDS}}
    return p


def _web_website(url: str, domain: str) -> str:
    """Home del sito per un risultato web: host originale se è il dominio (o www.), altrimenti
    il dominio registrabile. Mantiene lo schema http se presente."""
    parts = urlsplit(normalize_url(url) or "")
    host = (parts.hostname or "").lower()
    scheme = "http" if parts.scheme == "http" else "https"
    if host in (domain, f"www.{domain}"):
        return f"{scheme}://{parts.netloc}/"
    return f"{scheme}://{domain}/"


def web_result_to_prospect(r: SearchResult, params: RunParams, query: str,
                           category: str = WEB_CATEGORY) -> Prospect:
    """Converte un risultato della Web Search in prospect: solo dominio, sito e testo del
    risultato. Città, paese, email e telefono restano vuoti (li trova l'enrichment)."""
    extra = dict(r.extra or {})
    domain = registrable_domain(r.url) or ""
    p = Prospect(source=r.source, search_query=query, category=category, domain=domain)
    p.website = _web_website(r.url, domain) if domain else ""
    p.company_name = (company_name_from_title(r.title, domain) or domain).strip()[:200]
    p.raw_data["name_source"] = "title"    # provvisorio: il sito può dichiarare il nome vero
    p.description = clean_text(r.snippet)[:500]
    p.source_url = r.url
    p.status = STATUS_FOUND if p.website else STATUS_NO_WEBSITE
    p.raw_data["search"] = {"title": r.title, "snippet": r.snippet, "url": r.url,
                            "rank": extra.get("rank"), "other_urls": extra.get("other_urls", [])}
    return p


def apply_enrichment(p: Prospect, res: EnrichmentResult) -> Prospect:
    """Aggiorna il prospect con i dati del sito. I dati già presenti (es. da OSM) restano."""
    info = {"final_url": res.final_url, "pages_visited": res.pages_visited,
            "pages_failed": res.pages_failed, "warnings": res.warnings,
            "rendered_js": res.rendered_js, "at": now_iso()}
    if not res.ok:
        p.status = STATUS_FAILED
        p.error_message = res.error or "errore sconosciuto"
        p.raw_data["enrichment"] = info
        return p

    site_domain = normalize_domain(res.final_url) or p.domain
    p.status = STATUS_ENRICHED
    p.error_message = ""
    p.enriched_at = now_iso()

    emails = list(res.emails)
    for e in [p.email, *(p.emails or "").split("; ")]:
        if e and e not in emails:
            emails.append(e)
    emails = contacts.sort_emails(emails, site_domain)
    p.email = emails[0] if emails else ""
    p.emails = "; ".join(emails)

    phones = list(res.phones)
    known = contacts.normalize_phone(p.phone_raw or p.phone) if (p.phone_raw or p.phone) else None
    if known and known.e164 not in {x.e164 for x in phones}:
        phones.append(known)
    main = next((x for x in phones if x.from_tel_link), None) or known or (phones[0] if phones else None)
    if main:
        p.phone, p.phone_raw = main.international, main.raw
    ordered = ([main] if main else []) + [x for x in phones if main is None or x.e164 != main.e164]
    p.phones = "; ".join(x.international for x in ordered)

    for network in ("linkedin", "instagram", "facebook", "youtube", "twitter"):
        found = res.socials.get(network)
        if found:
            setattr(p, network, found[0])

    trusted_site_name = res.company_name_source in ("schema.org", "og:site_name")
    if (not p.company_name or p.company_name == p.domain
            or (trusted_site_name and p.raw_data.get("name_source") != "provider")):
        p.company_name = res.company_name or p.company_name or p.domain or ""
    for f in ("city", "address", "postal_code", "region", "country"):
        if not getattr(p, f) and getattr(res, f):
            setattr(p, f, getattr(res, f))
    p.vat_id = p.vat_id or res.vat_id
    p.page_title = res.page_title or p.page_title
    p.description = res.description or p.description

    info.update({"all_emails": res.emails, "socials": res.socials,
                 "phones_raw": [x.raw for x in res.phones], "country_source": res.country_source,
                 "company_name_site": res.company_name, "schema_type": res.jsonld.get("type", "")})
    p.raw_data["enrichment"] = info
    return p


def _safe_enrich(crawler: WebsiteCrawler, website: str) -> EnrichmentResult:
    try:
        return crawler.enrich(website)
    except Exception as exc:  # noqa: BLE001 - un sito non deve fermare il batch
        log.exception("errore interno durante l'enrichment di %s", website)
        return EnrichmentResult(website=website, ok=False, error=f"errore interno: {type(exc).__name__}")


class Pipeline:
    def __init__(self, db: Database, client: HttpClient | None = None,
                 crawler: WebsiteCrawler | None = None,
                 on_message: MessageFn | None = None, on_progress: ProgressFn | None = None):
        self.db = db
        self.client = client or default_client()
        self.crawler = crawler or WebsiteCrawler(self.client)
        self.msg = on_message or (lambda text, level="info": None)
        self.progress = on_progress or (lambda done, total, label="": None)
        self.last_enrichment: dict[int, EnrichmentResult] = {}   # id prospect -> esito (riusato dalla qualifica)

    def run(self, params: RunParams) -> RunResult:
        result = RunResult()
        self.last_enrichment = {}
        with RunLogCapture() as capture:
            try:
                self._run(params, result)
            except Exception as exc:  # noqa: BLE001
                log.exception("esecuzione interrotta")
                result.fatal_error = f"{type(exc).__name__}: {exc}"
                self.msg(f"Errore imprevisto: {result.fatal_error}", "error")
            result.log_text = capture.text()
        return result

    def requalify(self, prospect_ids: list[int], run_id: int | None, llm_provider: str | None = None,
                  llm_model: str | None = None) -> RunResult:
        """Rilancia solo la qualifica AI su prospect già trovati e arricchiti (nessuna nuova ricerca).
        Le pagine dei siti vengono riscaricate; i risultati sostituiscono quelli precedenti."""
        result = RunResult(run_id=run_id, prospect_ids=list(prospect_ids))
        self.last_enrichment = {}
        t0 = time.monotonic()
        with RunLogCapture() as capture:
            try:
                prospects = self.db.list_prospects(ids=list(prospect_ids))
                params = RunParams(category=AGENCY_CATEGORY, search_source=SOURCE_AGENCY,
                                   llm_provider=llm_provider, llm_model=llm_model)
                result.n_unique = len(prospects)
                if self._qualify(prospects, params, result):
                    self.msg(f"Qualifica completata in {time.monotonic() - t0:.0f}s: "
                             + _qualify_summary(result), "success")
                else:
                    self.msg("Qualifica non eseguita", "warning")
            except Exception as exc:  # noqa: BLE001
                log.exception("riqualifica interrotta")
                result.fatal_error = f"{type(exc).__name__}: {exc}"
                self.msg(f"Errore imprevisto: {result.fatal_error}", "error")
            result.log_text = capture.text()
        return result

    def find_contacts(self, prospect_ids: list[int], force: bool = False, llm_provider: str | None = None,
                      llm_model: str | None = None, web_provider: str | None = None) -> ContactsResult:
        """Decisore, LinkedIn ed email per le agenzie già qualificate con is_agency = "si"
        (nessuna nuova ricerca). Con ``force`` rifà anche quelle già cercate."""
        result = ContactsResult()
        t0 = time.monotonic()
        with RunLogCapture() as capture:
            try:
                if self._find_contacts(list(prospect_ids), force, llm_provider, llm_model, web_provider, result):
                    self.msg(f"Contatti cercati in {time.monotonic() - t0:.0f}s: " + _contacts_summary(result),
                             "success")
            except Exception as exc:  # noqa: BLE001
                log.exception("ricerca contatti interrotta")
                result.fatal_error = f"{type(exc).__name__}: {exc}"
                self.msg(f"Errore imprevisto: {result.fatal_error}", "error")
            result.log_text = capture.text()
        return result

    def _find_contacts(self, ids: list[int], force: bool, llm_provider: str | None, llm_model: str | None,
                       web_provider: str | None, result: ContactsResult) -> bool:
        quals = self.db.get_qualifications(ids)
        done = self.db.get_decision_makers(ids) if not force else {}
        todo: list[Prospect] = []
        for p in self.db.list_prospects(ids=ids):
            q = quals.get(p.id)
            if not p.website or q is None or q.is_agency != "si":
                result.n_skipped_not_agency += 1
            elif p.id in done and done[p.id].status in (DM_FOUND, DM_NOT_FOUND):
                result.n_skipped_done += 1
            else:
                todo.append(p)
        if result.n_skipped_not_agency:
            self.msg(f"{_plural(result.n_skipped_not_agency, 'riga saltata', 'righe saltate')}: "
                     "solo agenzie qualificate con «Agenzia = si»", "info")
        if result.n_skipped_done:
            self.msg(f"{_plural(result.n_skipped_done, 'agenzia già cercata', 'agenzie già cercate')}: "
                     "spunta «Ricalcola» per rifarle", "info")
        if not todo:
            self.msg("Nessuna agenzia su cui cercare i contatti", "warning")
            return False
        classifier = qllm.get_classifier(llm_provider, self.client, llm_model)
        if not classifier.is_configured():
            self.msg("AI non configurata: inserisci la chiave API in «Impostazioni Agenzie»", "warning")
            return False
        provider = web_search.get_provider(web_provider, self.client)
        if not provider.is_configured():
            self.msg("Web Search non configurata: i profili LinkedIn non verranno cercati", "warning")
        prices = qconfig.load_scoring().get("prezzi", {})
        result.n_targets = len(todo)
        self.msg("Finding decision makers...", "info")
        workers = max(1, min(MAX_QUALIFY_WORKERS, settings.MAX_WORKERS, len(todo)))
        n = 0
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="contacts") as pool:
            futures = {pool.submit(dm_finder.find_decision_maker, p, self.client, classifier, provider,
                                   prices): p for p in todo}
            for fut in as_completed(futures):
                p = futures[fut]
                dm = fut.result()          # find_decision_maker non solleva
                self.db.save_decision_maker(p.id, dm)
                result.llm_cost_usd += dm.cost_usd
                result.web_calls += dm.web_calls
                if dm.status == DM_FOUND:
                    result.n_found += 1
                    result.n_linkedin += bool(dm.linkedin_url)
                    result.n_email_site += dm.email_verified
                    result.n_email_guess += bool(dm.email) and not dm.email_verified
                elif dm.status == DM_NOT_FOUND:
                    result.n_not_found += 1
                else:
                    result.n_failed += 1
                    log.info("contatti falliti %s: %s", p.website, dm.error)
                n += 1
                self.progress(n, len(todo), p.company_name or p.domain or p.website)
        return True

    # ------------------------------------------------------------------------
    def _run(self, params: RunParams, result: RunResult) -> None:
        t0 = time.monotonic()
        log.info("run: %s", params)
        result.run_id = self.db.start_run(
            mode=params.mode, category=params.category, keyword=params.keyword,
            location=params.location, max_results=params.max_results,
            providers=self._providers_label(params),
        )
        prospects: list[Prospect] = []

        agency = params.search_source == SOURCE_AGENCY
        if params.search_source in (SOURCE_WEB, SOURCE_AGENCY) and params.mode in (MODE_SEARCH, MODE_BOTH):
            if agency:
                prospects = self._web_discovery(params, result, extra_filter=_blacklist_filter(),
                                                category=AGENCY_CATEGORY)
            else:
                prospects = self._web_discovery(params, result)
        elif params.mode in (MODE_SEARCH, MODE_BOTH):
            self.msg("Searching...", "info")
            request = SearchRequest(keyword=params.keyword, location=params.location,
                                    category=params.category, max_results=params.max_results)
            report = run_search(request, params.providers, self.client)
            result.provider_errors = report.errors
            for name, err in report.errors.items():
                label = PROVIDERS[name].label if name in PROVIDERS else name
                self.msg(f"{label}: {err}", "warning")
            result.n_found = len(report.results)
            per_source = ", ".join(f"{PROVIDERS[k].label} {v}" for k, v in report.counts.items())
            self.msg(f"Found {result.n_found} results" + (f" ({per_source})" if per_source else ""), "info")
            prospects = [result_to_prospect(r, params) for r in report.results]
        else:
            prospects = self._enrich_targets(params)
            result.n_found = len(prospects)
            self.msg(f"{result.n_found} siti da arricchire", "info")

        self.msg("Deduplicating...", "info")
        unique = deduplicate(prospects)[: params.max_results]
        result.n_unique = len(unique)
        with_domain = sum(1 for p in unique if p.domain)
        self.msg(f"{len(prospects)} → {len(unique)} prospect unici ({with_domain} con dominio)", "info")

        saved = [self._save_merged(p, result.run_id) for p in unique]
        result.prospect_ids = [p.id for p in saved]

        if params.mode in (MODE_ENRICH, MODE_BOTH):
            self._enrich(saved, params, result)
        qualified = False
        if agency and params.qualify and params.mode == MODE_BOTH:
            qualified = self._qualify(saved, params, result)

        self.db.finish_run(result.run_id, n_found=result.n_found, n_unique=result.n_unique,
                           n_enriched=result.n_enriched, n_failed=result.n_failed)
        elapsed = time.monotonic() - t0
        summary = f"Completed in {elapsed:.0f}s: {result.n_unique} prospect"
        if params.mode != MODE_SEARCH:
            summary += f", {result.n_enriched} arricchiti, {result.n_failed} falliti"
            if result.n_cached:
                summary += f", {result.n_cached} dalla cache"
        if qualified:
            summary += ", " + _qualify_summary(result)
        self.msg(summary, "success")

    @staticmethod
    def _web_provider_name(params: RunParams) -> str:
        return params.web_provider or user_settings.get("web_provider", "tavily")

    def _providers_label(self, params: RunParams) -> str:
        """Fonti registrate nella ricerca: provider web (+ modello AI per le agenzie)."""
        if params.search_source == SOURCE_WEB:
            return self._web_provider_name(params)
        if params.search_source == SOURCE_AGENCY:
            names = [self._web_provider_name(params)]
            if params.qualify:
                try:
                    names.append(qllm.get_classifier(params.llm_provider, self.client, params.llm_model).model)
                except Exception:  # noqa: BLE001 - solo un'etichetta
                    log.exception("modello AI non determinabile")
            return ",".join(names)
        return ",".join(params.providers or [])

    def _web_discovery(self, params: RunParams, result: RunResult,
                       extra_filter: Callable[[SearchResult], str | None] | None = None,
                       category: str = WEB_CATEGORY) -> list[Prospect]:
        """Scoperta via Web Search: un prospect per dominio aziendale trovato."""
        provider = web_search.get_provider(params.web_provider, self.client)
        self.msg(f"Searching the web ({provider.label})...", "info")
        if extra_filter is None:
            report = web_search.run_web_search(params.keyword, params.location, params.max_results,
                                               provider=provider)
        else:
            report = web_search.run_web_search(params.keyword, params.location, params.max_results,
                                               provider=provider, extra_filter=extra_filter)
        if report.errors:
            result.provider_errors = {provider.name: "; ".join(report.errors)}
        for err in report.errors:
            self.msg(f"{provider.label}: {err}", "warning")
        result.n_found = len(report.results)
        self.msg(f"Found {report.raw_count} results, {result.n_found} domini aziendali "
                 f"({report.api_calls} ricerche API)", "info")
        if report.filtered:
            self.msg(f"{report.filtered} risultati scartati dalla blacklist", "info")
        fallback = report.queries[0] if report.queries else params.keyword
        if category == WEB_CATEGORY:
            return [web_result_to_prospect(r, params, (r.extra or {}).get("query") or fallback)
                    for r in report.results]
        return [web_result_to_prospect(r, params, (r.extra or {}).get("query") or fallback, category)
                for r in report.results]

    def _enrich_targets(self, params: RunParams) -> list[Prospect]:
        if params.urls:
            out = []
            for u in params.urls:
                home = homepage_url(u)
                if home and not is_domain_in(normalize_domain(home), settings.NON_COMPANY_DOMAINS):
                    out.append(Prospect(website=home, source="manual", category=params.category,
                                        source_url=u, status=STATUS_FOUND))
            return out
        return self.db.list_prospects(statuses=[STATUS_FOUND, STATUS_FAILED], with_website=True,
                                      limit=params.max_results)

    def _save_merged(self, p: Prospect, run_id: int) -> Prospect:
        existing = self.db.find_existing(p) if not p.id else None
        if existing:
            merge_prospects(existing, p)
            existing.domain = existing.domain or p.domain
            if existing.status == STATUS_NO_WEBSITE and existing.website:
                existing.status = STATUS_FOUND
            p = existing
        self.db.save(p)
        self.db.link_run(run_id, p.id)
        return p

    def _enrich(self, prospects: list[Prospect], params: RunParams, result: RunResult) -> None:
        todo: list[Prospect] = []
        for p in prospects:
            if not p.website:
                continue
            if (not params.force_refresh and p.status == STATUS_ENRICHED
                    and self.db.recently_enriched(p.domain)):
                result.n_cached += 1
                continue
            todo.append(p)
        if result.n_cached:
            self.msg(f"{result.n_cached} siti già arricchiti di recente: riuso i dati salvati", "info")
        total = len(todo)
        if not total:
            self.msg("Nessun sito da visitare", "info")
            return
        self.msg("Enriching websites...", "info")
        done = 0
        workers = max(1, min(settings.MAX_WORKERS, total))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="enrich") as pool:
            futures = {pool.submit(_safe_enrich, self.crawler, p.website): p for p in todo}
            for fut in as_completed(futures):
                p = futures[fut]
                res = fut.result()
                self.last_enrichment[p.id] = res
                apply_enrichment(p, res)
                self.db.save(p)
                done += 1
                if p.status == STATUS_ENRICHED:
                    result.n_enriched += 1
                else:
                    result.n_failed += 1
                    log.info("enrichment fallito %s: %s", p.website, p.error_message)
                self.progress(done, total, p.company_name or p.domain or p.website)

    # ------------------------------------------------------------------------
    def _qualify(self, prospects: list[Prospect], params: RunParams, result: RunResult) -> bool:
        """Qualifica con l'AI le agenzie arricchite. Restituisce True se la qualifica è partita.
        Non cambia ``prospects.status``: gli esiti stanno in ``agency_qualifications``."""
        classifier = qllm.get_classifier(params.llm_provider, self.client, params.llm_model)
        if not classifier.is_configured():
            self.msg("Qualifica non configurata: inserisci la chiave API in «Impostazioni Agenzie»",
                     "warning")
            return False
        todo = [p for p in prospects if p.website and p.status == STATUS_ENRICHED]
        if not todo:
            self.msg("Nessuna agenzia da qualificare", "info")
            return False
        scoring, scoring_error = qconfig.load_scoring_with_error()
        if scoring_error:
            self.msg(f"Pesi dello score non validi ({scoring_error}): uso quelli predefiniti", "warning")
        self.msg("Qualifying agencies...", "info")
        workers = max(1, min(MAX_QUALIFY_WORKERS, settings.MAX_WORKERS, len(todo)))
        done = 0
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="qualify") as pool:
            futures = {pool.submit(qqualifier.qualify_site, p, self.client, classifier, scoring,
                                   self.last_enrichment.get(p.id)): p for p in todo}
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    q = fut.result()
                except Exception as exc:  # noqa: BLE001 - qualify_site non dovrebbe sollevare
                    log.exception("qualifica interrotta per %s", p.website)
                    q = qqualifier.failed_qualification(f"errore interno: {type(exc).__name__}: {exc}",
                                                        classifier)
                self.db.save_qualification(p.id, result.run_id, q)
                result.llm_cost_usd += q.cost_usd
                if q.status == "ok":
                    result.n_qualified += 1
                elif q.status == "excluded":
                    result.n_excluded += 1
                else:
                    result.n_qual_failed += 1
                    log.info("qualifica fallita %s: %s", p.website, q.error)
                done += 1
                self.progress(done, len(todo), p.company_name or p.domain or p.website)
        return True


def _blacklist_filter() -> Callable[[SearchResult], str | None]:
    """Filtro della scoperta: motivo dello scarto per i risultati in blacklist."""
    blacklist = qconfig.load_blacklist()
    return lambda r: blacklist.match(r.url, r.title)


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _qualify_summary(result: RunResult) -> str:
    cost = result.llm_cost_usd
    cost_text = f"{cost:.3f}" if cost < 0.01 else f"{cost:.2f}"
    return ", ".join([_plural(result.n_qualified, "qualificata", "qualificate"),
                      _plural(result.n_excluded, "esclusa", "escluse"),
                      _plural(result.n_qual_failed, "fallita", "fallite"),
                      f"costo AI {cost_text.replace('.', ',')} $"])


def _contacts_summary(r: ContactsResult) -> str:
    cost = r.llm_cost_usd
    cost_text = (f"{cost:.3f}" if cost < 0.01 else f"{cost:.2f}").replace(".", ",")
    return ", ".join([_plural(r.n_found, "decisore trovato", "decisori trovati"),
                      _plural(r.n_not_found, "non trovato", "non trovati"),
                      _plural(r.n_failed, "fallita", "fallite"),
                      _plural(r.n_linkedin, "profilo LinkedIn", "profili LinkedIn"),
                      _plural(r.n_email_site, "email dal sito", "email dal sito"),
                      _plural(r.n_email_guess, "email ipotizzata", "email ipotizzate"),
                      f"{_plural(r.web_calls, 'ricerca web', 'ricerche web')}",
                      f"costo AI {cost_text} $"])
