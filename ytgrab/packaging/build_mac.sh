#!/bin/bash
# Costruisce dist/YTGrab.app e dist/YTGrab.dmg (Apple Silicon) con ffmpeg, ffprobe e deno inclusi.
# Usato da GitHub Actions; funziona anche su un Mac con Python 3.10+.
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"
B="$ROOT/build/mac"
VERSION="${VERSION:-1.0.0}"
rm -rf "$B" dist
mkdir -p "$B/bin" "$B/dmg"

echo "::group::Dipendenze Python"
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller pillow
echo "::endgroup::"

echo "::group::ffmpeg, ffprobe, deno (arm64 statici)"
for tool in ffmpeg ffprobe; do
  curl -fsSL --retry 3 -o "$B/$tool.zip" \
    "https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/$tool.zip"
  unzip -o -q "$B/$tool.zip" -d "$B/bin"
done
curl -fsSL --retry 3 -o "$B/deno.zip" \
  "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-apple-darwin.zip"
unzip -o -q "$B/deno.zip" -d "$B/bin"
chmod +x "$B/bin/"*
for tool in ffmpeg ffprobe deno; do
  file "$B/bin/$tool"
  if otool -L "$B/bin/$tool" | grep -E "/opt/homebrew|/usr/local"; then
    echo "$tool dipende da librerie esterne" >&2; exit 1
  fi
done
"$B/bin/ffmpeg" -hide_banner -version | head -1
"$B/bin/ffmpeg" -hide_banner -encoders | grep -q hevc_videotoolbox \
  && echo "hevc_videotoolbox disponibile" || echo "::warning::ffmpeg senza hevc_videotoolbox"
"$B/bin/deno" --version | head -1
echo "::endgroup::"

python3 -c "import yt_dlp; print(yt_dlp.version.__version__)" > "$B/ytdlp_version.txt"
python3 packaging/make_icon.py "$B/icon.png"

echo "::group::PyInstaller"
python3 -m PyInstaller --noconfirm --windowed \
  --name YTGrab \
  --osx-bundle-identifier local.ytgrab \
  --target-arch arm64 \
  --icon "$B/icon.png" \
  --distpath "$ROOT/dist" --workpath "$B/work" --specpath "$B" \
  --add-data "$ROOT/web:web" \
  --add-data "$B/ytdlp_version.txt:." \
  --collect-all yt_dlp_ejs \
  --collect-submodules yt_dlp \
  app.py
echo "::endgroup::"

APP="$ROOT/dist/YTGrab.app"
mkdir -p "$APP/Contents/MacOS/bin"
cp "$B/bin/ffmpeg" "$B/bin/ffprobe" "$B/bin/deno" "$APP/Contents/MacOS/bin/"

PL="$APP/Contents/Info.plist"
plutil -replace CFBundleDisplayName -string "YTGrab" "$PL"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$PL"
plutil -replace CFBundleVersion -string "$VERSION" "$PL"
plutil -replace LSMinimumSystemVersion -string "11.0" "$PL"
plutil -replace NSHighResolutionCapable -bool true "$PL"

# Firma ad-hoc (obbligatoria su Apple Silicon).
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

echo "::group::DMG"
cp -R "$APP" "$B/dmg/"
ln -s /Applications "$B/dmg/Applications"
hdiutil create -volname "YTGrab" -srcfolder "$B/dmg" -ov -format UDZO "$ROOT/dist/YTGrab.dmg"
echo "::endgroup::"

du -sh "$APP" "$ROOT/dist/YTGrab.dmg"
