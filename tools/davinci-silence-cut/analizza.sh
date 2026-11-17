#!/bin/bash
# SilenceCut — analisi dei silenzi da Terminale (o dall'app "SilenceCut Analizza").
# Serve perché DaVinci Resolve non permette agli script di avviare ffmpeg.
#
# Uso: bash analizza.sh [-f] file-o-cartella [altri ...]
#   Le cartelle vengono esplorate (anche le sottocartelle) cercando file audio/video.
#   I file già analizzati vengono saltati; -f li rianalizza.
# Il risultato viene letto dallo script SilenceCut dentro Resolve.

SC_DIR="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/SilenceCut"
CACHE="$SC_DIR/cache"
THRESHOLDS="-30 -35 -40"   # soglie in dB usate dai preset
MIN_SILENCE=0.3            # pausa più corta registrata (s)
EXTENSIONS="mp4 mov m4v mxf mts m2ts avi mkv wav aif aiff mp3 m4a aac flac caf"

FORCE=0
if [ "$1" = "-f" ]; then FORCE=1; shift; fi

FF=""
for p in "$(command -v ffmpeg 2>/dev/null)" /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do
  [ -n "$p" ] && [ -x "$p" ] && FF="$p" && break
done
if [ -z "$FF" ]; then
  echo "ffmpeg non trovato. Installalo con:  brew install ffmpeg"
  exit 1
fi
if [ $# -eq 0 ]; then
  echo "Uso: bash analizza.sh file-o-cartella [...]"
  exit 1
fi
mkdir -p "$CACHE"

# Nome del file di analisi: stessa regola usata dallo script in Resolve
cache_name() {
  local s
  s=$(printf '%s' "$1" | LC_ALL=C sed 's/[^A-Za-z0-9._-][^A-Za-z0-9._-]*/_/g')
  if [ ${#s} -gt 200 ]; then s=${s: -200}; fi
  printf '%s/%s.lua' "$CACHE" "$s"
}

is_media() {
  local ext
  ext=$(printf '%s' "${1##*.}" | tr '[:upper:]' '[:lower:]')
  case " $EXTENSIONS " in *" $ext "*) return 0 ;; esac
  return 1
}

analyze() {
  local f="$1" out tmp db log
  out=$(cache_name "$f")
  if [ $FORCE -eq 0 ] && [ -f "$out" ] && [ "$out" -nt "$f" ]; then
    SKIPPED=$((SKIPPED + 1))
    return
  fi
  echo "Analizzo: $(basename "$f")"
  tmp="$out.tmp"
  printf 'return {\n  path = [==[%s]==],\n' "$f" > "$tmp"
  for db in $THRESHOLDS; do
    log=$("$FF" -nostdin -hide_banner -nostats -i "$f" -map 0:a:0 \
      -af "silencedetect=noise=${db}dB:d=${MIN_SILENCE}" -f null - 2>&1)
    if printf '%s' "$log" | grep -q "matches no streams"; then
      echo "   (nessun audio, salto)"
      rm -f "$tmp"
      NOAUDIO=$((NOAUDIO + 1))
      return
    fi
    printf '%s\n' "$log" | awk -v db="$db" '
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
        printf "  [%s] = { %s },\n", db, list
        if (db == -35 && dur != "") printf "  duration = %s,\n", dur
      }' >> "$tmp"
  done
  echo "}" >> "$tmp"
  mv "$tmp" "$out"
  DONE=$((DONE + 1))
}

DONE=0; SKIPPED=0; NOAUDIO=0
for arg in "$@"; do
  [ "$arg" != "/" ] && arg="${arg%/}"
  if [ -d "$arg" ]; then
    while IFS= read -r f; do
      f=$(printf '%s' "$f" | sed 's#//*#/#g')
      is_media "$f" && analyze "$f"
    done < <(find "$arg" -type f ! -name '._*' 2>/dev/null | sort)
  elif [ -f "$arg" ]; then
    analyze "$arg"
  else
    echo "!! Non trovato: $arg"
  fi
done

echo
echo "Fatto: $DONE file analizzati, $SKIPPED già pronti, $NOAUDIO senza audio."
