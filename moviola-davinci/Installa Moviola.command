#!/bin/bash
# Moviola per DaVinci Resolve - installazione su Mac
# Doppio clic su questo file. Se macOS lo blocca: tasto destro > Apri
# (su macOS 15: Impostazioni di Sistema > Privacy e sicurezza > Apri comunque).
cd "$(dirname "$0")" || exit 1
echo "=============================================="
echo "  Moviola per DaVinci Resolve - Installazione"
echo "=============================================="
echo "Chiudi DaVinci Resolve, poi premi Invio..."
read -r
echo "[1/2] Installo i font in ~/Library/Fonts"
mkdir -p "$HOME/Library/Fonts" && cp Font/*.ttf "$HOME/Library/Fonts/" && echo "      OK"
DST="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit"
echo "[2/2] Copio i template in: $DST"
mkdir -p "$DST" && cp -R Templates/Edit/ "$DST/" && echo "      OK"
echo
echo "Fatto. Riapri DaVinci Resolve e cerca \"MOV\" nella Effects Library."
echo "Per i progetti a 60 fps fai doppio clic su Moviola-60fps.drfx."
echo "Gli effetti sonori sono nella cartella SFX: importali nel Media Pool."
