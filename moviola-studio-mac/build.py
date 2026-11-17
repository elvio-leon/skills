"""Costruisce Moviola Studio.dmg (macOS) da src/ e font/: python3 build.py"""
import os, re, shutil, subprocess, plistlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
R = Path(__file__).resolve().parent
OUT = R / "dist"; STAGE = R / "stage" / "Moviola Studio"
KEEP = "['scheda','contatore','risultato','confronto','classifica','timeline','grafico','lavagna','mappa']"

def page():
    src = (R / "src/index.html").read_text()
    src = re.sub(r'<link rel="preconnect"[^>]*>\n', '', src)
    src = re.sub(r'<link rel="stylesheet" href="https://fonts.googleapis.com[^>]*>', '<link rel="stylesheet" href="font/fonts.css">', src)
    src = src.replace('<script src="app.js"></script>',
        f'<script>window.PRESETS.splice(0, window.PRESETS.length, ...window.PRESETS.filter(p => {KEEP}.includes(p.id)));</script>\n<script src="app.js"></script>')
    src = src.replace('<p>Titoli, dati, tattica, transizioni e camera per documentari di calcio</p>', '<p>Schede giocatore, dati e tattica per documentari di calcio</p>')
    head = ('<!doctype html><html lang="it"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>body{margin:0;font:14px system-ui,sans-serif}[hidden]{display:none!important}img{max-width:100%}</style></head><body>')
    return head + src + '</body></html>'

def app_files(dst):
    dst.mkdir(parents=True, exist_ok=True)
    for f in (R / "src").glob("*.js"):
        t = f.read_text().replace('Nessun file: i preset "Camera" usano una foto di esempio', 'Nessun file: la scheda giocatore usa un ritratto di esempio')
        (dst / f.name).write_text(t)
    shutil.copytree(R / "font", dst / "font", dirs_exist_ok=True)
    (dst / "index.html").write_text(page())

def icon(path_png, path_icns):
    S = 1024; im = Image.new("RGBA", (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([60, 60, S - 60, S - 60], 200, fill=(24, 58, 47))
    d.rectangle([150, 150, S - 150, S - 150], outline=(245, 239, 230, 120), width=6)
    f = ImageFont.truetype(str(R / "font/Anton-400.ttf"), 560)
    d.text((S / 2, S / 2 - 30), "M", font=f, fill=(245, 239, 230), anchor="mm")
    d.rectangle([310, 760, S - 310, 790], fill=(181, 50, 60))
    im.save(path_png); im.save(path_icns, sizes=[(16,16),(32,32),(64,64),(128,128),(256,256),(512,512),(1024,1024)])

LAUNCHER = r'''#!/bin/bash
# Avvia Moviola Studio in una finestra propria di Chrome (o Edge/Brave), altrimenti nel browser predefinito.
DIR="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
URL="file://${DIR// /%20}/index.html"
DATA="$HOME/Library/Application Support/Moviola Studio/browser"
for B in "Google Chrome" "Microsoft Edge" "Brave Browser" "Chromium"; do
  for P in "/Applications/$B.app" "$HOME/Applications/$B.app"; do
    if [ -d "$P" ]; then
      mkdir -p "$DATA"
      open -na "$P" --args --app="$URL" --user-data-dir="$DATA" --no-first-run --no-default-browser-check --window-size=1500,950
      exit 0
    fi
  done
done
open "$DIR/index.html"
'''

def main():
    shutil.rmtree(R / "stage", ignore_errors=True); OUT.mkdir(exist_ok=True)
    app = STAGE / "Moviola Studio.app" / "Contents"
    (app / "MacOS").mkdir(parents=True); (app / "Resources").mkdir()
    app_files(app / "Resources" / "app")
    icon(R / "stage" / "icona.png", app / "Resources" / "icona.icns")
    (app / "MacOS" / "moviola").write_text(LAUNCHER); os.chmod(app / "MacOS" / "moviola", 0o755)
    plistlib.dump({"CFBundleName": "Moviola Studio", "CFBundleDisplayName": "Moviola Studio", "CFBundleExecutable": "moviola",
                   "CFBundleIdentifier": "it.moviola.studio", "CFBundlePackageType": "APPL", "CFBundleIconFile": "icona",
                   "CFBundleShortVersionString": "1.0", "CFBundleVersion": "1", "LSMinimumSystemVersion": "10.13",
                   "NSHighResolutionCapable": True}, open(app / "Info.plist", "wb"))
    app_files(STAGE / "Versione browser")
    (STAGE / "Versione browser" / "index.html").rename(STAGE / "Versione browser" / "Apri Moviola Studio.html")
    shutil.copy(R / "LEGGIMI.txt", STAGE / "LEGGIMI.txt")
    os.symlink("/Applications", STAGE / "Applicazioni")
    dmg = OUT / "Moviola Studio.dmg"
    subprocess.run(["genisoimage", "-quiet", "-V", "Moviola Studio", "-R", "-J", "-joliet-long", "-D", "-iso-level", "3",
                    "-o", str(dmg), str(STAGE)], check=True)
    print(dmg, dmg.stat().st_size // 1024, "KB")

if __name__ == "__main__":
    main()
