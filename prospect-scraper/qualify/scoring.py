"""Score 0-100 dell'agenzia: somma dei pesi (modificabili) per ogni segnale."""

from __future__ import annotations


def compute_score(q: dict, blog_status: str, weights: dict) -> tuple[int | None, dict]:
    """(score, dettaglio). ``None`` se l'azienda non è un'agenzia (is_agency == "no")."""
    if q.get("is_agency") == "no":
        return None, {}
    breakdown = {
        "seo_level": weights["seo_level"].get(q.get("seo_level", ""), 0),
        "servizi_ricorrenti": weights["servizi_ricorrenti"].get(q.get("servizi_ricorrenti", ""), 0),
        "size_signal": weights["size_signal"].get(q.get("size_signal", ""), 0),
        "blog": weights["blog"].get(blog_status, 0),
        "is_agency": weights["is_agency"].get(q.get("is_agency", ""), 0),
    }
    low, high = weights["limiti"]["min"], weights["limiti"]["max"]
    score = max(low, min(high, sum(breakdown.values())))
    return int(round(score)), breakdown
