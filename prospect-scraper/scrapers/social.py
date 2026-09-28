"""Individuazione dei profili social realmente linkati nelle pagine.

Salva solo URL presenti nell'HTML (href o JSON-LD sameAs), normalizzati.
Esclude link di condivisione, post singoli, plugin e intent.
"""

from __future__ import annotations

import re
from collections import Counter
from urllib.parse import urlsplit, urlunsplit

NETWORKS = {
    "linkedin": ("linkedin.com",),
    "instagram": ("instagram.com",),
    "facebook": ("facebook.com", "fb.com", "fb.me"),
    "youtube": ("youtube.com", "youtu.be"),
    "twitter": ("twitter.com", "x.com"),
}

_EXCLUDE = {
    "linkedin": re.compile(r"^/(shareArticle|sharing|feed|posts|pulse|jobs/view|login|signup|authwall)", re.I),
    "instagram": re.compile(r"^/(p|reel|reels|tv|explore|accounts|stories|direct)(/|$)", re.I),
    "facebook": re.compile(r"^/(sharer|share|dialog|plugins|tr|login|photo|photos|events|groups/?$|"
                           r"watch|story\.php|permalink\.php|hashtag|l\.php|policies|privacy)", re.I),
    "youtube": re.compile(r"^/(watch|embed|shorts|playlist|results|redirect|iframe_api|live)", re.I),
    "twitter": re.compile(r"^/(intent|share|home|search|hashtag|i/|widgets)", re.I),
}
_ALLOW = {
    "linkedin": re.compile(r"^/(company|in|school|showcase)/[^/]+", re.I),
    "youtube": re.compile(r"^/(@[^/]+|channel/[^/]+|c/[^/]+|user/[^/]+)", re.I),
}
_CANONICAL_HOST = {
    "linkedin": "www.linkedin.com", "instagram": "www.instagram.com",
    "facebook": "www.facebook.com", "youtube": "www.youtube.com", "twitter": "x.com",
}


def classify(url: str) -> str | None:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return None
    for network, domains in NETWORKS.items():
        if any(host == d or host.endswith("." + d) for d in domains):
            return network
    return None


def normalize_social_url(url: str) -> tuple[str, str] | None:
    """-> (network, url normalizzato) oppure None se non è un profilo."""
    url = (url or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    if not url.lower().startswith(("http://", "https://")):
        if re.match(r"^(www\.)?[a-z0-9.-]+\.(com|me)/", url, re.I):
            url = "https://" + url
        else:
            return None
    network = classify(url)
    if not network:
        return None
    parts = urlsplit(url)
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if network == "facebook" and path.lower().startswith("/pages/"):
        pass  # /pages/Nome/123 è un profilo valido
    elif network == "facebook" and path.lower() == "/profile.php":
        m = re.search(r"id=(\d+)", parts.query)
        if not m:
            return None
        return network, f"https://www.facebook.com/profile.php?id={m.group(1)}"
    if _EXCLUDE[network].search(path):
        return None
    if network in _ALLOW:
        m = _ALLOW[network].match(path)
        if not m:
            return None
        path = m.group(0)
    else:
        segments = [s for s in path.split("/") if s]
        if not segments:
            return None
        path = "/" + segments[0]
        if network == "facebook" and len(segments) > 1 and segments[0].lower() == "pages":
            path = "/" + "/".join(segments[:3])
    if network == "youtube" and (urlsplit(url).hostname or "").endswith("youtu.be"):
        return None  # link a video
    path = path.rstrip("/")
    return network, urlunsplit(("https", _CANONICAL_HOST[network], path, "", ""))


def extract_socials(urls: list[str]) -> dict[str, list[str]]:
    """Per ogni social, gli URL di profilo trovati (i più frequenti prima)."""
    counters: dict[str, Counter] = {n: Counter() for n in NETWORKS}
    for u in urls:
        res = normalize_social_url(u)
        if res:
            counters[res[0]][res[1]] += 1
    return {n: [u for u, _ in c.most_common()] for n, c in counters.items() if c}
