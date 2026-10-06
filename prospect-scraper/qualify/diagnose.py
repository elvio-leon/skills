"""Diagnostica della qualifica: UNA chiamata di prova al modello configurato, con la risposta grezza
o l'errore completo. Usata dal pulsante «Prova connessione AI» e da ``desktop.py --diagnose-ai``.
La chiave non viene mai mostrata (solo un'indicazione mascherata)."""

from __future__ import annotations

import time
import traceback

from qualify.llm import Classifier, ClassifyError, extract_json
from qualify.prompt import SYSTEM_PROMPT
from qualify.schema import validate_analysis

SAMPLE_USER_MESSAGE = """Dominio: agenzia-esempio.it

### [home] https://agenzia-esempio.it/
Titolo: Agenzia Esempio | Comunicazione e web a Milano
Siamo un'agenzia di comunicazione di Milano. Realizziamo siti web ed e-commerce, gestiamo i social
media dei nostri clienti con un canone mensile, curiamo campagne Google Ads e Meta Ads.
Tra i servizi anche consulenza SEO. Il nostro team è composto da 8 persone.
Clienti: ristoranti, hotel e cantine della Lombardia.
"""


def mask_key(key: str) -> str:
    key = (key or "").strip()
    if not key:
        return "(nessuna chiave)"
    return f"{key[:7]}…{key[-4:]} ({len(key)} caratteri)" if len(key) > 12 else "(chiave troppo corta)"


def run_diagnosis(classifier: Classifier) -> dict:
    """Esegue una chiamata di prova e restituisce un resoconto (mai eccezioni)."""
    report: dict = {"provider": classifier.name, "modello": classifier.model,
                    "chiave": mask_key(classifier.api_key), "configurato": classifier.is_configured()}
    if not classifier.is_configured():
        report["esito"] = "non configurato: manca la chiave API (o la libreria del provider)"
        return report
    t0 = time.monotonic()
    try:
        raw = classifier._call(SYSTEM_PROMPT, SAMPLE_USER_MESSAGE)   # una sola chiamata, niente retry
    except ClassifyError as exc:
        report.update(esito="ERRORE", errore=exc.reason, secondi=round(time.monotonic() - t0, 2))
        return report
    except Exception as exc:  # noqa: BLE001
        report.update(esito="ERRORE", errore=f"{type(exc).__name__}: {exc}",
                      traceback=traceback.format_exc(limit=6), secondi=round(time.monotonic() - t0, 2))
        return report
    report.update(secondi=round(time.monotonic() - t0, 2), risposta_grezza=raw.text[:4000],
                  token_input=raw.input_tokens, token_output=raw.output_tokens)
    if raw.meta:
        report["dettagli_risposta"] = raw.meta
    try:
        report["json_interpretato"] = validate_analysis(extract_json(raw.text))
        report["esito"] = "OK"
    except Exception as exc:  # noqa: BLE001
        report.update(esito="ERRORE", errore=f"risposta non interpretabile: {type(exc).__name__}: {exc}")
    return report
