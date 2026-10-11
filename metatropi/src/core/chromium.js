'use strict';

// Funzioni che usano il Chromium integrato in Electron: stampa HTML -> PDF,
// rendering dei PDF (pdf.js) e rasterizzazione degli SVG.

const fsp = require('fs/promises');
const path = require('path');
const { BrowserWindow, ipcMain } = require('electron');
const { CancelledError, ConversionError } = require('./tools');

const SAFE_PREFS = {
  sandbox: true,
  contextIsolation: true,
  nodeIntegration: false,
  javascript: false,
  webSecurity: true,
  images: true,
  spellcheck: false,
};

function lockDown(win) {
  win.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  win.webContents.on('will-navigate', (e) => e.preventDefault());
}

async function htmlToPdf(htmlFile, out, { css, landscape = false, preferCSSPageSize = false, margins, signal } = {}) {
  if (signal && signal.aborted) throw new CancelledError();
  const win = new BrowserWindow({ show: false, width: 1000, height: 1400, webPreferences: SAFE_PREFS });
  lockDown(win);
  const onAbort = () => !win.isDestroyed() && win.destroy();
  if (signal) signal.addEventListener('abort', onAbort, { once: true });
  try {
    await win.loadFile(htmlFile);
    if (css) await win.webContents.insertCSS(css);
    const pdf = await win.webContents.printToPDF({
      printBackground: true,
      pageSize: 'A4',
      landscape,
      preferCSSPageSize,
      margins: margins || { top: 0.7, bottom: 0.7, left: 0.7, right: 0.7 },
    });
    await fsp.writeFile(out, pdf);
  } catch (err) {
    if (signal && signal.aborted) throw new CancelledError();
    throw new ConversionError('Impossibile creare il PDF', err.message);
  } finally {
    if (signal) signal.removeEventListener('abort', onAbort);
    if (!win.isDestroyed()) win.destroy();
  }
}

// --- Finestra "motore" nascosta che esegue pdf.js e la rasterizzazione SVG ---

let engineWin = null;
let engineReady = null;
let nextId = 1;
const pending = new Map();

ipcMain.on('engine:result', (event, { id, ok, result, error }) => {
  if (!engineWin || event.sender !== engineWin.webContents) return;
  const p = pending.get(id);
  if (!p) return;
  pending.delete(id);
  if (ok) p.resolve(result);
  else p.reject(new ConversionError(error || 'Errore del motore interno'));
});

function startEngine() {
  if (engineReady) return engineReady;
  engineWin = new BrowserWindow({
    show: false,
    webPreferences: {
      preload: path.join(__dirname, '..', 'engine-preload.js'),
      sandbox: true,
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });
  lockDown(engineWin);
  engineReady = new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      ipcMain.removeListener('engine:ready', onReady);
      if (engineWin && !engineWin.isDestroyed()) engineWin.destroy();
      engineReady = null;
      reject(new ConversionError('Il motore interno non risponde'));
    }, 30000);
    const onReady = (event) => {
      if (!engineWin || event.sender !== engineWin.webContents) return;
      ipcMain.removeListener('engine:ready', onReady);
      clearTimeout(timer);
      resolve();
    };
    ipcMain.on('engine:ready', onReady);
  });
  engineWin.on('closed', () => {
    engineWin = null;
    engineReady = null;
    for (const p of pending.values()) p.reject(new ConversionError('Il motore interno si è chiuso'));
    pending.clear();
  });
  engineWin.webContents.on('render-process-gone', () => {
    if (engineWin && !engineWin.isDestroyed()) engineWin.destroy();
  });
  engineWin.loadURL('app://local/engine.html');
  return engineReady;
}

async function engine(type, payload) {
  await startEngine();
  const id = nextId++;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    engineWin.webContents.send('engine:task', { id, type, payload });
  });
}

function closeEngine() {
  if (engineWin && !engineWin.isDestroyed()) engineWin.destroy();
}

module.exports = { htmlToPdf, engine, closeEngine };
