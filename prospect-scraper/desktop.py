"""Prospect Scraper come app desktop.

- il server dell'interfaccia (Streamlit) gira in un processo figlio, solo su 127.0.0.1;
- la finestra è nativa (WKWebView su Mac tramite pywebview): niente browser, niente terminale;
- chiudendo la finestra si chiude tutto; se l'app viene terminata a forza, il server si
  spegne da solo (controlla che il processo padre sia ancora vivo).

È il punto d'ingresso dell'app impacchettata con PyInstaller (vedi packaging/build_mac.sh).
Da sorgente: ``python desktop.py`` (richiede ``pip install pywebview``, altrimenti usa il browser).
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "Prospect Scraper"
FROZEN = getattr(sys, "frozen", False)
HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

LOADING_HTML = """<!doctype html><html><body style="margin:0;height:100vh;display:flex;
align-items:center;justify-content:center;font-family:-apple-system,system-ui,sans-serif;
background:#f5f7fb;color:#305496"><div style="text-align:center"><div style="font-size:42px">🔎</div>
<h2 style="font-weight:600">Prospect Scraper</h2><p style="color:#667">Avvio in corso…</p></div></body></html>"""

ERROR_HTML = """<!doctype html><html><body style="font-family:-apple-system,system-ui,sans-serif;
padding:40px;color:#333"><h2>L'app non è riuscita ad avviarsi</h2>
<p>Chiudi la finestra e riprova. Se il problema continua, invia il file di log:</p>
<pre style="background:#f3f3f3;padding:12px;white-space:pre-wrap">{log}</pre></body></html>"""


def data_home() -> Path:
    if os.environ.get("PS_HOME"):
        base = Path(os.environ["PS_HOME"])
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
    else:
        base = Path.home() / ".local" / "share" / "prospect-scraper"
    base.mkdir(parents=True, exist_ok=True)
    return base


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def is_up(port: int) -> bool:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"http://127.0.0.1:{port}/_stcore/health", timeout=2) as r:
            return r.status == 200
    except OSError:
        return False


def _pid_alive(pid: int) -> bool:
    if os.name == "nt":
        return True  # su Windows il figlio viene chiuso dal padre alla chiusura della finestra
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


# --- processo figlio: server ----------------------------------------------------
def run_server(port: int, parent_pid: int) -> None:
    os.chdir(HERE)  # qui c'è .streamlit/config.toml
    sys.path.insert(0, str(HERE))

    def watchdog():
        while _pid_alive(parent_pid):
            time.sleep(2)
        os._exit(0)

    threading.Thread(target=watchdog, daemon=True).start()
    from streamlit.web import bootstrap

    flags = {
        "server.port": port, "server.address": "127.0.0.1", "server.headless": True,
        "server.fileWatcherType": "none", "server.runOnSave": False,
        "global.developmentMode": False, "browser.gatherUsageStats": False,
        "client.toolbarMode": "minimal",
    }
    bootstrap.load_config_options(flag_options=flags)
    bootstrap.run(str(HERE / "app.py"), False, [], flags)


def _bundle_imports() -> None:  # pragma: no cover - mai eseguita
    """Solo per PyInstaller: così include i moduli dell'app e le loro dipendenze."""
    import bs4, lxml.etree, openpyxl, pandas, phonenumbers, requests  # noqa: F401,E401
    import app  # noqa: F401
    import core.pipeline, database.db, exporters.export, scrapers.search, scrapers.website  # noqa: F401,E401
    import anthropic  # noqa: F401  (qualifica agenzie con Claude)
    import qualify.blog, qualify.config, qualify.llm, qualify.models, qualify.pages  # noqa: F401,E401
    import qualify.prompt, qualify.qualifier, qualify.schema, qualify.scoring  # noqa: F401,E401


# --- processo principale: finestra ----------------------------------------------
def start_server_process(home: Path, port: int) -> subprocess.Popen:
    env = {**os.environ, "PS_HOME": str(home), "PS_DESKTOP": "1"}
    args = ["--server", str(port), str(os.getpid())]
    cmd = [sys.executable, *args] if FROZEN else [sys.executable, str(Path(__file__).resolve()), *args]
    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = open(log_dir / "server.log", "a", encoding="utf-8")
    kwargs: dict = {"env": env, "stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(cmd, **kwargs)


def wait_for_server(port: int, proc: subprocess.Popen, timeout: float = 90) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_up(port):
            return True
        if proc.poll() is not None:
            return False
        time.sleep(0.3)
    return False


def log_tail(home: Path) -> str:
    path = home / "logs" / "server.log"
    try:
        return f"{path}\n\n" + path.read_text(encoding="utf-8", errors="replace")[-3000:]
    except OSError:
        return str(path)


def main(argv: list[str]) -> int:
    if "--check-imports" in argv:  # usato dalla build: le librerie caricate solo al bisogno ci sono?
        import anthropic

        import qualify.llm  # noqa: F401
        import qualify.qualifier  # noqa: F401
        print(f"IMPORT OK anthropic {anthropic.__version__}", flush=True)
        return 0

    if "--server" in argv:
        i = argv.index("--server")
        run_server(int(argv[i + 1]), int(argv[i + 2]))
        return 0

    selftest = "--selftest" in argv
    home = data_home()
    port = free_port()
    proc = start_server_process(home, port)
    url = f"http://127.0.0.1:{port}"
    result = {"code": 0}

    try:
        import webview
    except ImportError:
        webview = None

    try:
        if webview is None or "--browser" in argv:
            if not wait_for_server(port, proc):
                print(log_tail(home), file=sys.stderr)
                return 1
            webbrowser.open(url)
            proc.wait()
            return 0

        window = webview.create_window(APP_NAME, html=LOADING_HTML, width=1400, height=900,
                                       min_size=(1000, 650))

        def on_start():
            if not wait_for_server(port, proc):
                result["code"] = 1
                window.load_html(ERROR_HTML.format(log=log_tail(home)))
                if selftest:
                    print(log_tail(home), file=sys.stderr)
                    window.destroy()
                return
            window.load_url(url)
            if selftest:  # usato dalla build: l'interfaccia deve comparire davvero
                ok = False
                for _ in range(120):
                    time.sleep(1)
                    try:
                        text = window.evaluate_js("document.body ? document.body.innerText : ''") or ""
                    except Exception:  # noqa: BLE001
                        text = ""
                    if "CERCA PROSPECT" in text:
                        ok = True
                        break
                print("SELFTEST", "OK" if ok else "FALLITO", flush=True)
                result["code"] = 0 if ok else 1
                window.destroy()

        webview.start(on_start, private_mode=False, storage_path=str(home / "webview"))
        return result["code"]
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
