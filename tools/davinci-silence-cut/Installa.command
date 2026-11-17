#!/bin/bash
# Doppio clic su questo file per installare SilenceCut in DaVinci Resolve (macOS).
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit"

echo "== Installazione SilenceCut per DaVinci Resolve =="
mkdir -p "$DEST"
cp "$DIR/SilenceCut.py" "$DEST/SilenceCut.py"
echo "OK  Script copiato in: $DEST"

if command -v python3 >/dev/null 2>&1; then
  echo "OK  Python 3 trovato: $(python3 --version 2>&1)"
else
  echo "!!  Python 3 non trovato. Scaricalo da https://www.python.org/downloads/macos/"
fi

FF=""
for p in "$(command -v ffmpeg 2>/dev/null)" /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do
  [ -n "$p" ] && [ -x "$p" ] && FF="$p" && break
done
if [ -n "$FF" ]; then
  echo "OK  ffmpeg trovato: $FF"
else
  echo "!!  ffmpeg non trovato. Installa Homebrew (https://brew.sh) e poi esegui:  brew install ffmpeg"
fi

echo
echo "Fatto. Riavvia DaVinci Resolve, seleziona le clip nel Media Pool e usa:"
echo "   Workspace > Scripts > Edit > SilenceCut"
echo
read -n 1 -s -r -p "Premi un tasto per chiudere..."
