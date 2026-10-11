// Pagina nascosta che esegue pdf.js e la rasterizzazione degli SVG.
import * as pdfjsLib from './vendor/pdfjs/build/pdf.mjs';

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdfjs/build/pdf.worker.mjs', import.meta.url).href;
const PDFJS_BASE = new URL('./vendor/pdfjs/', import.meta.url).href;

const docs = new Map();
let nextDocId = 1;

function getDoc(docId) {
  const doc = docs.get(docId);
  if (!doc) throw new Error('Documento PDF non aperto');
  return doc;
}

function canvasToBytes(canvas, mime, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(async (blob) => {
      if (!blob) return reject(new Error('Impossibile generare l’immagine'));
      resolve(new Uint8Array(await blob.arrayBuffer()));
    }, mime, quality);
  });
}

const UNITS = { '': 1, px: 1, pt: 4 / 3, pc: 16, mm: 96 / 25.4, cm: 96 / 2.54, in: 96, em: 16 };

// Converte una lunghezza SVG ("10cm", "200", "50%") in pixel; 0 se non utilizzabile.
function svgLength(value) {
  const m = String(value || '').trim().match(/^([\d.]+)\s*([a-z]*)$/i);
  if (!m) return 0;
  const unit = UNITS[m[2].toLowerCase()];
  return unit ? parseFloat(m[1]) * unit : 0;
}

const handlers = {
  async 'pdf-open'({ data }) {
    const doc = await pdfjsLib.getDocument({
      data,
      cMapUrl: `${PDFJS_BASE}cmaps/`,
      cMapPacked: true,
      standardFontDataUrl: `${PDFJS_BASE}standard_fonts/`,
      wasmUrl: `${PDFJS_BASE}wasm/`,
      iccUrl: `${PDFJS_BASE}iccs/`,
      isEvalSupported: false,
    }).promise;
    const docId = nextDocId++;
    docs.set(docId, doc);
    return { docId, numPages: doc.numPages };
  },

  async 'pdf-text'({ docId, page }) {
    const p = await getDoc(docId).getPage(page);
    const content = await p.getTextContent();
    let text = '';
    for (const item of content.items) {
      if (typeof item.str !== 'string') continue;
      text += item.str;
      if (item.hasEOL) text += '\n';
    }
    p.cleanup();
    return { text: text.replace(/[ \t]+\n/g, '\n').trimEnd() };
  },

  async 'pdf-render'({ docId, page, scale, mime, quality }) {
    const p = await getDoc(docId).getPage(page);
    // Evita canvas giganteschi su pagine molto grandi
    const base = p.getViewport({ scale: 1 });
    const maxSide = 12000;
    const s = Math.min(scale, maxSide / Math.max(base.width, base.height));
    const viewport = p.getViewport({ scale: s });
    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil(viewport.width);
    canvas.height = Math.ceil(viewport.height);
    await p.render({ canvas, viewport, background: '#ffffff' }).promise;
    const bytes = await canvasToBytes(canvas, mime, quality);
    canvas.width = 0;
    canvas.height = 0;
    p.cleanup();
    return bytes;
  },

  async 'pdf-close'({ docId }) {
    const doc = docs.get(docId);
    docs.delete(docId);
    if (doc) await doc.destroy();
    return true;
  },

  async 'svg-raster'({ svg, maxSize }) {
    const doc = new DOMParser().parseFromString(svg, 'image/svg+xml');
    const root = doc.documentElement;
    if (!root || root.nodeName.toLowerCase() !== 'svg') throw new Error('Il file SVG non è valido');
    let w = svgLength(root.getAttribute('width'));
    let h = svgLength(root.getAttribute('height'));
    const vb = (root.getAttribute('viewBox') || '').trim().split(/[\s,]+/).map(Number);
    const hasViewBox = vb.length === 4 && vb[2] > 0 && vb[3] > 0;
    if ((!w || !h) && hasViewBox) {
      w = vb[2];
      h = vb[3];
    }
    if (!w || !h) {
      // Dimensioni predefinite di un SVG senza width/height né viewBox
      w = 300;
      h = 150;
    }
    // Senza viewBox le coordinate interne sono in pixel: lo fissiamo prima di ridimensionare
    if (!hasViewBox) root.setAttribute('viewBox', `0 0 ${w} ${h}`);
    const longest = maxSize || Math.max(w, h, 1024);
    const k = longest / Math.max(w, h);
    const width = Math.max(1, Math.round(w * k));
    const height = Math.max(1, Math.round(h * k));
    root.setAttribute('width', String(width));
    root.setAttribute('height', String(height));
    const blob = new Blob([new XMLSerializer().serializeToString(root)], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(blob);
    try {
      const img = new Image();
      img.src = url;
      await img.decode();
      const canvas = document.createElement('canvas');
      canvas.width = width;
      canvas.height = height;
      canvas.getContext('2d').drawImage(img, 0, 0, width, height);
      return await canvasToBytes(canvas, 'image/png');
    } finally {
      URL.revokeObjectURL(url);
    }
  },
};

window.engineBridge.onTask(async ({ id, type, payload }) => {
  try {
    const handler = handlers[type];
    if (!handler) throw new Error(`Operazione sconosciuta: ${type}`);
    const result = await handler(payload);
    window.engineBridge.reply({ id, ok: true, result });
  } catch (err) {
    window.engineBridge.reply({ id, ok: false, error: err && err.message ? err.message : String(err) });
  }
});

window.engineBridge.ready();
