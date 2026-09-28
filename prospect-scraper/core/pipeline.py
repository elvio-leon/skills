"""Orchestrazione: ricerca -> normalizzazione -> deduplicazione -> salvataggio ->
website enrichment concorrente -> aggiornamento DB. Indipendente dalla UI."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable

from config import settings
from database.db import Database, now_iso
from models.prospect import STATUS_ENRICHED, STATUS_FAILED, STATUS_FOUND, STATUS_NO_WEBSITE, Prospect
from scrapers import contacts, social
from scrapers.company import company_name_from_title
from scrapers.http import HttpClient, default_client
from scrapers.search import PROVIDERS, SearchRequest, SearchResult, run_search
from scrapers.website import EnrichmentResult, WebsiteCrawler
from utils.deduplication import deduplicate, merge_prospects
from utils.logging import RunLogCapture, get_logger
from utils.normalization import homepage_url, is_domain_in, normalize_domain

log = get_logger("pipeline")

MODE_SEARCH = "Search"
MODE_ENRICH = "Website enrichment"
MODE_BOTH = "Search + enrichment"
MODES = [MODE_SEARCH, MODE_ENRICH, MODE_BOTH]

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

    def run(self, params: RunParams) -> RunResult:
        result = RunResult()
        with RunLogCapture() as capture:
            try:
                self._run(params, result)
            except Exception as exc:  # noqa: BLE001
                log.exception("esecuzione interrotta")
                result.fatal_error = f"{type(exc).__name__}: {exc}"
                self.msg(f"Errore imprevisto: {result.fatal_error}", "error")
            result.log_text = capture.text()
        return result

    # ------------------------------------------------------------------------
    def _run(self, params: RunParams, result: RunResult) -> None:
        t0 = time.monotonic()
        log.info("run: %s", params)
        result.run_id = self.db.start_run(
            mode=params.mode, category=params.category, keyword=params.keyword,
            location=params.location, max_results=params.max_results,
            providers=",".join(params.providers or []),
        )
        prospects: list[Prospect] = []

        if params.mode in (MODE_SEARCH, MODE_BOTH):
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

        self.db.finish_run(result.run_id, n_found=result.n_found, n_unique=result.n_unique,
                           n_enriched=result.n_enriched, n_failed=result.n_failed)
        elapsed = time.monotonic() - t0
        summary = f"Completed in {elapsed:.0f}s: {result.n_unique} prospect"
        if params.mode != MODE_SEARCH:
            summary += f", {result.n_enriched} arricchiti, {result.n_failed} falliti"
            if result.n_cached:
                summary += f", {result.n_cached} dalla cache"
        self.msg(summary, "success")

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
                apply_enrichment(p, res)
                self.db.save(p)
                done += 1
                if p.status == STATUS_ENRICHED:
                    result.n_enriched += 1
                else:
                    result.n_failed += 1
                    log.info("enrichment fallito %s: %s", p.website, p.error_message)
                self.progress(done, total, p.company_name or p.domain or p.website)
