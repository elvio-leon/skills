#!/usr/bin/env node
// Scarica i binari di ffmpeg e pandoc da includere nell'app.
// Uso: node scripts/fetch-binaries.mjs [--platform darwin|linux] [--arch arm64|x64]
// I file finiscono in vendor/<platform>-<arch>/ e vengono copiati nell'app da electron-builder.

import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const FFMPEG_RELEASE = 'b6.1.1'; // https://github.com/eugeneware/ffmpeg-static/releases
const PANDOC_VERSION = '3.8.2'; // https://github.com/jgm/pandoc/releases

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const args = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const platform = arg('platform', process.platform);
const arch = arg('arch', process.arch);
if (!['darwin', 'linux'].includes(platform)) throw new Error(`Piattaforma non supportata: ${platform}`);
if (!['arm64', 'x64'].includes(arch)) throw new Error(`Architettura non supportata: ${arch}`);

const dest = path.join(root, 'vendor', `${platform}-${arch}`);
fs.mkdirSync(dest, { recursive: true });
const stamp = path.join(dest, '.versions');
const wanted = `ffmpeg ${FFMPEG_RELEASE}\npandoc ${PANDOC_VERSION}\n`;
if (fs.existsSync(stamp) && fs.readFileSync(stamp, 'utf8') === wanted && fs.existsSync(path.join(dest, 'ffmpeg')) && fs.existsSync(path.join(dest, 'pandoc'))) {
  console.log(`Binari già presenti in ${dest}`);
  process.exit(0);
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'convertitutto-bin-'));

function download(url, file) {
  console.log(`↓ ${url}`);
  execFileSync('curl', ['-fsSL', '--retry', '4', '--retry-delay', '3', '-o', file, url], { stdio: 'inherit' });
}

function findFile(dir, name) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      const found = findFile(p, name);
      if (found) return found;
    } else if (entry.name === name) return p;
  }
  return null;
}

try {
  // ffmpeg (build statica con libx264, libx265, libvpx, libaom, SVT-AV1, libwebp, lame, opus, vorbis)
  const ffBase = `https://github.com/eugeneware/ffmpeg-static/releases/download/${FFMPEG_RELEASE}`;
  const gz = path.join(tmp, 'ffmpeg.gz');
  download(`${ffBase}/ffmpeg-${platform}-${arch}.gz`, gz);
  fs.writeFileSync(path.join(dest, 'ffmpeg'), zlib.gunzipSync(fs.readFileSync(gz)));
  fs.chmodSync(path.join(dest, 'ffmpeg'), 0o755);
  download(`${ffBase}/${platform}-${arch}.LICENSE`, path.join(dest, 'ffmpeg.LICENSE'));
  download(`${ffBase}/${platform}-${arch}.README`, path.join(dest, 'ffmpeg.README'));

  // pandoc
  const pandocArch = arch === 'arm64' ? 'arm64' : platform === 'darwin' ? 'x86_64' : 'amd64';
  const pandocFile = platform === 'darwin' ? `pandoc-${PANDOC_VERSION}-${pandocArch}-macOS.zip` : `pandoc-${PANDOC_VERSION}-linux-${pandocArch}.tar.gz`;
  const archive = path.join(tmp, pandocFile);
  download(`https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/${pandocFile}`, archive);
  const extracted = path.join(tmp, 'pandoc');
  fs.mkdirSync(extracted);
  if (pandocFile.endsWith('.zip')) execFileSync('unzip', ['-q', archive, '-d', extracted]);
  else execFileSync('tar', ['-xzf', archive, '-C', extracted]);
  const pandocBin = findFile(extracted, 'pandoc');
  if (!pandocBin) throw new Error('pandoc non trovato nell’archivio');
  fs.copyFileSync(pandocBin, path.join(dest, 'pandoc'));
  fs.chmodSync(path.join(dest, 'pandoc'), 0o755);

  // Su macOS i binari arm64 devono avere almeno una firma ad-hoc per essere eseguiti
  if (platform === 'darwin' && process.platform === 'darwin') {
    for (const bin of ['ffmpeg', 'pandoc']) {
      execFileSync('xattr', ['-c', path.join(dest, bin)]);
      execFileSync('codesign', ['--force', '--sign', '-', path.join(dest, bin)], { stdio: 'inherit' });
    }
  }

  fs.writeFileSync(stamp, wanted);
  console.log(`✓ Binari pronti in ${dest}`);
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}
