#!/bin/bash
# SilenceCut — analisi dei silenzi da Terminale.
# Serve quando DaVinci Resolve non permette agli script di avviare ffmpeg.
# Uso: bash analizza.sh file1.wav [file2.mov ...]
# Il risultato viene letto dallo script SilenceCut dentro Resolve.

OUT_DIR="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/SilenceCut"
OUT="$OUT_DIR/analisi.lua"
THRESHOLDS="-30 -35 -40"   # soglie in dB usate dai preset
MIN_SILENCE=0.3            # pausa più corta registrata (s)

FF=""
for p in "$(command -v ffmpeg 2>/dev/null)" /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do
  [ -n "$p" ] && [ -x "$p" ] && FF="$p" && break
done
if [ -z "$FF" ]; then
  echo "ffmpeg non trovato. Installalo con:  brew install ffmpeg"
  exit 1
fi
if [ $# -eq 0 ]; then
  echo "Uso: bash analizza.sh file1 [file2 ...]"
  exit 1
fi

mkdir -p "$OUT_DIR"
TMP="$(mktemp)"
echo "return {" > "$TMP"
ok=0
for f in "$@"; do
  if [ ! -f "$f" ]; then
    echo "!! File non trovato: $f"
    continue
  fi
  echo "Analizzo: $(basename "$f")"
  printf '  [ [==[%s]==] ] = {\n' "$f" >> "$TMP"
  for db in $THRESHOLDS; do
    "$FF" -hide_banner -nostats -i "$f" -map 0:a:0 \
      -af "silencedetect=noise=${db}dB:d=${MIN_SILENCE}" -f null - 2>&1 |
    awk -v db="$db" '
      /Duration:/ && dur == "" {
        split($2, t, ":"); gsub(",", "", t[3]); dur = t[1] * 3600 + t[2] * 60 + t[3]
      }
      /silence_start:/ { s = $NF; if (s < 0) s = 0; open = 1 }
      /silence_end:/ {
        for (i = 1; i <= NF; i++) if ($i == "silence_end:") e = $(i + 1)
        if (open) { list = list sprintf("{%s,%s},", s, e); open = 0 }
      }
      END {
        if (open && dur != "") list = list sprintf("{%s,%s},", s, dur)
        printf "    [%s] = { %s },\n", db, list
        if (db == -35 && dur != "") printf "    duration = %s,\n", dur
      }' >> "$TMP"
  done
  echo "  }," >> "$TMP"
  ok=$((ok + 1))
done
echo "}" >> "$TMP"
mv "$TMP" "$OUT"

echo
if [ $ok -gt 0 ]; then
  echo "Fatto: $ok file analizzati."
  echo "Ora torna in DaVinci Resolve e rilancia SilenceCut."
else
  echo "Nessun file analizzato."
fi
