"""Qualifica di una singola agenzia: pagine -> AI -> score. Non solleva mai: ogni errore diventa
una ``Qualification`` con status "failed" e un motivo leggibile."""

from __future__ import annotations

from datetime import date

from database.db import now_iso
from models.prospect import Prospect
from qualify.llm import Classifier, ClassifyError, cost_usd
from qualify.models import STATUS_EXCLUDED, STATUS_FAILED, STATUS_OK, Qualification
from qualify.pages import SiteContent, collect_site_content
from qualify.prompt import SYSTEM_PROMPT, build_user_message
from qualify.scoring import compute_score
from scrapers.http import HttpClient
from scrapers.website import EnrichmentResult
from utils.logging import get_logger

log = get_logger("qualify")

__all__ = ["Qualification", "classify_and_score", "failed_qualification", "qualify_site"]


def failed_qualification(reason: str, classifier: Classifier | None = None,
                         content: SiteContent | None = None) -> Qualification:
    q = Qualification(status=STATUS_FAILED, error=reason or "errore sconosciuto", qualified_at=now_iso())
    if classifier is not None:
        q.llm_provider, q.llm_model = classifier.name, classifier.model
    if content is not None:
        _fill_site(q, content)
    return q


def _fill_site(q: Qualification, content: SiteContent) -> None:
    q.pages_used = [p.url for p in content.pages]
    q.blog_status = content.blog.status
    q.blog_last_post = content.blog.last_post.isoformat() if content.blog.last_post else ""


def classify_and_score(content: SiteContent, classifier: Classifier, scoring: dict) -> Qualification:
    """Classifica i testi già raccolti con ``classifier`` e calcola lo score."""
    try:
        if content.error or not content.pages:
            return failed_qualification(content.error or "nessuna pagina disponibile", classifier, content)
        result = classifier.classify(SYSTEM_PROMPT, build_user_message(content))
    except ClassifyError as exc:
        q = failed_qualification(exc.reason, classifier, content)
        q.input_tokens, q.output_tokens, q.latency_s = exc.input_tokens, exc.output_tokens, exc.latency_s
        q.cost_usd = cost_usd(classifier.model, q.input_tokens, q.output_tokens, scoring.get("prezzi", {}))
        return q
    except Exception as exc:  # noqa: BLE001
        log.exception("errore imprevisto nella classificazione")
        return failed_qualification(f"errore interno: {type(exc).__name__}: {str(exc)[:250]}",
                                    classifier, content)
    try:
        data = result.data
        score, breakdown = compute_score(data, content.blog.status, scoring)
        q = Qualification(
            status=STATUS_EXCLUDED if data["is_agency"] == "no" else STATUS_OK,
            is_agency=data["is_agency"], servizi=list(data["servizi"]),
            servizi_altro=data["servizi_altro"], seo_level=data["seo_level"],
            servizi_ricorrenti=data["servizi_ricorrenti"], verticali=list(data["verticali"]),
            size_signal=data["size_signal"], note=data["note"], score=score,
            score_breakdown=breakdown,
            evidence={"agenzia": data["is_agency_evidence"], "seo": data["seo_evidence"],
                      "ricorrenti": data["ricorrenti_evidence"], "team": data["size_evidence"]},
            llm_provider=classifier.name, llm_model=classifier.model,
            input_tokens=result.input_tokens, output_tokens=result.output_tokens,
            cost_usd=cost_usd(classifier.model, result.input_tokens, result.output_tokens,
                              scoring.get("prezzi", {})),
            latency_s=round(result.latency_s, 2), qualified_at=now_iso())
        _fill_site(q, content)
        return q
    except Exception as exc:  # noqa: BLE001
        log.exception("errore imprevisto nel calcolo dello score")
        return failed_qualification(f"errore interno nello score: {type(exc).__name__}: {str(exc)[:250]}",
                                    classifier, content)


def qualify_site(prospect: Prospect, client: HttpClient, classifier: Classifier, scoring: dict,
                 enrichment: EnrichmentResult | None = None, today: date | None = None) -> Qualification:
    """Raccoglie le pagine del sito e le qualifica. Non solleva mai."""
    try:
        content = collect_site_content(prospect.website, client, enrichment, today=today)
    except Exception as exc:  # noqa: BLE001
        log.exception("errore nella raccolta delle pagine di %s", prospect.website)
        return failed_qualification(f"errore interno: {type(exc).__name__}", classifier)
    return classify_and_score(content, classifier, scoring)
