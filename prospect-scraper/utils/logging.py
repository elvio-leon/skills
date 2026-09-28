"""Logging tecnico su file + buffer in memoria per scaricare il log di un'esecuzione."""

from __future__ import annotations

import logging
import threading
from logging.handlers import RotatingFileHandler

from config import settings

LOGGER_NAME = "prospect_scraper"
_FORMAT = "%(asctime)s %(levelname)-7s %(threadName)s %(name)s: %(message)s"
_setup_lock = threading.Lock()


def get_logger(name: str | None = None) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"{LOGGER_NAME}.{name}" if name else LOGGER_NAME)


def setup_logging() -> None:
    root = logging.getLogger(LOGGER_NAME)
    with _setup_lock:
        if getattr(root, "_ps_configured", False):
            return
        root.setLevel(logging.DEBUG)
        root.propagate = False
        try:
            settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
            fh = RotatingFileHandler(
                settings.LOG_DIR / "prospect_scraper.log",
                maxBytes=2_000_000, backupCount=3, encoding="utf-8",
            )
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter(_FORMAT))
            root.addHandler(fh)
        except OSError:
            pass  # log su file non disponibile: si continua con il buffer in memoria
        root._ps_configured = True  # type: ignore[attr-defined]


class RunLogCapture(logging.Handler):
    """Raccoglie i log tecnici di una singola esecuzione (per il download in UI)."""

    def __init__(self, level: int = logging.DEBUG):
        super().__init__(level)
        self.lines: list[str] = []
        self.setFormatter(logging.Formatter(_FORMAT))
        self._lock_lines = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:  # noqa: BLE001
            return
        with self._lock_lines:
            self.lines.append(line)

    def __enter__(self):
        get_logger().addHandler(self)
        return self

    def __exit__(self, *exc):
        get_logger().removeHandler(self)
        return False

    def text(self) -> str:
        with self._lock_lines:
            return "\n".join(self.lines)
