'use strict';

const fs = require('fs');
const fsp = require('fs/promises');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');

const IS_MAC = process.platform === 'darwin';
const EXTRA_PATHS = ['/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin'];

function isExecutable(p) {
  try {
    fs.accessSync(p, fs.constants.X_OK);
    return fs.statSync(p).isFile();
  } catch {
    return false;
  }
}

function which(name) {
  const dirs = (process.env.PATH || '').split(path.delimiter).concat(EXTRA_PATHS);
  for (const dir of dirs) {
    if (!dir) continue;
    const p = path.join(dir, name);
    if (isExecutable(p)) return p;
  }
  return null;
}

// Cerca prima i binari inclusi nell'app, poi quelli scaricati in sviluppo,
// infine quelli installati nel sistema.
function bundledBinary(name) {
  const candidates = [];
  if (process.resourcesPath) candidates.push(path.join(process.resourcesPath, 'bin', name));
  candidates.push(path.join(__dirname, '..', '..', 'vendor', `${process.platform}-${process.arch}`, name));
  for (const p of candidates) if (isExecutable(p)) return p;
  return which(name);
}

function findLibreOffice() {
  const candidates = IS_MAC
    ? ['/Applications/LibreOffice.app/Contents/MacOS/soffice', path.join(os.homedir(), 'Applications/LibreOffice.app/Contents/MacOS/soffice')]
    : [];
  for (const p of candidates) if (isExecutable(p)) return p;
  return which('soffice') || which('libreoffice');
}

let cachedTools = null;
function tools() {
  if (!cachedTools) {
    cachedTools = {
      ffmpeg: bundledBinary('ffmpeg'),
      pandoc: bundledBinary('pandoc'),
      libreoffice: findLibreOffice(),
      sips: IS_MAC && isExecutable('/usr/bin/sips') ? '/usr/bin/sips' : null,
      textutil: IS_MAC && isExecutable('/usr/bin/textutil') ? '/usr/bin/textutil' : null,
    };
  }
  return cachedTools;
}

function refreshTools() {
  cachedTools = null;
  return tools();
}

function env() {
  const t = tools();
  return {
    mac: IS_MAC,
    ffmpeg: !!t.ffmpeg,
    pandoc: !!t.pandoc,
    libreoffice: !!t.libreoffice,
  };
}

class ConversionError extends Error {
  constructor(message, details) {
    super(message);
    this.details = details || '';
  }
}

class CancelledError extends Error {
  constructor() {
    super('Conversione annullata');
    this.cancelled = true;
  }
}

// Esegue un programma senza shell. `signal` (AbortSignal) lo termina.
// Con `allowFailure` la promessa si risolve comunque, restituendo anche `code`.
function run(cmd, args, { cwd, signal, onStdout, onStderr, env: extraEnv, input, allowFailure } = {}) {
  return new Promise((resolve, reject) => {
    if (signal && signal.aborted) return reject(new CancelledError());
    const child = spawn(cmd, args, {
      cwd,
      env: { ...process.env, ...(extraEnv || {}) },
      stdio: [input != null ? 'pipe' : 'ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    const onAbort = () => child.kill('SIGKILL');
    if (signal) signal.addEventListener('abort', onAbort, { once: true });
    child.stdout.on('data', (d) => {
      const s = d.toString();
      stdout += s;
      if (stdout.length > 4e6) stdout = stdout.slice(-2e6);
      if (onStdout) onStdout(s);
    });
    child.stderr.on('data', (d) => {
      const s = d.toString();
      stderr += s;
      if (stderr.length > 4e6) stderr = stderr.slice(-2e6);
      if (onStderr) onStderr(s);
    });
    if (input != null) child.stdin.end(input);
    child.on('error', (err) => {
      if (signal) signal.removeEventListener('abort', onAbort);
      reject(new ConversionError(`Impossibile avviare ${path.basename(cmd)}: ${err.message}`));
    });
    child.on('close', (code) => {
      if (signal) signal.removeEventListener('abort', onAbort);
      if (signal && signal.aborted) return reject(new CancelledError());
      if (code === 0 || allowFailure) resolve({ code, stdout, stderr });
      else {
        const tail = stderr.trim().split('\n').slice(-15).join('\n');
        reject(new ConversionError(`${path.basename(cmd)} ha restituito un errore (codice ${code})`, tail));
      }
    });
  });
}

async function makeTempDir() {
  return fsp.mkdtemp(path.join(os.tmpdir(), 'convertitutto-'));
}

async function removeDir(dir) {
  if (!dir) return;
  await fsp.rm(dir, { recursive: true, force: true }).catch(() => {});
}

// Restituisce un percorso libero: "nome.ext", "nome (1).ext", ...
function uniquePath(dir, base, ext) {
  let candidate = path.join(dir, ext ? `${base}.${ext}` : base);
  let i = 1;
  while (fs.existsSync(candidate)) {
    candidate = path.join(dir, ext ? `${base} (${i}).${ext}` : `${base} (${i})`);
    i += 1;
  }
  return candidate;
}

async function moveFile(from, to) {
  try {
    await fsp.rename(from, to);
  } catch (err) {
    if (err.code !== 'EXDEV') throw err;
    await fsp.copyFile(from, to);
    await fsp.unlink(from);
  }
}

module.exports = {
  IS_MAC,
  tools,
  refreshTools,
  env,
  run,
  makeTempDir,
  removeDir,
  uniquePath,
  moveFile,
  ConversionError,
  CancelledError,
};
