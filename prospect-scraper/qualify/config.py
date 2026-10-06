"""Blacklist e pesi dello score: file modificabili dall'utente.

I file predefiniti stanno in ``config/`` (dentro l'app); alla prima lettura vengono copiati
nella cartella dati (``settings.DATA_HOME``) e da lì l'utente li modifica (anche dall'app).
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlsplit

from config import settings
from utils.logging import get_logger
from utils.normalization import is_domain_in, normalize_domain, registrable_domain

log = get_logger("qualify.config")

BLACKLIST_FILE = "agency_blacklist.txt"
SCORING_FILE = "agency_scoring.toml"

# sezioni numeriche: nome -> chiavi attese (le chiavi mancanti prendono il valore predefinito)
_WEIGHT_SECTIONS = {
    "seo_level": ("assente", "accennata", "strutturata"),
    "servizi_ricorrenti": ("si", "no"),
    "size_signal": ("1", "2-5", "6-20", "20+", "non determinabile"),
    "blog": ("assente", "fermo", "attivo", "non determinabile"),
    "is_agency": ("si", "dubbio"),
}


def bundled_path(name: str) -> Path:
    """Percorso del file predefinito (anche dentro l'app PyInstaller)."""
    base = Path(getattr(sys, "_MEIPASS", "")) if getattr(sys, "_MEIPASS", None) else None
    if base and (base / "config" / name).exists():
        return base / "config" / name
    return Path(__file__).resolve().parent.parent / "config" / name


def user_path(name: str) -> Path:
    return Path(settings.DATA_HOME) / name


def _ensure_user_file(name: str) -> Path:
    """Copia il file predefinito nella cartella dati se manca. Mai eccezioni."""
    target = user_path(name)
    if not target.exists():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundled_path(name), target)
        except OSError as exc:
            log.warning("impossibile creare %s: %s", target, type(exc).__name__)
    return target


def _read(name: str) -> str:
    """Testo del file utente (creato se manca); se illeggibile, quello predefinito."""
    try:
        return _ensure_user_file(name).read_text(encoding="utf-8")
    except OSError:
        return bundled_path(name).read_text(encoding="utf-8")


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        Path(tmp).replace(path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


# --- blacklist --------------------------------------------------------------------
@dataclass
class Blacklist:
    domains: set[str] = field(default_factory=set)
    phrases: list[str] = field(default_factory=list)

    def match(self, url: str, title: str = "") -> str | None:
        """Motivo dello scarto ("dominio in blacklist: x" / "frase in blacklist: y") o None."""
        host, reg = normalize_domain(url), registrable_domain(url)
        for d in sorted(self.domains):
            if is_domain_in(reg, {d}) or is_domain_in(host, {d}):
                return f"dominio in blacklist: {d}"
        if not self.phrases:
            return None
        try:
            path = unquote(urlsplit(url or "").path)
        except ValueError:
            path = ""
        haystacks = (_squash(title), _squash(path.replace("-", " ").replace("_", " ")))
        for phrase in self.phrases:
            if any(phrase in h for h in haystacks):
                return f"frase in blacklist: {phrase}"
        return None


def _squash(text: str) -> str:
    return " ".join((text or "").lower().split())


def _clean_domain(value: str) -> str:
    value = value.strip().lower()
    return normalize_domain(value) or value.removeprefix("www.").strip("/")


def parse_blacklist(text: str) -> Blacklist:
    bl, section = Blacklist(), "domini"
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if section == "frasi":
            phrase = _squash(line)
            if phrase and phrase not in bl.phrases:
                bl.phrases.append(phrase)
        elif section == "domini":
            domain = _clean_domain(line)
            if domain:
                bl.domains.add(domain)
    return bl


def blacklist_text() -> str:
    return _read(BLACKLIST_FILE)


def load_blacklist() -> Blacklist:
    return parse_blacklist(blacklist_text())


def save_blacklist_text(text: str) -> None:
    _write_atomic(user_path(BLACKLIST_FILE), text if text.endswith("\n") else text + "\n")
    log.info("blacklist agenzie salvata")


# --- pesi dello score -------------------------------------------------------------
def _number(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where}: serve un numero (trovato {value!r})")
    return value


def validate_scoring(data: dict, defaults: dict | None = None) -> dict:
    """Controlla i tipi e completa le voci mancanti con i valori predefiniti.
    Solleva ValueError con un messaggio leggibile."""
    defaults = defaults if defaults is not None else _default_scoring()
    out: dict = {}
    for section, keys in _WEIGHT_SECTIONS.items():
        raw = data.get(section, {})
        if not isinstance(raw, dict):
            raise ValueError(f"[{section}]: sezione non valida")
        out[section] = {}
        for key in keys:
            if key in raw:
                out[section][key] = _number(raw[key], f"[{section}] {key}")
            else:
                out[section][key] = defaults[section][key]
    limits = data.get("limiti", {})
    if not isinstance(limits, dict):
        raise ValueError("[limiti]: sezione non valida")
    out["limiti"] = {k: _number(limits.get(k, defaults["limiti"][k]), f"[limiti] {k}")
                     for k in ("min", "max")}
    if out["limiti"]["min"] > out["limiti"]["max"]:
        raise ValueError("[limiti]: min non può superare max")
    llm = data.get("llm", {})
    if not isinstance(llm, dict):
        raise ValueError("[llm]: sezione non valida")
    out["llm"] = dict(defaults["llm"])
    for key, value in llm.items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"[llm] {key}: serve il nome di un modello tra virgolette")
        out["llm"][key] = value.strip()
    prices = data.get("prezzi", {})
    if not isinstance(prices, dict):
        raise ValueError("[prezzi]: sezione non valida")
    out["prezzi"] = {k: list(v) for k, v in defaults["prezzi"].items()}
    for model, pair in prices.items():
        if (not isinstance(pair, list) or len(pair) != 2
                or any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in pair)):
            raise ValueError(f"[prezzi] {model}: servono due numeri [input, output]")
        out["prezzi"][model] = [float(pair[0]), float(pair[1])]
    return out


def _parse_toml(text: str) -> dict:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"file dei pesi non valido: {exc}") from exc


def _default_scoring() -> dict:
    data = _parse_toml(bundled_path(SCORING_FILE).read_text(encoding="utf-8"))
    return validate_scoring(data, defaults=_raw_defaults(data))


def _raw_defaults(data: dict) -> dict:
    """Il file predefinito è completo: i suoi valori fanno da base a sé stesso."""
    return {**{s: dict(data[s]) for s in (*_WEIGHT_SECTIONS, "limiti", "llm")},
            "prezzi": {k: list(v) for k, v in data["prezzi"].items()}}


def load_scoring_with_error() -> tuple[dict, str]:
    """(pesi, errore). Se il file utente è rotto: pesi predefiniti + testo dell'errore."""
    default = _default_scoring()
    try:
        return validate_scoring(_parse_toml(_read(SCORING_FILE)), default), ""
    except ValueError as exc:
        log.warning("pesi dello score non validi (%s): uso quelli predefiniti", exc)
        return default, str(exc)


def load_scoring() -> dict:
    return load_scoring_with_error()[0]


def scoring_text() -> str:
    return _read(SCORING_FILE)


def save_scoring_text(text: str) -> None:
    """Valida PRIMA di scrivere: se non è valido solleva ValueError e il file non cambia."""
    validate_scoring(_parse_toml(text), _default_scoring())
    _write_atomic(user_path(SCORING_FILE), text if text.endswith("\n") else text + "\n")
    log.info("pesi dello score salvati")
