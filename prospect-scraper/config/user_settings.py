"""Impostazioni modificabili dall'utente (chiavi API, provider di Web Search).

Nell'app Mac non si possono impostare variabili d'ambiente: le impostazioni stanno in
un file JSON in ``DATA_HOME/user_settings.json`` (permessi 0600). Le variabili d'ambiente
``PS_*`` hanno la precedenza sul file. I valori delle chiavi non vengono mai loggati.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from config import settings
from utils.logging import get_logger

log = get_logger("user_settings")

DEFAULTS: dict[str, str] = {
    "web_provider": "tavily",
    "tavily_api_key": "",
    "brave_api_key": "",
    "searxng_url": "",
    # Agenzie (qualifica con AI)
    "llm_provider": "claude",
    "claude_model": "claude-haiku-4-5",
    "anthropic_api_key": "",
    "openai_api_key": "",
    "gemini_api_key": "",
}
_ENV_NAMES = {
    "web_provider": "PS_WEB_PROVIDER",
    "tavily_api_key": "PS_TAVILY_API_KEY",
    "brave_api_key": "PS_BRAVE_API_KEY",
    "searxng_url": "PS_SEARXNG_URL",
    "llm_provider": "PS_LLM_PROVIDER",
    "claude_model": "PS_CLAUDE_MODEL",
    "anthropic_api_key": "PS_ANTHROPIC_API_KEY",
    "openai_api_key": "PS_OPENAI_API_KEY",
    "gemini_api_key": "PS_GEMINI_API_KEY",
}
# Variabili d'ambiente "standard" dei provider: usate solo se manca sia PS_* sia il file (es. CI).
_ENV_FALLBACKS = {
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "openai_api_key": "OPENAI_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
}


def path() -> Path:
    """Percorso del file (risolto a ogni chiamata: ``DATA_HOME`` può cambiare nei test)."""
    return Path(settings.DATA_HOME) / "user_settings.json"


def load() -> dict:
    """Impostazioni salvate, complete dei valori predefiniti. Mai eccezioni."""
    values = dict(DEFAULTS)
    try:
        raw = json.loads(path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            values.update({k: v for k, v in raw.items() if isinstance(v, str)})
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        log.warning("impostazioni utente illeggibili (%s): uso i valori predefiniti", type(exc).__name__)
    return values


def get(key: str, default: str = "") -> str:
    """Valore di ``key``: variabile d'ambiente, poi file, poi ``default``."""
    env_name = _ENV_NAMES.get(key)
    env_value = os.environ.get(env_name, "").strip() if env_name else ""
    if env_value:
        return env_value
    value = (load().get(key) or "").strip()
    if not value and key == "searxng_url":
        value = (settings.SEARXNG_URL or "").strip()
    if not value and key in _ENV_FALLBACKS:
        value = os.environ.get(_ENV_FALLBACKS[key], "").strip()
    return value or default


def save(values: dict) -> None:
    """Unisce ``values`` alle impostazioni esistenti e scrive il file in modo atomico."""
    merged = load()
    merged.update({k: str(v).strip() for k, v in values.items() if k in DEFAULTS})
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".user_settings.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(merged, fh, ensure_ascii=False, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    log.info("impostazioni utente salvate (%s)", ", ".join(sorted(values)))
