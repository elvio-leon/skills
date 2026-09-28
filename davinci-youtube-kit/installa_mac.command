#!/bin/bash
# YouTube Kit per DaVinci Resolve - installer macOS
# Doppio clic su questo file (se macOS lo blocca: tasto destro > Apri).
cd "$(dirname "$0")" || exit 1
echo "=============================================="
echo "  YouTube Kit per DaVinci Resolve - Installer"
echo "=============================================="
echo "Chiudi DaVinci Resolve prima di continuare. Premi Invio..."
read -r

DST="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit"
echo "[1/2] Copio i template in: $DST"
mkdir -p "$DST" && cp -R Templates/Edit/ "$DST/" && echo "      OK"

LUTDST="/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/YouTube Kit"
echo "[2/2] Copio le LUT in: $LUTDST"
if mkdir -p "$LUTDST" 2>/dev/null && cp LUT/*.cube "$LUTDST/" 2>/dev/null; then
  echo "      OK"
else
  echo "      Serve la password di amministratore per la cartella LUT:"
  sudo mkdir -p "$LUTDST" && sudo cp LUT/*.cube "$LUTDST/" && echo "      OK" || \
  echo "      Copia a mano la cartella LUT (Impostazioni progetto > Color Management > Open LUT Folder)."
fi

echo
echo "Fatto! Riapri DaVinci Resolve e cerca \"YTK\" nella Effects Library."
echo "Gli effetti sonori sono nella cartella SFX: importali nel Media Pool."
