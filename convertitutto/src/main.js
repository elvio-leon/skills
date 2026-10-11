'use strict';

const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const { app, BrowserWindow, ipcMain, dialog, shell, protocol, nativeTheme } = require('electron');

protocol.registerSchemesAsPrivileged([
  { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } },
]);

const { describeTargets, familyOf, CATEGORY_OF_FAMILY, CATEGORY_LABELS } = require('./core/formats');
const { tools, env } = require('./core/tools');
const { convertFile, mergeImagesToPdf } = require('./core/convert');
const chromium = require('./core/chromium');

const SELFTEST = process.argv.includes('--selftest');
const UI_DIR = path.join(__dirname, 'ui');
const PDFJS_DIR = path.join(__dirname, '..', 'node_modules', 'pdfjs-dist');
const CONCURRENCY = 2;
const MAX_FILES = 2000;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.wasm': 'application/wasm',
  '.bcmap': 'application/octet-stream',
  '.pfb': 'application/octet-stream',
  '.ttf': 'font/ttf',
  '.icc': 'application/vnd.iccprofile',
};

function registerAppProtocol() {
  protocol.handle('app', async (request) => {
    const url = new URL(request.url);
    let rel = decodeURIComponent(url.pathname);
    let base = UI_DIR;
    if (rel.startsWith('/vendor/pdfjs/')) {
      base = PDFJS_DIR;
      rel = rel.slice('/vendor/pdfjs'.length);
    }
    const file = path.normalize(path.join(base, rel));
    if (!file.startsWith(base + path.sep)) return new Response('Forbidden', { status: 403 });
    try {
      const data = await fsp.readFile(file);
      return new Response(data, { headers: { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' } });
    } catch {
      return new Response('Not found', { status: 404 });
    }
  });
}

// ---------- Finestra principale ----------

let mainWindow = null;
const pendingOpen = [];

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1080,
    height: 760,
    minWidth: 780,
    minHeight: 560,
    show: false,
    title: 'Convertitutto',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: nativeTheme.shouldUseDarkColors ? '#1c1c1e' : '#f5f5f7',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  mainWindow.webContents.on('will-navigate', (e) => e.preventDefault());
  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.webContents.once('did-finish-load', () => {
    if (pendingOpen.length) mainWindow.webContents.send('open-files', pendingOpen.splice(0));
  });
  mainWindow.on('closed', () => {
    mainWindow = null;
    chromium.closeEngine();
  });
  mainWindow.loadURL('app://local/index.html');
}

// File aperti trascinandoli sull'icona nel Dock o con "Apri con"
app.on('open-file', (event, filePath) => {
  event.preventDefault();
  if (mainWindow && !mainWindow.webContents.isLoading()) mainWindow.webContents.send('open-files', [filePath]);
  else pendingOpen.push(filePath);
});

function fromMainWindow(event) {
  return mainWindow && event.sender === mainWindow.webContents;
}

function handle(channel, fn) {
  ipcMain.handle(channel, (event, ...args) => {
    if (!fromMainWindow(event)) throw new Error('Richiesta non autorizzata');
    return fn(event, ...args);
  });
}

// ---------- Descrizione dei file ----------

async function expandPaths(paths) {
  const out = [];
  async function walk(p, depth) {
    if (out.length >= MAX_FILES) return;
    let st;
    try {
      st = await fsp.stat(p);
    } catch {
      return;
    }
    if (st.isDirectory()) {
      // I pacchetti macOS (.pages, .key, .numbers salvati come cartella) sono trattati come file
      if (familyOf(path.extname(p).slice(1))) return out.push({ path: p, size: st.size });
      if (depth > 6) return;
      const entries = await fsp.readdir(p).catch(() => []);
      for (const name of entries.sort()) {
        if (!name.startsWith('.')) await walk(path.join(p, name), depth + 1);
      }
    } else if (st.isFile()) {
      out.push({ path: p, size: st.size });
    }
  }
  for (const p of paths) await walk(p, 0);
  return out;
}

function describe(file) {
  const ext = path.extname(file.path).slice(1).toLowerCase();
  const family = familyOf(ext);
  return {
    path: file.path,
    name: path.basename(file.path),
    ext,
    size: file.size,
    family,
    category: family ? CATEGORY_OF_FAMILY[family] : null,
    targets: family ? describeTargets(ext, env()) : [],
  };
}

// ---------- Coda di conversione ----------

let currentRun = null;

async function runQueue(jobs, options, sender) {
  const controller = new AbortController();
  currentRun = controller;
  const send = (channel, msg) => {
    if (!sender.isDestroyed()) sender.send(channel, msg);
  };
  const jobOptions = { ...options };
  const outDir = options.outDir && fs.existsSync(options.outDir) ? options.outDir : null;

  let queue = jobs.map((j) => ({ ids: [j.id], input: j.input, targetId: j.targetId }));
  if (options.mergePdf) {
    const isImage = (j) => j.targetId === 'pdf' && CATEGORY_OF_FAMILY[familyOf(path.extname(j.input).slice(1))] === 'image';
    const images = queue.filter(isImage);
    if (images.length > 1) {
      queue = queue.filter((j) => !isImage(j));
      queue.unshift({ ids: images.flatMap((j) => j.ids), merge: images.map((j) => j.input) });
    }
  }

  const runOne = async (job) => {
    for (const id of job.ids) send('job:update', { id, status: 'running', progress: null });
    let last = 0;
    const onProgress = (p) => {
      const now = Date.now();
      if (now - last < 120) return;
      last = now;
      for (const id of job.ids) send('job:update', { id, status: 'running', progress: p });
    };
    const ctx = { signal: controller.signal, onProgress, chromium };
    try {
      const result = job.merge
        ? await mergeImagesToPdf(job.merge, outDir, jobOptions, ctx)
        : await convertFile({ input: job.input, targetId: job.targetId, outDir, options: jobOptions }, ctx);
      for (const id of job.ids) send('job:update', { id, status: 'done', progress: 1, outputs: result.outputs });
    } catch (err) {
      const cancelled = err.cancelled || controller.signal.aborted;
      if (!cancelled) console.error(err);
      for (const id of job.ids) {
        send('job:update', {
          id,
          status: cancelled ? 'cancelled' : 'error',
          error: cancelled ? 'Annullata' : err.message || String(err),
          details: err.details || '',
        });
      }
    }
  };

  const workers = Array.from({ length: CONCURRENCY }, async () => {
    while (queue.length && !controller.signal.aborted) await runOne(queue.shift());
  });
  await Promise.all(workers);
  for (const job of queue) for (const id of job.ids) send('job:update', { id, status: 'cancelled', error: 'Annullata' });
  if (currentRun === controller) currentRun = null;
  send('queue:done', {});
}

function registerIpc() {
  handle('env', () => {
    const t = tools();
    return {
      platform: process.platform,
      version: app.getVersion(),
      engines: {
        ffmpeg: !!t.ffmpeg,
        pandoc: !!t.pandoc,
        libreoffice: !!t.libreoffice,
        sips: !!t.sips,
        textutil: !!t.textutil,
      },
      categories: CATEGORY_LABELS,
    };
  });

  handle('describe', async (_e, paths) => {
    if (!Array.isArray(paths)) return [];
    const files = await expandPaths(paths.filter((p) => typeof p === 'string' && p));
    return files.map(describe);
  });

  handle('pick-files', async () => {
    const res = await dialog.showOpenDialog(mainWindow, {
      title: 'Scegli i file da convertire',
      properties: ['openFile', 'openDirectory', 'multiSelections'],
    });
    if (res.canceled) return [];
    return (await expandPaths(res.filePaths)).map(describe);
  });

  handle('pick-folder', async () => {
    const res = await dialog.showOpenDialog(mainWindow, {
      title: 'Cartella di destinazione',
      properties: ['openDirectory', 'createDirectory'],
    });
    return res.canceled ? null : res.filePaths[0];
  });

  handle('convert', (event, { jobs, options }) => {
    if (currentRun) return { started: false, reason: 'busy' };
    const valid = (Array.isArray(jobs) ? jobs : []).filter((j) => j && typeof j.input === 'string' && typeof j.targetId === 'string');
    runQueue(valid, options || {}, event.sender).catch((err) => console.error(err));
    return { started: true };
  });

  handle('cancel', () => {
    if (currentRun) currentRun.abort();
    return true;
  });

  handle('reveal', (_e, p) => {
    if (typeof p === 'string' && fs.existsSync(p)) shell.showItemInFolder(p);
  });

  handle('open-path', (_e, p) => {
    if (typeof p === 'string' && fs.existsSync(p)) return shell.openPath(p);
    return 'File non trovato';
  });

  handle('open-libreoffice-site', () => shell.openExternal('https://www.libreoffice.org/download/download-libreoffice/'));
}

// ---------- Avvio ----------

if (!SELFTEST && !app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    registerAppProtocol();
    if (SELFTEST) {
      const { runSelfTest } = require('./core/selftest');
      const code = await runSelfTest({ chromium });
      app.exit(code);
      return;
    }
    registerIpc();
    createWindow();
    app.on('activate', () => {
      if (!mainWindow) createWindow();
    });
  });

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin' && !SELFTEST) app.quit();
  });
}
