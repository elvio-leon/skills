#!/bin/bash
# Installa il template "Mi piace Iscriviti" e i font Roboto per DaVinci Resolve su macOS.
# Uso: apri il Terminale, scrivi "bash " (con lo spazio), trascina qui questo file e premi Invio.
set -euo pipefail
cd "$(dirname "$0")"

DEST="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit/Titles/Like e Iscriviti"
mkdir -p "$DEST"
cp "Mi piace Iscriviti.setting" "Mi piace Iscriviti.png" "$DEST/"
echo "Template copiato in: $DEST"

FONTS="fonts"
[ -d "$FONTS" ] || FONTS="../fonts"
mkdir -p "$HOME/Library/Fonts"
cp "$FONTS/Roboto-Medium.ttf" "$FONTS/Roboto-Bold.ttf" "$HOME/Library/Fonts/"
echo "Font Roboto Medium e Bold installati."

echo "Fatto. Chiudi e riapri DaVinci Resolve: lo trovi in Effects > Titles > Fusion Titles."
