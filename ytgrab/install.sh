#!/bin/bash
# Installa YTGrab in ~/Applications (macOS, Apple Silicon o Intel).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
SUPPORT="$HOME/Library/Application Support/YTGrab"
APP="$HOME/Applications/YTGrab.app"

if ! command -v brew >/dev/null 2>&1; then
  echo "Serve Homebrew: https://brew.sh" >&2
  exit 1
fi

echo "→ Dipendenze di sistema (python, ffmpeg, deno)…"
brew install python@3.12 ffmpeg deno

PY="$(brew --prefix python@3.12)/bin/python3.12"

echo "→ Ambiente Python…"
mkdir -p "$SUPPORT/app"
[ -x "$SUPPORT/venv/bin/python" ] || "$PY" -m venv "$SUPPORT/venv"
"$SUPPORT/venv/bin/python" -m pip install --quiet --upgrade pip
"$SUPPORT/venv/bin/python" -m pip install --quiet --upgrade -r "$SRC/requirements.txt"

echo "→ Copio l'app…"
rm -rf "$SUPPORT/app"
mkdir -p "$SUPPORT/app"
cp -R "$SRC/app.py" "$SRC/web" "$SUPPORT/app/"

echo "→ Creo $APP…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/MacOS/YTGrab" <<'SH'
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
DIR="$HOME/Library/Application Support/YTGrab"
exec "$DIR/venv/bin/python" "$DIR/app/app.py" "$@"
SH
chmod +x "$APP/Contents/MacOS/YTGrab"
cat > "$APP/Contents/Info.plist" <<'PL'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>YTGrab</string>
  <key>CFBundleDisplayName</key><string>YTGrab</string>
  <key>CFBundleIdentifier</key><string>local.ytgrab</string>
  <key>CFBundleExecutable</key><string>YTGrab</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PL

echo
echo "✓ Fatto. Apri YTGrab da ~/Applications (o con Spotlight: ⌘Spazio → YTGrab)."
echo "  I download finiscono in ~/Movies/YTGrab (modificabile dall'app)."
