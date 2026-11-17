#!/usr/bin/env python3
"""Genera Installa-SilenceCut.command: un unico file che installa tutto sul Mac."""
import os
here = os.path.dirname(os.path.abspath(__file__))
lua = open(os.path.join(here, "SilenceCut.lua")).read()
sh = open(os.path.join(here, "analizza.sh")).read()

applescript = r'''on open theItems
	set analyzer to (POSIX path of (path to home folder)) & "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/SilenceCut/analizza.sh"
	set args to ""
	repeat with anItem in theItems
		set args to args & " " & quoted form of (POSIX path of anItem)
	end repeat
	display notification "Analisi dell'audio in corso..." with title "SilenceCut"
	try
		set out to do shell script "/bin/bash " & quoted form of analyzer & args
		display dialog (last paragraph of out) & return & return & "Ora in DaVinci Resolve: Workspace > Scripts > SilenceCut" buttons {"OK"} default button "OK" with title "SilenceCut"
	on error errMsg
		display dialog "Errore: " & errMsg buttons {"OK"} default button "OK" with title "SilenceCut" with icon caution
	end try
end open

on run
	set theFolder to choose folder with prompt "Scegli la cartella del girato da analizzare"
	open {theFolder}
end run
'''

wrapper = '''SC_PRESET = "{p}"
dofile(os.getenv("HOME") .. "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/SilenceCut.lua")
'''

out = '''#!/bin/bash
# Installa SilenceCut per DaVinci Resolve (macOS). Doppio clic, oppure:  bash Installa-SilenceCut.command
set -e
FUSION="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion"
UTIL="$FUSION/Scripts/Utility"
SC="$FUSION/SilenceCut"
APP="$HOME/Applications/SilenceCut Analizza.app"
mkdir -p "$UTIL" "$SC/cache" "$HOME/Applications"

echo "== Installazione SilenceCut =="

cat > "$UTIL/SilenceCut.lua" <<'SC_EOF_LUA'
''' + lua + '''SC_EOF_LUA

cat > "$UTIL/SilenceCut Aggressivo.lua" <<'SC_EOF_W1'
''' + wrapper.format(p="Aggressivo") + '''SC_EOF_W1

cat > "$UTIL/SilenceCut Delicato.lua" <<'SC_EOF_W2'
''' + wrapper.format(p="Delicato") + '''SC_EOF_W2

cat > "$SC/analizza.sh" <<'SC_EOF_SH'
''' + sh + '''SC_EOF_SH
chmod +x "$SC/analizza.sh"
echo "OK  Script per Resolve installati (menu Workspace > Scripts)"

if command -v osacompile >/dev/null 2>&1; then
  rm -rf "$APP"
  osacompile -o "$APP" <<'SC_EOF_AS'
''' + applescript + '''SC_EOF_AS
  echo "OK  App creata: $APP"
else
  echo "!!  osacompile non disponibile: app non creata"
fi

FF=""
for p in "$(command -v ffmpeg 2>/dev/null)" /opt/homebrew/bin/ffmpeg /usr/local/bin/ffmpeg; do
  [ -n "$p" ] && [ -x "$p" ] && FF="$p" && break
done
[ -n "$FF" ] && echo "OK  ffmpeg: $FF" || echo "!!  ffmpeg non trovato: esegui  brew install ffmpeg"

echo
echo "Fatto. Trascina 'SilenceCut Analizza' dalla finestra che si apre nel Dock."
echo "Poi riavvia DaVinci Resolve."
command -v open >/dev/null 2>&1 && open -R "$APP" || true
'''
dst = os.path.join(here, "Installa-SilenceCut.command")
open(dst, "w").write(out)
os.chmod(dst, 0o755)
print("creato", dst)
