"""Avvio di Prospect Scraper con un doppio clic.

1. solo la prima volta (o se cambiano le dipendenze): crea l'ambiente ``.venv`` e installa i pacchetti;
2. avvia il server dell'app in background (o riusa quello già attivo);
3. apre l'app in una finestra dedicata (Edge/Chrome in "modalità app", altrimenti il browser predefinito).

Usa solo la libreria standard: funziona anche prima dell'installazione delle dipendenze.
Si chiude l'app con il pulsante "Chiudi app" nella barra laterale.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
VENV = APP_DIR / ".venv"
REQUIREMENTS = APP_DIR / "requirements.txt"
STATE_FILE = APP_DIR / "data" / "app_server.json"
LOG_DIR = APP_DIR / "logs"
SERVER_LOG = LOG_DIR / "server.log"
IS_WINDOWS = os.name == "nt"
IS_MAC = sys.platform == "darwin"


def say(msg: str) -> None:
    print(msg, flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


# --- 1. ambiente ----------------------------------------------------------------
def ensure_environment() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit(f"Serve Python 3.11 o superiore (trovato {sys.version.split()[0]}). "
                         "Scaricalo da https://www.python.org/downloads/")
    wanted = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    marker = VENV / ".requirements.sha256"
    if venv_python().exists() and marker.exists() and marker.read_text().strip() == wanted:
        return
    say("Preparazione dell'app (solo la prima volta, 1-3 minuti)...")
    if not venv_python().exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    subprocess.check_call([str(venv_python()), "-m", "pip", "install", "--disable-pip-version-check",
                           "-q", "-r", str(REQUIREMENTS)])
    marker.write_text(wanted)
    say("Installazione completata.")


# --- 2. server ------------------------------------------------------------------
def _http_ok(url: str, timeout: float = 2) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # localhost: niente proxy
    try:
        with opener.open(url, timeout=timeout) as r:
            return r.status == 200
    except OSError:
        return False


def is_running(port: int) -> bool:
    return _http_ok(f"http://127.0.0.1:{port}/_stcore/health")


def running_port() -> int | None:
    try:
        port = int(json.loads(STATE_FILE.read_text())["port"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return port if is_running(port) else None


def free_port(preferred: int = 8501) -> int:
    for port in (preferred, 0):
        with socket.socket() as s:
            if not IS_WINDOWS:  # porta in TIME_WAIT dopo una chiusura recente: riutilizzabile
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("nessuna porta libera")


def start_server(port: int) -> subprocess.Popen:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [str(venv_python()), "-m", "streamlit", "run", str(APP_DIR / "app.py"),
           "--server.port", str(port), "--server.address", "127.0.0.1", "--server.headless", "true"]
    kwargs: dict = {"cwd": str(APP_DIR), "stdin": subprocess.DEVNULL, "stderr": subprocess.STDOUT,
                    "stdout": open(SERVER_LOG, "a", encoding="utf-8")}
    if IS_WINDOWS:  # nessuna finestra nera; sopravvive alla chiusura del launcher
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(cmd, **kwargs)


def wait_until_ready(port: int, proc: subprocess.Popen, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_running(port):
            return
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    tail = SERVER_LOG.read_text(encoding="utf-8", errors="replace")[-2000:] if SERVER_LOG.exists() else ""
    raise SystemExit(f"L'app non si è avviata. Dettagli in {SERVER_LOG}\n\n{tail}")


# --- 3. finestra ----------------------------------------------------------------
def app_browser() -> str | None:
    """Browser Chromium (Edge/Chrome/Brave/Chromium) per aprire l'app senza barra degli indirizzi."""
    if IS_WINDOWS:
        roots = [os.environ.get(k, "") for k in ("ProgramFiles(x86)", "ProgramFiles", "LocalAppData")]
        rel = [r"Microsoft\Edge\Application\msedge.exe", r"Google\Chrome\Application\chrome.exe",
               r"BraveSoftware\Brave-Browser\Application\brave.exe"]
        paths = [os.path.join(root, r) for r in rel for root in roots if root]
    elif IS_MAC:
        paths = [f"/Applications/{app}.app/Contents/MacOS/{app}" for app in
                 ("Google Chrome", "Microsoft Edge", "Brave Browser", "Chromium")]
    else:
        paths = [shutil.which(n) or "" for n in ("google-chrome", "google-chrome-stable", "chromium",
                                                 "chromium-browser", "microsoft-edge", "brave-browser")]
    return next((p for p in paths if p and os.path.isfile(p)), None)


def open_window(url: str) -> None:
    exe = app_browser()
    if exe:
        kwargs: dict = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
        if not IS_WINDOWS:
            kwargs["start_new_session"] = True
        try:
            subprocess.Popen([exe, f"--app={url}", "--window-size=1400,900"], **kwargs)
            return
        except OSError:
            pass
    webbrowser.open(url)


# --------------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    os.chdir(APP_DIR)
    open_it = "--no-window" not in argv
    ensure_environment()
    port = running_port()
    if port:
        say("L'app è già aperta: la porto in primo piano.")
    else:
        port = free_port()
        say("Avvio dell'app...")
        proc = start_server(port)
        wait_until_ready(port, proc)
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({"port": port, "pid": proc.pid}))
    url = f"http://localhost:{port}"
    if open_it:
        open_window(url)
    say(f"Prospect Scraper è pronto: {url}\nPuoi chiudere questa finestra. Per spegnere l'app usa "
        "il pulsante \"Chiudi app\" nella barra laterale.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except subprocess.CalledProcessError as exc:
        say(f"Installazione non riuscita ({exc}). Controlla la connessione a Internet e riprova.")
        sys.exit(1)
