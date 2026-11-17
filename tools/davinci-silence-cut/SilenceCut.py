#!/usr/bin/env python3
"""
SilenceCut — taglio automatico dei silenzi per DaVinci Resolve.

Due modi d'uso:

1) DENTRO RESOLVE (consigliato)
   Copia questo file in:
     ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit/
   Poi in Resolve: seleziona le clip nel Media Pool -> Workspace > Scripts > SilenceCut.
   Viene creata una NUOVA timeline con solo le parti parlate (le clip originali
   non vengono toccate).

2) DA TERMINALE (alternativa, genera un file FCPXML da importare)
     python3 SilenceCut.py clip1.mov clip2.mov -o tagliato.fcpxml
   Poi in Resolve: File > Import > Timeline... e scegli il file .fcpxml.

Requisiti: ffmpeg (brew install ffmpeg) e Python 3.
"""

import os
import re
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from xml.sax.saxutils import quoteattr
from urllib.parse import quote

# ---------------------------------------------------------------------------
# IMPOSTAZIONI — modifica qui se vuoi cambiare i valori predefiniti
# ---------------------------------------------------------------------------

PRESETS = {
    # noise_db: sotto questo volume è "silenzio" (più vicino a 0 = taglia di più)
    # min_silence: durata minima (s) di una pausa per essere tagliata
    # pad_before / pad_after: margine (s) lasciato prima/dopo ogni frase
    # merge_gap: se due frasi restano separate da meno di così (s), le unisce
    # min_keep: scarta pezzi parlati più corti di così (s) (colpi, click)
    "Normale": dict(noise_db=-35, min_silence=0.5, pad_before=0.12, pad_after=0.20, merge_gap=0.30, min_keep=0.25),
    "Delicato": dict(noise_db=-40, min_silence=0.8, pad_before=0.20, pad_after=0.30, merge_gap=0.45, min_keep=0.25),
    "Aggressivo": dict(noise_db=-30, min_silence=0.3, pad_before=0.06, pad_after=0.10, merge_gap=0.15, min_keep=0.20),
}
DEFAULT_PRESET = "Normale"

AUDIO_STREAM = 0          # quale traccia audio analizzare (0 = la prima)
ASK_PRESET = True         # su Mac mostra una finestrina per scegliere il preset
COLOR_BY_SOURCE = True    # colora le clip in timeline in base al file d'origine
CLIP_COLORS = ["Orange", "Teal", "Yellow", "Violet", "Green", "Pink", "Blue", "Apricot"]

# Percorsi dove cercare ffmpeg (Resolve non vede il PATH del Terminale)
FFMPEG_CANDIDATES = ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]

# ---------------------------------------------------------------------------
# Analisi audio (comune ai due modi)
# ---------------------------------------------------------------------------


def find_tool(name):
    found = shutil.which(name)
    if found:
        return found
    for cand in FFMPEG_CANDIDATES:
        cand = os.path.join(os.path.dirname(cand), name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True, errors="replace")


def detect_silences(ffmpeg, path, noise_db, min_silence, stream=AUDIO_STREAM):
    """Restituisce (lista di silenzi [(inizio, fine)], durata audio) in secondi."""
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-i", path,
           "-map", "0:a:%d" % stream,
           "-af", "silencedetect=noise=%sdB:d=%s" % (noise_db, min_silence),
           "-f", "null", "-"]
    res = run(cmd)
    if res.returncode != 0:
        tail = "\n".join(res.stderr.strip().splitlines()[-3:])
        raise RuntimeError("ffmpeg non riesce a leggere l'audio di %s:\n%s" % (os.path.basename(path), tail))

    duration = None
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    # durata reale elaborata (più precisa di quella del container)
    times = re.findall(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", res.stderr)
    if times:
        h, mi, s = times[-1]
        duration = max(duration or 0, int(h) * 3600 + int(mi) * 60 + float(s))

    silences, start = [], None
    for line in res.stderr.splitlines():
        ms = re.search(r"silence_start:\s*(-?[\d.]+)", line)
        if ms:
            start = max(0.0, float(ms.group(1)))
            continue
        me = re.search(r"silence_end:\s*([\d.]+)", line)
        if me and start is not None:
            silences.append((start, float(me.group(1))))
            start = None
    if start is not None and duration:
        silences.append((start, duration))
    return silences, duration


def speech_segments(silences, duration, p):
    """Trasforma i silenzi nei pezzi parlati da tenere, con margini e unioni."""
    segs, cursor = [], 0.0
    for s, e in silences:
        if s > cursor:
            segs.append([cursor, s])
        cursor = max(cursor, e)
    if duration and cursor < duration:
        segs.append([cursor, duration])

    padded = []
    for s, e in segs:
        s = max(0.0, s - p["pad_before"])
        e = min(duration, e + p["pad_after"]) if duration else e + p["pad_after"]
        if padded and s - padded[-1][1] <= p["merge_gap"]:
            padded[-1][1] = max(padded[-1][1], e)
        else:
            padded.append([s, e])
    return [(s, e) for s, e in padded if e - s >= p["min_keep"]]


def analyze(ffmpeg, path, p, log=print):
    silences, duration = detect_silences(ffmpeg, path, p["noise_db"], p["min_silence"])
    segs = speech_segments(silences, duration, p)
    kept = sum(e - s for s, e in segs)
    if duration:
        log("  %s: %d pezzi, %s -> %s (-%d%%)" % (
            os.path.basename(path), len(segs), fmt_time(duration), fmt_time(kept),
            round(100 * (1 - kept / duration)) if duration else 0))
    return segs, duration


def fmt_time(sec):
    sec = int(round(sec))
    return "%d:%02d" % (sec // 60, sec % 60) if sec < 3600 else "%d:%02d:%02d" % (sec // 3600, sec // 60 % 60, sec % 60)


# ---------------------------------------------------------------------------
# Modo 1: dentro DaVinci Resolve (Workspace > Scripts)
# ---------------------------------------------------------------------------


def mac_dialog_choose(options, default):
    if sys.platform != "darwin" or not ASK_PRESET:
        return default
    items = ", ".join('"%s"' % o for o in options)
    script = ('choose from list {%s} with title "SilenceCut" with prompt '
              '"Quanto tagliare i silenzi?" default items {"%s"}' % (items, default))
    try:
        out = run(["osascript", "-e", script]).stdout.strip()
    except Exception:
        return default
    if out == "false":
        return None  # annullato
    return out if out in options else default


def mac_alert(message):
    print(message)
    if sys.platform == "darwin":
        safe = message.replace("\\", "\\\\").replace('"', '\\"')
        try:
            run(["osascript", "-e", 'display dialog "%s" with title "SilenceCut" buttons {"OK"} default button "OK"' % safe])
        except Exception:
            pass


def get_resolve():
    g = globals()
    if g.get("resolve"):
        return g["resolve"]
    for name in ("app", "bmd"):
        obj = g.get(name)
        if obj is not None:
            try:
                r = obj.GetResolve() if name == "app" else obj.scriptapp("Resolve")
                if r:
                    return r
            except Exception:
                pass
    try:
        import DaVinciResolveScript as dvr  # noqa
        return dvr.scriptapp("Resolve")
    except Exception:
        return None


def clip_fps(clip, project):
    for val in (clip.GetClipProperty("FPS"), project.GetSetting("timelineFrameRate")):
        try:
            f = float(str(val).split()[0])
            if f > 0:
                return f
        except Exception:
            continue
    return 25.0


def run_in_resolve(resolve):
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        return mac_alert("Apri prima un progetto in DaVinci Resolve.")
    mp = project.GetMediaPool()

    def as_list(x):
        return list(x.values()) if isinstance(x, dict) else list(x or [])

    clips = []
    try:
        clips = as_list(mp.GetSelectedClips())
    except Exception:
        pass
    if not clips:
        clips = as_list(mp.GetCurrentFolder().GetClipList())
    clips = [c for c in clips if (c.GetClipProperty("File Path") or "").strip()]
    if not clips:
        return mac_alert("Seleziona una o più clip nel Media Pool e rilancia lo script.")

    ffmpeg = find_tool("ffmpeg")
    if not ffmpeg:
        return mac_alert("ffmpeg non trovato. Installalo dal Terminale con:  brew install ffmpeg")

    preset_name = mac_dialog_choose(list(PRESETS), DEFAULT_PRESET)
    if preset_name is None:
        return
    p = PRESETS[preset_name]
    print("SilenceCut — preset %s %s" % (preset_name, p))

    infos, sources, errors, total_before, total_after = [], [], [], 0.0, 0.0
    for idx, clip in enumerate(clips):
        path = clip.GetClipProperty("File Path")
        try:
            segs, duration = analyze(ffmpeg, path, p)
        except Exception as exc:
            errors.append(str(exc))
            continue
        fps = clip_fps(clip, project)
        total_before += duration or 0
        for s, e in segs:
            start_f = int(round(s * fps))
            end_f = int(round(e * fps)) - 1  # endFrame è incluso
            if end_f > start_f:
                infos.append({"mediaPoolItem": clip, "startFrame": start_f, "endFrame": end_f})
                sources.append(idx)
                total_after += e - s

    if not infos:
        return mac_alert("Nessun parlato trovato.\n" + "\n".join(errors))

    base = clips[0].GetName() if len(clips) == 1 else "%d clip" % len(clips)
    tl_name = "SilenceCut - %s - %s" % (base, time.strftime("%H.%M.%S"))
    timeline = mp.CreateEmptyTimeline(tl_name)
    if not timeline:
        return mac_alert("Impossibile creare la timeline.")
    project.SetCurrentTimeline(timeline)
    items = mp.AppendToTimeline(infos) or []

    if COLOR_BY_SOURCE and len(clips) > 1:
        for item, src in zip(items, sources):
            try:
                item.SetClipColor(CLIP_COLORS[src % len(CLIP_COLORS)])
            except Exception:
                pass

    try:
        resolve.OpenPage("edit")
    except Exception:
        pass

    msg = "Timeline creata: %s\n%d pezzi — da %s a %s (preset %s)." % (
        tl_name, len(infos), fmt_time(total_before), fmt_time(total_after), preset_name)
    if errors:
        msg += "\n\nAttenzione:\n" + "\n".join(errors)
    mac_alert(msg)


# ---------------------------------------------------------------------------
# Modo 2: da terminale -> FCPXML (File > Import > Timeline in Resolve)
# ---------------------------------------------------------------------------


def ffprobe_info(ffprobe, path):
    import json
    res = run([ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path])
    if res.returncode != 0:
        raise RuntimeError("ffprobe non riesce a leggere %s" % path)
    data = json.loads(res.stdout)
    v = next((s for s in data["streams"] if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")), None)
    a = [s for s in data["streams"] if s.get("codec_type") == "audio"]
    fps = Fraction(v["r_frame_rate"]) if v and v.get("r_frame_rate", "0/0") != "0/0" else Fraction(25)
    tc = (data.get("format", {}).get("tags", {}).get("timecode")
          or (v or {}).get("tags", {}).get("timecode")
          or next((s.get("tags", {}).get("timecode") for s in data["streams"] if s.get("tags", {}).get("timecode")), None))
    return {
        "fps": fps.limit_denominator(1001),
        "has_video": v is not None,
        "width": int(v["width"]) if v else 1920,
        "height": int(v["height"]) if v else 1080,
        "duration": float(data.get("format", {}).get("duration", 0) or 0),
        "timecode": tc,
        "audio_channels": int(a[0].get("channels", 2)) if a else 0,
        "audio_rate": int(a[0].get("sample_rate", 48000)) if a else 48000,
    }


def timecode_to_frames(tc, fps):
    """Converte "HH:MM:SS:FF" (o drop-frame "HH:MM:SS;FF") in numero di fotogrammi."""
    m = re.match(r"(\d+):(\d+):(\d+)([:;.,])(\d+)", tc or "")
    if not m:
        return 0
    h, mi, s, sep, f = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4), int(m.group(5))
    nominal = int(round(float(fps)))
    frames = ((h * 60 + mi) * 60 + s) * nominal + f
    if sep in ";," and nominal in (30, 60):
        drop = 2 if nominal == 30 else 4
        total_min = h * 60 + mi
        frames -= drop * (total_min - total_min // 10)
    return frames


def rt(frac):
    """Fraction di secondi -> stringa tempo FCPXML (es. '1001/30000s')."""
    frac = Fraction(frac)
    if frac.denominator == 1:
        return "%ds" % frac.numerator
    return "%d/%ds" % (frac.numerator, frac.denominator)


def build_fcpxml(entries, name):
    """entries: lista di (path, info, segs)."""
    seq_fps = entries[0][1]["fps"]
    seq_fd = 1 / seq_fps
    formats, assets, clips_xml = {}, [], []
    offset_frames = 0

    def fmt_id(info):
        key = (info["fps"], info["width"], info["height"])
        if key not in formats:
            formats[key] = "r%d" % (len(formats) + 1)
        return formats[key]

    seq_fmt = fmt_id(entries[0][1])
    asset_ids = []
    for i, (path, info, segs) in enumerate(entries):
        fd = 1 / info["fps"]
        fid = fmt_id(info)
        aid = "a%d" % (i + 1)
        asset_ids.append(aid)
        tc_start = timecode_to_frames(info["timecode"], info["fps"]) * fd
        dur_frames = int(info["duration"] * info["fps"])
        info["_start"] = tc_start
        src = "file://" + quote(os.path.abspath(path))
        assets.append(
            '    <asset id="%s" name=%s start="%s" duration="%s" hasVideo="%d" hasAudio="%d" format="%s"'
            ' audioSources="1" audioChannels="%d" audioRate="%d">\n'
            '      <media-rep kind="original-media" src=%s/>\n'
            '    </asset>' % (aid, quoteattr(os.path.splitext(os.path.basename(path))[0]), rt(tc_start),
                             rt(dur_frames * fd), info["has_video"], info["audio_channels"] > 0, fid,
                             max(info["audio_channels"], 1), info["audio_rate"], quoteattr(src)))

        for s, e in segs:
            s_f = int(round(s * info["fps"]))
            e_f = int(round(e * info["fps"]))
            # durata quantizzata ai fotogrammi della sequenza
            dur_seq = int(round((e_f - s_f) * fd * seq_fps))
            if dur_seq <= 0:
                continue
            clips_xml.append(
                '          <asset-clip ref="%s" name=%s offset="%s" start="%s" duration="%s" format="%s" tcFormat="NDF"/>'
                % (aid, quoteattr(os.path.basename(path)), rt(offset_frames * seq_fd),
                   rt(tc_start + s_f * fd), rt(dur_seq * seq_fd), fid))
            offset_frames += dur_seq

    fmt_xml = []
    for (fps, w, h), fid in formats.items():
        fmt_xml.append('    <format id="%s" frameDuration="%s" width="%d" height="%d"/>' % (fid, rt(1 / fps), w, h))

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.9">\n'
        '  <resources>\n%s\n%s\n  </resources>\n'
        '  <library>\n    <event name="SilenceCut">\n      <project name=%s>\n'
        '        <sequence format="%s" duration="%s" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">\n'
        '          <spine>\n%s\n          </spine>\n        </sequence>\n      </project>\n    </event>\n  </library>\n'
        '</fcpxml>\n' % ("\n".join(fmt_xml), "\n".join(assets), quoteattr(name), seq_fmt,
                         rt(offset_frames * seq_fd), "\n".join(clips_xml)))


def run_cli(argv):
    import argparse
    ap = argparse.ArgumentParser(description="Taglia i silenzi e crea una timeline FCPXML per DaVinci Resolve.")
    ap.add_argument("files", nargs="+", help="file video/audio, in ordine")
    ap.add_argument("-o", "--output", help="file .fcpxml di uscita (default: accanto al primo file)")
    ap.add_argument("-p", "--preset", choices=list(PRESETS), default=DEFAULT_PRESET)
    ap.add_argument("--noise", type=float, help="soglia silenzio in dB (es. -35)")
    ap.add_argument("--min-silence", type=float, help="pausa minima da tagliare, in secondi")
    ap.add_argument("--pad", type=float, help="margine prima e dopo ogni frase, in secondi")
    args = ap.parse_args(argv)

    p = dict(PRESETS[args.preset])
    if args.noise is not None:
        p["noise_db"] = args.noise
    if args.min_silence is not None:
        p["min_silence"] = args.min_silence
    if args.pad is not None:
        p["pad_before"] = p["pad_after"] = args.pad

    ffmpeg, ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
    if not ffmpeg or not ffprobe:
        sys.exit("ffmpeg/ffprobe non trovati. Installa con:  brew install ffmpeg")

    print("Preset %s: %s" % (args.preset, p))
    entries = []
    for f in args.files:
        info = ffprobe_info(ffprobe, f)
        segs, duration = analyze(ffmpeg, f, p)
        if duration:
            info["duration"] = max(info["duration"], duration)
        entries.append((f, info, segs))

    out = args.output or os.path.splitext(args.files[0])[0] + "_silencecut.fcpxml"
    name = "SilenceCut - " + os.path.splitext(os.path.basename(args.files[0]))[0]
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(build_fcpxml(entries, name))
    print("\nCreato: %s\nIn Resolve: File > Import > Timeline... e seleziona questo file." % out)


# ---------------------------------------------------------------------------

def main():
    injected = any(globals().get(n) is not None for n in ("resolve", "app", "bmd", "fusion"))
    if injected or len(sys.argv) <= 1:
        r = get_resolve()
        if r:
            return run_in_resolve(r)
        if len(sys.argv) <= 1:
            print(__doc__)
            return
    run_cli(sys.argv[1:])


if __name__ == "__main__" or globals().get("resolve") is not None:
    main()
