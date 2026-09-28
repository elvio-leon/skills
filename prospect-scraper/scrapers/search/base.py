"""Interfaccia comune dei search provider."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from scrapers.http import HttpClient, default_client


@dataclass
class SearchResult:
    title: str
    url: str          # sito del prospect se noto, altrimenti "" (mai inventato)
    snippet: str
    source: str
    extra: dict[str, Any] = field(default_factory=dict)  # dati strutturati opzionali

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "url": self.url, "snippet": self.snippet,
                "source": self.source, "extra": self.extra}


@dataclass
class SearchRequest:
    keyword: str
    location: str = ""
    category: str = "Custom"
    max_results: int = 20


class SearchProvider(ABC):
    """Per aggiungere una fonte: sottoclasse + registrazione in ``scrapers.search.PROVIDERS``."""

    name: str = "base"
    label: str = "Base"

    def __init__(self, client: HttpClient | None = None):
        self.client = client or default_client()

    def is_available(self) -> bool:
        return True

    @abstractmethod
    def search(self, request: SearchRequest) -> list[SearchResult]:
        ...


# --- utilità comuni per interpretare la keyword -----------------------------

STOPWORDS = {
    "di", "del", "della", "dei", "delle", "degli", "in", "a", "ad", "e", "ed", "con",
    "per", "da", "the", "of", "and", "in", "at", "for", "il", "lo", "la", "i", "gli", "le",
}


def tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,;/]+", (text or "").lower()) if t]


def remove_phrases(text: str, phrases: list[str]) -> tuple[str, list[str]]:
    """Rimuove dal testo le frasi trovate (match a parola intera, le più lunghe prima)."""
    found = []
    low = f" {(text or '').lower()} "
    for phrase in sorted(set(phrases), key=len, reverse=True):
        pattern = r"(?<![\w&])" + re.escape(phrase) + r"(?![\w&])"
        if re.search(pattern, low):
            found.append(phrase)
            low = re.sub(pattern, " ", low)
    return re.sub(r"\s+", " ", low).strip(), found


def leftover_words(text: str) -> list[str]:
    return [t for t in tokenize(text) if t not in STOPWORDS and len(t) > 1]
