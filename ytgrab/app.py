#!/usr/bin/env python3
"""YTGrab — downloader YouTube leggero per macOS, basato su yt-dlp.

Un piccolo server HTTP locale (solo stdlib) serve l'interfaccia in web/ e
un'API JSON; la finestra è una WKWebView nativa tramite pywebview (se non è
installato, l'interfaccia si apre nel browser predefinito).
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Le app lanciate dal Finder hanno un PATH minimale: aggiungi Homebrew.
for _p in ("/opt/homebrew/bin", "/usr/local/bin"):
    if os.path.isdir(_p) and _p not in os.environ.get("PATH", "").split(":"):
        os.environ["PATH"] = _p + ":" + os.environ.get("PATH", "")

import yt_dlp  # noqa: E402
from yt_dlp.utils import download_range_func  # noqa: E402

APP_NAME = "YTGrab"
HERE = Path(__file__).resolve().parent
WEB_DIR = HERE / "web"
if sys.platform == "darwin":
    CONFIG_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
else:
    CONFIG_DIR = Path.home() / ".config" / APP_NAME.lower()
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULT_PORT = 47811

DEFAULT_SETTINGS = {
    "download_dir": str(Path.home() / "Movies" / "YTGrab"),
    "mode": "av",            # av | v | a
    "quality": "davinci",    # davinci | hevc | original
    "max_height": 1080,
    "audio_format": "m4a",   # m4a | wav | mp3
    "precise_cuts": False,
    "cookies_browser": "",   # "" | safari | chrome | firefox | brave | edge
}


# ---------------------------------------------------------------- settings

_settings_lock = threading.Lock()


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        s.update(json.loads(SETTINGS_FILE.read_text()))
    except (OSError, ValueError):
        pass
    return s


def save_settings(patch):
    with _settings_lock:
        s = load_settings()
        s.update({k: v for k, v in patch.items() if k in DEFAULT_SETTINGS})
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(s, indent=2))
        return s


# ---------------------------------------------------------------- yt-dlp

def js_runtimes():
    """YouTube richiede un runtime JS: usa quelli presenti nel PATH."""
    found = {}
    for name in ("deno", "node", "bun"):
        path = shutil.which(name)
        if path:
            found[name] = {"path": path}
    return found or None


def base_opts(settings):
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "socket_timeout": 20,
    }
    runtimes = js_runtimes()
    if runtimes:
        opts["js_runtimes"] = runtimes
    if settings.get("cookies_browser"):
        opts["cookiesfrombrowser"] = (settings["cookies_browser"],)
    return opts


def _thumb(entry):
    thumbs = entry.get("thumbnails") or []
    for t in reversed(thumbs):
        if t.get("url") and (t.get("width") or 0) <= 480:
            return t["url"]
    vid = entry.get("id")
    return f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else None


def _entry(e):
    return {
        "id": e.get("id"),
        "title": e.get("title") or "",
        "channel": e.get("channel") or e.get("uploader") or "",
        "duration": e.get("duration"),
        "views": e.get("view_count"),
        "thumb": _thumb(e),
        "url": e.get("webpage_url") or e.get("url")
               or f"https://www.youtube.com/watch?v={e.get('id')}",
    }


def search(query, limit=24):
    query = query.strip()
    if query.startswith(("http://", "https://", "www.", "youtu")):
        target = query if "://" in query else "https://" + query
    else:
        target = f"ytsearch{limit}:{query}"
    opts = base_opts(load_settings())
    opts["extract_flat"] = "in_playlist"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(target, download=False)
    if info.get("_type") in ("playlist", "multi_video"):
        entries = [e for e in (info.get("entries") or []) if e and e.get("id")]
    else:
        entries = [info]
    return [_entry(e) for e in entries]


def build_format(mode, quality, max_height):
    h = int(max_height or 1080)
    if mode == "a":
        return "ba[ext=m4a]/ba/b"
    # "davinci": H.264 + AAC, si importa in DaVinci senza conversioni (YouTube
    # offre H.264 fino a 1080p). Altrimenti il miglior codec disponibile (VP9/AV1).
    pref = "[vcodec^=avc1]" if quality == "davinci" else ""
    if mode == "v":
        return f"bv{pref}[height<={h}]/bv[height<={h}]/bv"
    return (f"bv*{pref}[height<={h}]+ba[ext=m4a]/bv*[height<={h}]+ba[ext=m4a]"
            f"/bv*[height<={h}]+ba/b[height<={h}]/b")


class Job:
    def __init__(self, req):
        self.id = uuid.uuid4().hex[:10]
        self.req = req
        self.title = req.get("title") or req.get("id")
        self.status = "in coda"
        self.state = "queued"      # queued | running | done | error
        self.progress = 0.0
        self.speed = ""
        self.eta = ""
        self.files = []
        self.error = ""
        self.created = time.time()
        self.section_idx = 0
        self.section_total = max(1, len(req.get("sections") or []))

    def public(self):
        return {
            "id": self.id, "title": self.title, "status": self.status,
            "state": self.state, "progress": round(self.progress, 1),
            "speed": self.speed, "eta": self.eta, "files": self.files,
            "error": self.error, "mode": self.req.get("mode"),
            "sections": self.req.get("sections") or [],
            "thumb": self.req.get("thumb"),
        }


JOBS = {}
JOBS_LOCK = threading.Lock()
# Due download in parallelo bastano e non affaticano un M1 da 8 GB.
EXECUTOR = ThreadPoolExecutor(max_workers=2)


def run_job(job):
    job.state, job.status = "running", "avvio…"
    s = load_settings()
    req = job.req
    mode = req.get("mode", s["mode"])
    quality = req.get("quality", s["quality"])
    max_h = req.get("max_height", s["max_height"])
    sections = [(float(a), float(b)) for a, b in (req.get("sections") or []) if float(b) > float(a)]
    out_dir = Path(os.path.expanduser(s["download_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)

    suffix = {"a": " (audio)", "v": " (video)"}.get(mode, "")
    tmpl = ("%(title).90B [%(id)s]"
            "%(section_start>_%Hh%Mm%Ss|)s%(section_end>-%Hh%Mm%Ss|)s"
            f"{suffix}.%(ext)s")

    def hook(d):
        st = d.get("status")
        if st == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            done = d.get("downloaded_bytes") or 0
            frac = (done / total) if total else 0
            if sections:
                frac = (job.section_idx + frac) / job.section_total
            job.progress = max(job.progress, min(99.0, frac * 100))
            sp = d.get("speed")
            job.speed = f"{sp / 1048576:.1f} MB/s" if sp else ""
            eta = d.get("eta")
            job.eta = f"{int(eta) // 60}:{int(eta) % 60:02d}" if eta else ""
            job.status = (f"spezzone {job.section_idx + 1}/{job.section_total}"
                          if sections else "download")
        elif st == "finished":
            job.status = "elaborazione…"

    def pp_hook(d):
        if d.get("status") == "started":
            job.status = {
                "FFmpegMerger": "unione audio+video…",
                "FFmpegExtractAudio": "conversione audio…",
                "FFmpegVideoConvertor": "conversione HEVC…",
            }.get(d.get("postprocessor"), "elaborazione…")
        if d.get("status") == "finished" and d.get("postprocessor") == "MoveFiles":
            path = (d.get("info_dict") or {}).get("filepath")
            if path and path not in job.files:
                job.files.append(path)
                job.section_idx = min(job.section_idx + 1, job.section_total)

    opts = base_opts(s)
    opts.update({
        "format": build_format(mode, quality, max_h),
        "outtmpl": {"default": str(out_dir / tmpl)},
        "paths": {"temp": str(out_dir / ".ytgrab-tmp")},
        "progress_hooks": [hook],
        "postprocessor_hooks": [pp_hook],
        "concurrent_fragment_downloads": 4,
        "overwrites": False,
        "noplaylist": True,
        "windowsfilenames": False,
        "trim_file_name": 180,
    })
    pps = []
    if mode == "a":
        codec = s.get("audio_format") or "m4a"
        if req.get("audio_format"):
            codec = req["audio_format"]
        pps.append({"key": "FFmpegExtractAudio", "preferredcodec": codec,
                    "preferredquality": "0"})
    else:
        opts["merge_output_format"] = "mp4" if quality != "original" else "mp4/mkv"
        if quality == "hevc":
            # Ricodifica hardware (VideoToolbox) in HEVC/.mov: veloce su Apple Silicon
            # e leggibile da DaVinci anche per sorgenti VP9/AV1 fino al 4K.
            pps.append({"key": "FFmpegVideoConvertor", "preferedformat": "mov"})
            enc = (["-c:v", "hevc_videotoolbox", "-q:v", "65", "-tag:v", "hvc1", "-pix_fmt", "yuv420p"]
                   if sys.platform == "darwin" else ["-c:v", "libx265", "-crf", "20", "-tag:v", "hvc1"])
            opts["postprocessor_args"] = {"videoconvertor": enc + ["-c:a", "aac", "-b:a", "256k"]}
    if pps:
        opts["postprocessors"] = pps
    if sections:
        opts["download_ranges"] = download_range_func(None, sections)
        opts["force_keyframes_at_cuts"] = bool(req.get("precise_cuts", s["precise_cuts"]))

    url = req.get("url") or f"https://www.youtube.com/watch?v={req['id']}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not job.files and info:
                for r in info.get("requested_downloads") or [info]:
                    p = r.get("filepath") or r.get("_filename")
                    if p and os.path.exists(p):
                        job.files.append(p)
        job.state, job.status, job.progress = "done", "completato", 100.0
        job.speed = job.eta = ""
    except Exception as exc:  # noqa: BLE001 - mostriamo l'errore nell'interfaccia
        msg = str(exc).replace("ERROR: ", "")
        job.state, job.status, job.error = "error", "errore", msg[:400]
    finally:
        shutil.rmtree(out_dir / ".ytgrab-tmp", ignore_errors=True)


def enqueue(req):
    if not (req.get("id") or req.get("url")):
        raise ValueError("id o url mancante")
    job = Job(req)
    with JOBS_LOCK:
        JOBS[job.id] = job
    EXECUTOR.submit(run_job, job)
    return job.public()


# ---------------------------------------------------------------- mac helpers

def reveal(path):
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path] if os.path.isfile(path) else ["open", path])


def choose_folder(current):
    if sys.platform != "darwin":
        return None
    script = (f'POSIX path of (choose folder with prompt "Cartella download" '
              f'default location (POSIX file "{current}"))')
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    return r.stdout.strip() or None


def update_ytdlp():
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "--quiet",
                        "yt-dlp[default]"], capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()[-600:] or "ok"


def doctor():
    return {
        "yt_dlp": yt_dlp.version.__version__,
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "js_runtime": ", ".join(js_runtimes() or {}) or None,
        "python": sys.version.split()[0],
    }


# ---------------------------------------------------------------- http

class Handler(BaseHTTPRequestHandler):
    server_version = APP_NAME

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _local_only(self):
        # Blocca richieste cross-site da altre pagine aperte nel browser.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if origin and urlparse(origin).netloc != host:
            self._send(403, {"error": "forbidden"})
            return False
        return True

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, (WEB_DIR / "index.html").read_bytes(),
                                  "text/html; charset=utf-8")
            if u.path == "/api/search":
                return self._send(200, {"results": search(q.get("q", ""), int(q.get("n", 24)))})
            if u.path == "/api/jobs":
                with JOBS_LOCK:
                    jobs = sorted(JOBS.values(), key=lambda j: j.created, reverse=True)
                return self._send(200, {"jobs": [j.public() for j in jobs]})
            if u.path == "/api/settings":
                return self._send(200, load_settings())
            if u.path == "/api/doctor":
                return self._send(200, doctor())
            return self._send(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": str(exc).replace("ERROR: ", "")[:400]})

    def do_POST(self):
        if not self._local_only():
            return
        u = urlparse(self.path)
        try:
            body = self._json_body()
            if u.path == "/api/download":
                return self._send(200, enqueue(body))
            if u.path == "/api/settings":
                return self._send(200, save_settings(body))
            if u.path == "/api/reveal":
                reveal(body.get("path") or os.path.expanduser(load_settings()["download_dir"]))
                return self._send(200, {"ok": True})
            if u.path == "/api/choose-folder":
                cur = os.path.expanduser(load_settings()["download_dir"])
                path = choose_folder(cur if os.path.isdir(cur) else str(Path.home()))
                return self._send(200, save_settings({"download_dir": path}) if path else load_settings())
            if u.path == "/api/clear":
                with JOBS_LOCK:
                    for k in [k for k, j in JOBS.items() if j.state in ("done", "error")]:
                        del JOBS[k]
                return self._send(200, {"ok": True})
            if u.path == "/api/update":
                return self._send(200, {"log": update_ytdlp()})
            return self._send(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            return self._send(500, {"error": str(exc).replace("ERROR: ", "")[:400]})


def make_server():
    for port in (DEFAULT_PORT, 0):
        try:
            return ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError:
            continue
    raise RuntimeError("nessuna porta libera")


def already_running():
    try:
        with socket.create_connection(("127.0.0.1", DEFAULT_PORT), timeout=0.3):
            return True
    except OSError:
        return False


def main():
    browser = "--browser" in sys.argv
    if already_running() and "--server" not in sys.argv:
        # Un'istanza è già aperta: non duplicare il server.
        url = f"http://127.0.0.1:{DEFAULT_PORT}/"
        try:
            if browser:
                raise ImportError
            import webview
            webview.create_window(APP_NAME, url, width=1360, height=860, min_size=(980, 640))
            webview.start()
        except ImportError:
            webbrowser.open(url)
        return

    srv = make_server()
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"{APP_NAME} in ascolto su {url}", flush=True)

    if "--server" in sys.argv:
        srv.serve_forever()
        return
    try:
        if browser:
            raise ImportError
        import webview
    except ImportError:
        webbrowser.open(url)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
        return
    webview.create_window(APP_NAME, url, width=1360, height=860,
                          min_size=(980, 640), background_color="#0e0f12")
    webview.start()


if __name__ == "__main__":
    main()
