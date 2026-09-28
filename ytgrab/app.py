#!/usr/bin/env python3
"""YTGrab — downloader YouTube leggero per macOS, basato su yt-dlp.

Un piccolo server HTTP locale (solo stdlib) serve l'interfaccia in web/ e
un'API JSON; la finestra è una WKWebView nativa tramite pywebview (se non è
installato, l'interfaccia si apre nel browser predefinito).
"""

import json
import os
import re
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

APP_NAME = "YTGrab"
FROZEN = getattr(sys, "frozen", False)
# Nell'app impacchettata (PyInstaller) i file stanno in sys._MEIPASS.
HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
WEB_DIR = HERE / "web"
if sys.platform == "darwin":
    CONFIG_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
else:
    CONFIG_DIR = Path.home() / ".config" / APP_NAME.lower()
SETTINGS_FILE = CONFIG_DIR / "settings.json"
# Copia aggiornata di yt-dlp scaricata da "Aggiorna yt-dlp" (solo app impacchettata).
USER_LIB = CONFIG_DIR / "pylib"


def _bundled_bin_dirs():
    # ffmpeg, ffprobe e deno inclusi nell'app: YTGrab.app/Contents/MacOS/bin
    exe = Path(sys.executable).resolve()
    return [exe.parent / "bin", HERE / "bin"] if FROZEN else [HERE / "bin"]


# Le app lanciate dal Finder hanno un PATH minimale: aggiungi i binari inclusi e Homebrew.
for _p in [*map(str, _bundled_bin_dirs()), "/opt/homebrew/bin", "/usr/local/bin"][::-1]:
    if os.path.isdir(_p) and _p not in os.environ.get("PATH", "").split(":"):
        os.environ["PATH"] = _p + ":" + os.environ.get("PATH", "")


def _version_tuple(v):
    try:
        return tuple(int(x) for x in str(v).strip().split("."))
    except ValueError:
        return ()


def _user_lib_version():
    try:
        text = (USER_LIB / "yt_dlp" / "version.py").read_text()
        return text.split("__version__ = ")[1].split("\n")[0].strip("'\" ")
    except (OSError, IndexError):
        return ""


def _bundled_version():
    try:
        return (HERE / "ytdlp_version.txt").read_text().strip()
    except OSError:
        return ""


def _import_ytdlp():
    # Usa la copia aggiornata solo se più recente di quella inclusa nell'app;
    # se è rotta, torna a quella inclusa.
    use_user = FROZEN and _version_tuple(_user_lib_version()) > _version_tuple(_bundled_version())
    if use_user:
        sys.path.insert(0, str(USER_LIB))
    try:
        import yt_dlp as mod
        import yt_dlp.utils  # noqa: F401
        return mod
    except Exception:  # noqa: BLE001
        if not use_user:
            raise
        sys.path.remove(str(USER_LIB))
        for name in [m for m in sys.modules if m.split(".")[0] in ("yt_dlp", "yt_dlp_ejs")]:
            del sys.modules[name]
        import yt_dlp as mod
        return mod


yt_dlp = _import_ytdlp()
from yt_dlp.utils import download_range_func  # noqa: E402

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
    if req.get("sections") and not req.get("_ytdlp_ranges"):
        return run_sections_job(job, s)
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


# ---------------------------------------------------------------- spezzoni

# YouTube interrompe le richieste HTTP troppo lunghe dei client non-browser: se
# ffmpeg legge direttamente da googlevideo, dopo qualche MB la connessione cade
# ("ffmpeg exited with code 251"). ffmpeg legge quindi da questo proxy locale,
# che scarica da YouTube solo i byte richiesti, a blocchi da 10 MB, come fa yt-dlp.
PROXY = {}
PROXY_LOCK = threading.Lock()
CHUNK = 10 * 1024 * 1024
SERVER_PORT = [None]


def proxy_register(ydl, fmt):
    token = uuid.uuid4().hex
    with PROXY_LOCK:
        PROXY[token] = {"ydl": ydl, "url": fmt["url"],
                        "headers": dict(fmt.get("http_headers") or {}),
                        "total": fmt.get("filesize")}
    return f"http://127.0.0.1:{SERVER_PORT[0]}/proxy/{token}", token


def proxy_unregister(token):
    with PROXY_LOCK:
        PROXY.pop(token, None)


def _open(entry, start, end):
    """Apre una richiesta per i byte [start, end] al server originale (con retry)."""
    from yt_dlp.networking import Request
    headers = {**entry["headers"], "Range": f"bytes={start}-{end}"}
    for attempt in range(3):
        try:
            return entry["ydl"].urlopen(Request(entry["url"], headers=headers))
        except Exception:  # noqa: BLE001
            if attempt == 2:
                raise
            time.sleep(0.5 * (attempt + 1))


def _copy(resp, wfile, skip=0):
    """Copia la risposta verso ffmpeg a piccoli pezzi: se ffmpeg chiude, ci fermiamo subito."""
    sent = 0
    while True:
        buf = resp.read(64 * 1024)
        if not buf:
            return sent
        if skip:
            cut = min(skip, len(buf))
            buf, skip = buf[cut:], skip - cut
            if not buf:
                continue
        wfile.write(buf)
        sent += len(buf)


def proxy_serve(handler, token):
    entry = PROXY.get(token)
    if not entry:
        return handler._send(404, {"error": "not found"})
    m = re.match(r"bytes=(\d+)-(\d*)", handler.headers.get("Range") or "")
    start = int(m.group(1)) if m else 0
    req_end = int(m.group(2)) if m and m.group(2) else None
    total = entry["total"]
    if total is not None and start >= total:
        handler.send_response(416)
        handler.send_header("Content-Range", f"bytes */{total}")
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return
    chunk_end = start + CHUNK - 1 if req_end is None else min(start + CHUNK - 1, req_end)
    try:
        resp = _open(entry, start, chunk_end)
    except Exception as exc:  # noqa: BLE001
        return handler._send(502, {"error": str(exc)[:300]})
    try:
        cr = re.search(r"/(\d+)", resp.headers.get("Content-Range") or "")
        if cr:
            total = int(cr.group(1))
        elif total is None:
            total = start + int(resp.headers.get("Content-Length") or 0)
        entry["total"] = total
        last = total - 1 if req_end is None else min(req_end, total - 1)

        handler.send_response(206 if m else 200)
        handler.send_header("Content-Type", "application/octet-stream")
        handler.send_header("Accept-Ranges", "bytes")
        if m:
            handler.send_header("Content-Range", f"bytes {start}-{last}/{total}")
        handler.send_header("Content-Length", str(last - start + 1))
        handler.end_headers()
        # Buffer piccolo: quando ffmpeg salta altrove non restano MB già scaricati e inutili.
        handler.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 128 * 1024)

        # Se il server ignora il Range (200) scartiamo i byte iniziali.
        pos = start + _copy(resp, handler.wfile, skip=start if resp.status == 200 else 0)
        resp.close()
        while pos <= last and PROXY.get(token) is entry:
            resp = _open(entry, pos, min(pos + CHUNK - 1, last))
            got = _copy(resp, handler.wfile)
            resp.close()
            if not got:
                break
            pos += got
    except (BrokenPipeError, ConnectionResetError):
        pass  # ffmpeg ha letto quello che gli serviva e ha chiuso
    except Exception:  # noqa: BLE001
        pass  # errore a monte: ffmpeg vedrà la connessione chiusa e lo riporterà
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass


def _hms(t):
    t = int(t)
    return f"{t // 3600:02d}h{t % 3600 // 60:02d}m{t % 60:02d}s"


def _encoder_args(mode, quality, precise, audio_fmt):
    """Codec e contenitore per ffmpeg: (argomenti, estensione)."""
    mac = sys.platform == "darwin"
    if mode == "a":
        return {
            "wav": (["-c:a", "pcm_s16le"], "wav"),
            "mp3": (["-c:a", "libmp3lame", "-q:a", "0"], "mp3"),
        }.get(audio_fmt, (["-c:a", "copy"], "m4a"))
    if quality == "hevc":
        v = (["-c:v", "hevc_videotoolbox", "-q:v", "65"] if mac
             else ["-c:v", "libx265", "-crf", "20", "-preset", "fast"])
        return v + ["-tag:v", "hvc1", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k"], "mov"
    if precise:
        v = (["-c:v", "h264_videotoolbox", "-q:v", "70"] if mac
             else ["-c:v", "libx264", "-crf", "17", "-preset", "veryfast"])
        return v + ["-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k"], "mp4"
    return ["-c", "copy"], "mp4"


def run_sections_job(job, s):
    req = job.req
    mode = req.get("mode", s["mode"])
    quality = req.get("quality", s["quality"])
    precise = bool(req.get("precise_cuts", s["precise_cuts"]))
    audio_fmt = req.get("audio_format") or s.get("audio_format") or "m4a"
    sections = [(float(a), float(b)) for a, b in req["sections"] if float(b) > float(a)]
    job.section_total = len(sections)
    out_dir = Path(os.path.expanduser(s["download_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    url = req.get("url") or f"https://www.youtube.com/watch?v={req['id']}"

    opts = base_opts(s)
    opts.update({"format": build_format(mode, quality, req.get("max_height", s["max_height"])),
                 "noplaylist": True})
    tokens = []
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            job.status = "analisi…"
            info = ydl.extract_info(url, download=False)
            fmts = info.get("requested_formats") or [info]
            if any(not re.match(r"https?://", f.get("url") or "") for f in fmts):
                # Formato non HTTP (es. HLS): lascia fare a yt-dlp.
                req = {**req}
                job.req = req
                return _run_ranges_with_ytdlp(job, s, sections)
            job.title = info.get("title") or job.title
            inputs = []
            for f in fmts:
                purl, tok = proxy_register(ydl, f)
                tokens.append(tok)
                inputs.append((purl, f))

            args_codec, ext = _encoder_args(mode, quality, precise, audio_fmt)
            ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
            base = yt_dlp.utils.sanitize_filename(info.get("title") or info["id"])[:90].strip()
            suffix = {"a": " (audio)", "v": " (video)"}.get(mode, "")

            for i, (a, b) in enumerate(sections):
                job.section_idx = i
                job.status = f"spezzone {i + 1}/{len(sections)}"
                dur = b - a
                out = out_dir / f"{base} [{info['id']}]_{_hms(a)}-{_hms(b)}{suffix}.{ext}"
                n = 2
                while out.exists():
                    out = out.with_name(f"{out.stem} ({n}){out.suffix}")
                    n += 1
                tmp = out.with_name(f".{out.stem}.part.{ext}")

                cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error",
                       "-progress", "pipe:1", "-nostats"]
                for purl, _ in inputs:
                    cmd += ["-recv_buffer_size", "131072",
                            "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", purl]
                if len(inputs) == 2:
                    maps = {"av": ["-map", "0:v:0", "-map", "1:a:0"],
                            "v": ["-map", "0:v:0"], "a": ["-map", "1:a:0"]}[mode]
                else:
                    maps = {"av": ["-map", "0:v:0?", "-map", "0:a:0?"],
                            "v": ["-map", "0:v:0"], "a": ["-map", "0:a:0"]}[mode]
                cmd += maps + args_codec
                if ext in ("mp4", "mov", "m4a"):
                    cmd += ["-movflags", "+faststart"]
                cmd += [str(tmp)]

                err = _run_ffmpeg(cmd, job, i, len(sections), dur)
                if err:
                    tmp.unlink(missing_ok=True)
                    raise RuntimeError(f"spezzone {i + 1}: {err}")
                tmp.rename(out)
                job.files.append(str(out))
        job.state, job.status, job.progress = "done", "completato", 100.0
        job.speed = job.eta = ""
    except Exception as exc:  # noqa: BLE001
        job.state, job.status = "error", "errore"
        job.error = str(exc).replace("ERROR: ", "")[:600]
    finally:
        for tok in tokens:
            proxy_unregister(tok)


def _run_ffmpeg(cmd, job, idx, count, dur):
    """Esegue ffmpeg aggiornando l'avanzamento. Ritorna il messaggio d'errore o None."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    err_lines = []

    def read_err():
        for line in proc.stderr:
            err_lines.append(line.rstrip())
            del err_lines[:-15]

    t = threading.Thread(target=read_err, daemon=True)
    t.start()
    started = time.time()
    for line in proc.stdout:
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            try:
                done = max(0, int(line.split("=")[1])) / 1e6
            except ValueError:
                continue
            frac = min(1.0, done / dur) if dur else 0
            job.progress = max(job.progress, min(99.0, (idx + frac) / count * 100))
            el = time.time() - started
            if frac > 0.02 and el > 1:
                rem = el / frac * (1 - frac)
                job.eta = f"{int(rem) // 60}:{int(rem) % 60:02d}"
            job.speed = f"{done / el:.1f}×" if el > 0.5 else ""
    proc.wait()
    t.join(timeout=2)
    if proc.returncode != 0:
        detail = " | ".join(line for line in err_lines if line.strip())[-500:]
        return f"ffmpeg exited with code {proc.returncode}" + (f": {detail}" if detail else "")
    return None


def _run_ranges_with_ytdlp(job, s, sections):
    job.req = {**job.req, "_ytdlp_ranges": True}
    return run_job(job)


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
    if not FROZEN:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "-U", "--quiet",
                            "yt-dlp[default]"], capture_output=True, text=True)
        return (r.stdout + r.stderr).strip()[-600:] or "ok"
    # App impacchettata: niente pip. Scarica le wheel da PyPI e le estrae in USER_LIB.
    import ssl
    import tempfile
    import urllib.request
    import zipfile
    import certifi

    ctx = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or certifi.where())

    def fetch(url):
        with urllib.request.urlopen(url, context=ctx, timeout=60) as r:
            return r.read()

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="ytgrab-upd-", dir=CONFIG_DIR))
    try:
        version = ""
        for pkg in ("yt-dlp", "yt-dlp-ejs"):
            meta = json.loads(fetch(f"https://pypi.org/pypi/{pkg}/json"))
            wheel = next(u for u in meta["urls"]
                         if u["packagetype"] == "bdist_wheel" and u["filename"].endswith("-none-any.whl"))
            whl = tmp / wheel["filename"]
            whl.write_bytes(fetch(wheel["url"]))
            with zipfile.ZipFile(whl) as z:
                z.extractall(tmp / "lib")
            whl.unlink()
            if pkg == "yt-dlp":
                version = meta["info"]["version"]
        if USER_LIB.exists():
            shutil.rmtree(USER_LIB)
        (tmp / "lib").rename(USER_LIB)
        return f"yt-dlp {version}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def doctor():
    return {
        "yt_dlp": yt_dlp.version.__version__,
        "frozen": bool(FROZEN),
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
            if u.path.startswith("/proxy/"):
                return proxy_serve(self, u.path.rsplit("/", 1)[-1])
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
    SERVER_PORT[0] = srv.server_address[1]
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
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    webview.start(private_mode=False, storage_path=str(CONFIG_DIR / "webview"))


if __name__ == "__main__":
    main()
