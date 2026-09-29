#!/bin/bash
# Costruisce "dist/Prospect Scraper.app" e "dist/Prospect Scraper.dmg" (Apple Silicon).
# Usato da GitHub Actions; funziona anche su un Mac con Python 3.11+.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
B="$ROOT/build/mac"
NAME="Prospect Scraper"
VERSION="${VERSION:-1.0.0}"
rm -rf "$B" dist
mkdir -p "$B/dmg"

echo "::group::Dipendenze Python"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt "pywebview>=5.0" pyinstaller pillow
echo "::endgroup::"

python3 packaging/make_icon.py "$B/icon.png"

source packaging/pyinstaller_args.sh
echo "::group::PyInstaller"
python3 -m PyInstaller --noconfirm --windowed \
  --name "$NAME" \
  --osx-bundle-identifier local.prospectscraper \
  --target-arch arm64 \
  --icon "$B/icon.png" \
  --distpath "$ROOT/dist" --workpath "$B/work" --specpath "$B" \
  "${PYI_ARGS[@]}" \
  desktop.py
echo "::endgroup::"

APP="$ROOT/dist/$NAME.app"
PL="$APP/Contents/Info.plist"
plutil -replace CFBundleDisplayName -string "$NAME" "$PL"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PL"
plutil -replace CFBundleVersion -string "$VERSION" "$PL"
plutil -replace LSMinimumSystemVersion -string "11.0" "$PL"
plutil -replace NSHighResolutionCapable -bool true "$PL"
plutil -replace NSDownloadsFolderUsageDescription -string \
  "Prospect Scraper salva gli export (CSV/Excel) nella cartella Download." "$PL"

# Firma ad-hoc (obbligatoria su Apple Silicon).
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

echo "::group::DMG"
cp -R "$APP" "$B/dmg/"
ln -s /Applications "$B/dmg/Applications"
hdiutil create -volname "$NAME" -srcfolder "$B/dmg" -ov -format UDZO "$ROOT/dist/ProspectScraper.dmg"
echo "::endgroup::"

du -sh "$APP" "$ROOT/dist/ProspectScraper.dmg"
