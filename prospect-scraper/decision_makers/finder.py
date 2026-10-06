"""Contatti del decisore di UNA agenzia: pagine -> AI -> verifica -> LinkedIn -> email.
Non solleva mai: ogni errore diventa un ``DecisionMaker`` con status "fallito" e un motivo."""

from __future__ import annotations

from database.db import now_iso
from decision_makers import email as dm_email
from decision_makers.extract import (SCHEMA, SYSTEM_PROMPT, build_user_message, choose_person,
                                     collect_people_pages, validate_people)
from decision_makers.linkedin import agency_name, find_linkedin
from decision_makers.models import (EMAIL_GUESS, EMAIL_SITE, LINKEDIN_NOT_FOUND, LINKEDIN_NOT_SEARCHED,
                                    STATUS_FAILED, STATUS_FOUND, STATUS_NOT_FOUND, DecisionMaker)
from models.prospect import Prospect
from qualify.llm import Classifier, ClassifyError, cost_usd
from scrapers.http import HttpClient
from scrapers.web_search.base import WebSearchProvider
from utils.logging import get_logger

log = get_logger("decision_makers")


def _split(emails: str) -> list[str]:
    return [e.strip() for e in (emails or "").replace(",", ";").split(";") if e.strip()]


def find_decision_maker(prospect: Prospect, client: HttpClient, classifier: Classifier,
                        web_provider: WebSearchProvider | None, prices: dict | None = None) -> DecisionMaker:
    """``web_provider`` None (o non configurato) = LinkedIn non cercato."""
    dm = DecisionMaker(llm_provider=classifier.name, llm_model=classifier.model, found_at=now_iso())
    try:
        return _find(prospect, client, classifier, web_provider, prices or {}, dm)
    except Exception as exc:  # noqa: BLE001
        log.exception("ricerca del decisore interrotta per %s", prospect.website)
        dm.status, dm.error = STATUS_FAILED, f"errore interno: {type(exc).__name__}: {str(exc)[:200]}"
        return dm


def _find(prospect: Prospect, client: HttpClient, classifier: Classifier,
          web_provider: WebSearchProvider | None, prices: dict, dm: DecisionMaker) -> DecisionMaker:
    # 1. decisore dalle pagine del sito
    content = collect_people_pages(prospect.website, client)
    dm.pages_used = [p.url for p in content.pages]
    if content.error or not content.pages:
        dm.status, dm.error = STATUS_FAILED, f"sito: {content.error or 'nessuna pagina disponibile'}"
        return dm
    company = agency_name(prospect.company_name, prospect.domain)
    try:
        result = classifier.classify(SYSTEM_PROMPT, build_user_message(content, company),
                                     schema=SCHEMA, validator=validate_people)
    except ClassifyError as exc:
        dm.input_tokens, dm.output_tokens, dm.latency_s = exc.input_tokens, exc.output_tokens, exc.latency_s
        dm.cost_usd = cost_usd(classifier.model, dm.input_tokens, dm.output_tokens, prices)
        dm.status, dm.error = STATUS_FAILED, f"AI: {exc.reason}"
        return dm
    dm.input_tokens, dm.output_tokens = result.input_tokens, result.output_tokens
    dm.latency_s = round(result.latency_s, 2)
    dm.cost_usd = cost_usd(classifier.model, dm.input_tokens, dm.output_tokens, prices)

    person, rejected = choose_person(result.data["persone"], content.text)
    if rejected:
        log.info("%s: persone scartate perché non presenti nel testo: %s", prospect.domain, rejected)
    if person is None:
        dm.status = STATUS_NOT_FOUND
        dm.error = "nomi proposti dall'AI non presenti nel testo del sito" if rejected else ""
        return dm
    dm.status = STATUS_FOUND
    dm.nome, dm.cognome, dm.ruolo = person["nome"].strip(), person["cognome"].strip(), person["ruolo"].strip()
    dm.evidence, dm.source_url = person["citazione"], person["pagina_url"]

    # 2. LinkedIn: solo URL e titolo dei risultati di ricerca
    if web_provider is None or not web_provider.is_configured():
        dm.linkedin_confidence = f"{LINKEDIN_NOT_SEARCHED}: Web Search non configurata"
    else:
        match = find_linkedin(web_provider, dm.nome, dm.cognome, company, dm.ruolo, prospect.domain)
        dm.web_calls += match.calls
        if match.error:
            dm.linkedin_confidence = f"{LINKEDIN_NOT_SEARCHED}: {match.error}"
        elif match.url:
            dm.linkedin_url, dm.linkedin_title, dm.linkedin_confidence = match.url, match.title, match.confidence
        else:
            dm.linkedin_confidence = LINKEDIN_NOT_FOUND

    # 3. email: nominativa dal sito, altrimenti ipotesi nome@dominio
    site_emails = list(dict.fromkeys(_split(prospect.email) + _split(prospect.emails) + content.emails))
    found = dm_email.nominative_email(site_emails, dm.nome, dm.cognome, prospect.domain or content.domain)
    if found:
        dm.email, dm.email_source, dm.email_verified = found, EMAIL_SITE, True
    else:
        guess = dm_email.guess_email(dm.nome, prospect.domain or content.domain)
        if guess:
            dm.email, dm.email_source, dm.email_verified = guess, EMAIL_GUESS, False
    return dm
