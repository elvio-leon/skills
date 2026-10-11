#!/usr/bin/env node
// Prepara i motori da includere nell'app:
// - ffmpeg e pandoc (binari statici)
// - un Python portatile con pdf2docx e PyMuPDF (PDF → Word, tabelle dei PDF)
// - su macOS, il programma `ocr` (riconoscimento testo con Vision), compilato da src/native/ocr.swift
// Uso: node scripts/fetch-binaries.mjs [--platform darwin|linux] [--arch arm64|x64]
// I file finiscono in vendor/<platform>-<arch>/ e vengono copiati nell'app da electron-builder.

import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import { fileURLToPath } from 'node:url';

const FFMPEG_RELEASE = 'b6.1.1'; // https://github.com/eugeneware/ffmpeg-static/releases
const PANDOC_VERSION = '3.8.2'; // https://github.com/jgm/pandoc/releases
const PYTHON_RELEASE = '20250918'; // https://github.com/astral-sh/python-build-standalone/releases
const PYTHON_VERSION = '3.12.11';
const PY_PACKAGES = ['pdf2docx==0.5.13', 'pymupdf'];

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
const onMac = platform === 'darwin' && process.platform === 'darwin';

const dest = path.join(root, 'vendor', `${platform}-${arch}`);
fs.mkdirSync(dest, { recursive: true });
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'metatropi-bin-'));

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

// Ogni componente viene rifatto solo se la sua "impronta" (versioni, sorgenti) è cambiata
function step(name, fingerprint, outputs, fn) {
  const stamp = path.join(dest, `.${name}.stamp`);
  if (fs.existsSync(stamp) && fs.readFileSync(stamp, 'utf8') === fingerprint && outputs.every((o) => fs.existsSync(path.join(dest, o)))) {
    console.log(`✓ ${name} già pronto`);
    return;
  }
  fn();
  fs.writeFileSync(stamp, fingerprint);
  console.log(`✓ ${name} pronto`);
}

function adhocSign(file) {
  if (!onMac) return;
  execFileSync('xattr', ['-c', file]);
  execFileSync('codesign', ['--force', '--sign', '-', file], { stdio: 'inherit' });
}

try {
  // ---------- ffmpeg ----------
  step('ffmpeg', FFMPEG_RELEASE, ['ffmpeg'], () => {
    const base = `https://github.com/eugeneware/ffmpeg-static/releases/download/${FFMPEG_RELEASE}`;
    const gz = path.join(tmp, 'ffmpeg.gz');
    download(`${base}/ffmpeg-${platform}-${arch}.gz`, gz);
    fs.writeFileSync(path.join(dest, 'ffmpeg'), zlib.gunzipSync(fs.readFileSync(gz)));
    fs.chmodSync(path.join(dest, 'ffmpeg'), 0o755);
    download(`${base}/${platform}-${arch}.LICENSE`, path.join(dest, 'ffmpeg.LICENSE'));
    download(`${base}/${platform}-${arch}.README`, path.join(dest, 'ffmpeg.README'));
    adhocSign(path.join(dest, 'ffmpeg'));
  });

  // ---------- pandoc ----------
  step('pandoc', PANDOC_VERSION, ['pandoc'], () => {
    const pandocArch = arch === 'arm64' ? 'arm64' : platform === 'darwin' ? 'x86_64' : 'amd64';
    const file = platform === 'darwin' ? `pandoc-${PANDOC_VERSION}-${pandocArch}-macOS.zip` : `pandoc-${PANDOC_VERSION}-linux-${pandocArch}.tar.gz`;
    const archive = path.join(tmp, file);
    download(`https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/${file}`, archive);
    const extracted = path.join(tmp, 'pandoc');
    fs.mkdirSync(extracted);
    if (file.endsWith('.zip')) execFileSync('unzip', ['-q', archive, '-d', extracted]);
    else execFileSync('tar', ['-xzf', archive, '-C', extracted]);
    const bin = findFile(extracted, 'pandoc');
    if (!bin) throw new Error('pandoc non trovato nell’archivio');
    fs.copyFileSync(bin, path.join(dest, 'pandoc'));
    fs.chmodSync(path.join(dest, 'pandoc'), 0o755);
    adhocSign(path.join(dest, 'pandoc'));
  });

  // ---------- Python portatile con pdf2docx ----------
  step('python', `${PYTHON_RELEASE} ${PYTHON_VERSION} ${PY_PACKAGES.join(' ')}`, ['python/bin/python3'], () => {
    const triple = {
      'darwin-arm64': 'aarch64-apple-darwin',
      'darwin-x64': 'x86_64-apple-darwin',
      'linux-x64': 'x86_64-unknown-linux-gnu',
      'linux-arm64': 'aarch64-unknown-linux-gnu',
    }[`${platform}-${arch}`];
    const file = `cpython-${PYTHON_VERSION}+${PYTHON_RELEASE}-${triple}-install_only_stripped.tar.gz`;
    const archive = path.join(tmp, file);
    download(`https://github.com/astral-sh/python-build-standalone/releases/download/${PYTHON_RELEASE}/${file}`, archive);
    const pyDir = path.join(dest, 'python');
    fs.rmSync(pyDir, { recursive: true, force: true });
    execFileSync('tar', ['-xzf', archive, '-C', dest]);
    const python = path.join(pyDir, 'bin', 'python3');
    // Su un Mac Apple Silicon la versione Intel si installa tramite Rosetta
    const runner = onMac && arch !== process.arch ? ['arch', [`-${arch === 'x64' ? 'x86_64' : 'arm64'}`, python]] : [python, []];
    const pip = (...a) => execFileSync(runner[0], [...runner[1], '-m', 'pip', ...a], { stdio: 'inherit', env: { ...process.env, PIP_DISABLE_PIP_VERSION_CHECK: '1' } });
    pip('install', '--no-cache-dir', '--no-compile', '--only-binary=:all:', ...PY_PACKAGES);
    pip('uninstall', '-y', 'pip');
    prunePython(pyDir);
    if (onMac) signTree(pyDir);
  });

  // ---------- OCR (solo macOS) ----------
  if (platform === 'darwin') {
    const source = path.join(root, 'src', 'native', 'ocr.swift');
    const hash = crypto.createHash('sha256').update(fs.readFileSync(source)).digest('hex');
    if (onMac) {
      step('ocr', hash, ['ocr'], () => {
        const target = `${arch === 'arm64' ? 'arm64' : 'x86_64'}-apple-macos12.0`;
        execFileSync('swiftc', ['-O', '-target', target, '-o', path.join(dest, 'ocr'), source], { stdio: 'inherit' });
        adhocSign(path.join(dest, 'ocr'));
      });
    } else {
      console.log('! ocr: va compilato su un Mac (swiftc), salto');
    }
  }
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}

// Toglie dal Python tutto ciò che non serve per eseguire gli script di conversione
function prunePython(pyDir) {
  const lib = path.join(pyDir, 'lib', `python${PYTHON_VERSION.split('.').slice(0, 2).join('.')}`);
  const remove = [
    path.join(pyDir, 'include'),
    path.join(pyDir, 'share'),
    ...['test', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', 'lib2to3', 'pydoc_data', 'unittest/test', 'sqlite3/test', 'ctypes/test', 'distutils/tests']
      .map((d) => path.join(lib, d)),
  ];
  for (const entry of fs.readdirSync(lib)) {
    if (entry.startsWith('config-')) remove.push(path.join(lib, entry));
  }
  for (const entry of fs.readdirSync(path.join(pyDir, 'lib'))) {
    if (/^(tcl|tk|itcl|thread)\d|^lib(tcl|tk)/.test(entry)) remove.push(path.join(pyDir, 'lib', entry));
  }
  const dynload = path.join(lib, 'lib-dynload');
  if (fs.existsSync(dynload)) {
    for (const entry of fs.readdirSync(dynload)) if (entry.startsWith('_tkinter') || entry.includes('_test')) remove.push(path.join(dynload, entry));
  }
  for (const p of remove) fs.rmSync(p, { recursive: true, force: true });
  // cache di bytecode e test dei pacchetti
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (entry.name === '__pycache__' || (dir.includes('site-packages') && /^tests?$/.test(entry.name))) fs.rmSync(p, { recursive: true, force: true });
        else walk(p);
      }
    }
  };
  walk(pyDir);
  // in bin/ servono solo gli eseguibili python
  for (const entry of fs.readdirSync(path.join(pyDir, 'bin'))) {
    if (!/^python3(\.\d+)?$/.test(entry)) fs.rmSync(path.join(pyDir, 'bin', entry), { recursive: true, force: true });
  }
}

// Firma ad-hoc ogni file Mach-O del Python (librerie native comprese)
function signTree(dir) {
  const files = [];
  const walk = (d) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const p = path.join(d, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) walk(p);
      else {
        const fd = fs.openSync(p, 'r');
        const buf = Buffer.alloc(4);
        fs.readSync(fd, buf, 0, 4, 0);
        fs.closeSync(fd);
        const magic = buf.readUInt32BE(0);
        if ([0xcffaedfe, 0xcefaedfe, 0xfeedfacf, 0xfeedface, 0xcafebabe].includes(magic)) files.push(p);
      }
    }
  };
  walk(dir);
  for (const f of files) {
    execFileSync('xattr', ['-c', f]);
    execFileSync('codesign', ['--force', '--sign', '-', f]);
  }
  console.log(`  firmati ${files.length} file nativi del Python`);
}
