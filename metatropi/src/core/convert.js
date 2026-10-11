'use strict';

// Punto d'ingresso delle conversioni: sceglie il motore giusto per ogni coppia
// formato di partenza -> formato di arrivo.

const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const { TARGETS, familyOf, normExt, targetIdsFor } = require('./formats');
const { env, tools, run, makeTempDir, removeDir, ConversionError } = require('./tools');
const media = require('./media');
const docs = require('./docs');
const sheets = require('./sheets');
const py = require('./pytools');

// Percorsi di uscita già assegnati a conversioni in corso (evita collisioni in parallelo)
const reserved = new Set();

function reserveOutput(dir, base, ext) {
  let i = 0;
  for (;;) {
    const name = i === 0 ? base : `${base} (${i})`;
    const candidate = path.join(dir, ext ? `${name}.${ext}` : name);
    if (!reserved.has(candidate) && !fs.existsSync(candidate)) {
      reserved.add(candidate);
      return candidate;
    }
    i += 1;
  }
}

// Formati che `sips` legge direttamente
const SIPS_READABLE = new Set(['jpg', 'png', 'tiff', 'bmp', 'gif', 'heic', 'heif', 'psd', 'dng', 'cr2', 'cr3', 'nef', 'arw', 'raf', 'orf', 'rw2', 'srw', 'pef']);
// Formati che Chromium mostra direttamente in una pagina
const BROWSER_IMAGES = { jpg: 'image/jpeg', png: 'image/png', webp: 'image/webp', gif: 'image/gif', bmp: 'image/bmp', avif: 'image/avif', svg: 'image/svg+xml', ico: 'image/x-icon' };

// Proporzioni di un SVG dagli attributi width/height o dal viewBox
function svgSize(svg) {
  const tag = (svg.match(/<svg\b[^>]*>/i) || [''])[0];
  const attr = (name) => {
    const m = tag.match(new RegExp(`\\s${name}\\s*=\\s*["']([^"']*)["']`, 'i'));
    return m ? m[1] : '';
  };
  const vb = attr('viewBox').trim().split(/[\s,]+/).map(Number);
  let width = /%/.test(attr('width')) ? 0 : parseFloat(attr('width')) || 0;
  let height = /%/.test(attr('height')) ? 0 : parseFloat(attr('height')) || 0;
  if ((!width || !height) && vb.length === 4) [, , width, height] = vb;
  return { width: width || 0, height: height || 0 };
}

async function rasterizeSvg(input, tmp, opts, chromium) {
  const svg = await fsp.readFile(input, 'utf8');
  const png = await chromium.engine('svg-raster', { svg, maxSize: Number(opts.maxSize) || 0 });
  const file = path.join(tmp, `svg-${Date.now()}.png`);
  await fsp.writeFile(file, Buffer.from(png));
  return file;
}

// Porta un'immagine qualsiasi in un formato leggibile da ffmpeg/Chromium.
async function decodableImage(input, tmp, opts, ctx) {
  const ext = normExt(path.extname(input));
  const family = familyOf(path.extname(input).slice(1));
  if (family === 'imageMac') {
    const png = path.join(tmp, `decoded-${Date.now()}.png`);
    await media.sips(input, png, 'png', { signal: ctx.signal });
    return png;
  }
  if (ext === 'svg') return rasterizeSvg(input, tmp, opts, ctx.chromium);
  return input;
}

async function convertImage(input, out, targetId, opts, ctx) {
  const ext = normExt(path.extname(input));
  const { tmp, signal } = ctx;

  if (targetId === 'pdf') {
    await imagesToPdf([input], out, opts, ctx);
    return [out];
  }
  if (targetId === 'txt' || targetId === 'docx') {
    const text = await py.ocr(input, ctx);
    return docs.fromPlainText(text, out, targetId, path.basename(input, path.extname(input)), opts, ctx);
  }
  if (targetId === 'mp4' || targetId === 'webm') {
    await media.convertVideo(input, out, targetId, opts, ctx);
    return [out];
  }
  if (targetId === 'heic') {
    let src = input;
    if (!SIPS_READABLE.has(ext)) {
      const decoded = await decodableImage(input, tmp, opts, ctx);
      src = path.join(tmp, `heic-src-${Date.now()}.png`);
      await media.ffmpegImage(decoded, src, 'png', {}, { signal });
    }
    await media.sips(src, out, 'heic', { quality: Number(opts.imageQuality) || 85, maxSize: Number(opts.maxSize) || 0, signal });
    return [out];
  }
  const src = await decodableImage(input, tmp, opts, ctx);
  const animated = ext === 'gif' && (targetId === 'gif' || targetId === 'webp');
  await media.ffmpegImage(src, out, targetId, opts, { signal, animated });
  return [out];
}

// Una o più immagini -> un PDF, una pagina A4 per immagine (orientata come l'immagine).
async function imagesToPdf(inputs, out, opts, ctx) {
  const { tmp, chromium, signal } = ctx;
  const pages = [];
  for (const input of inputs) {
    const ext = normExt(path.extname(input));
    let file = input;
    let mime = BROWSER_IMAGES[ext];
    if (!mime) {
      const decoded = await decodableImage(input, tmp, opts, ctx);
      file = path.join(tmp, `page-${pages.length}.png`);
      await media.ffmpegImage(decoded, file, 'png', {}, { signal });
      mime = 'image/png';
    }
    let landscape = false;
    if (ext === 'svg') {
      const { width, height } = svgSize(await fsp.readFile(file, 'utf8'));
      landscape = width > height;
    } else {
      const info = await media.probe(file, signal);
      landscape = info.width > info.height;
    }
    const data = (await fsp.readFile(file)).toString('base64');
    pages.push(`<div class="p ${landscape ? 'land' : 'port'}"><img src="data:${mime};base64,${data}"></div>`);
  }
  const html = `<!doctype html><html><head><meta charset="utf-8"><style>
    @page port { size: A4 portrait; margin: 0; }
    @page land { size: A4 landscape; margin: 0; }
    html, body { margin: 0; padding: 0; background: #fff; }
    .p { box-sizing: border-box; padding: 8mm; display: flex; align-items: center; justify-content: center; overflow: hidden; break-after: page; }
    .p:last-child { break-after: auto; }
    .port { page: port; width: 210mm; height: 296.6mm; }
    .land { page: land; width: 297mm; height: 209.6mm; }
    img { max-width: 100%; max-height: 100%; object-fit: contain; }
  </style></head><body>${pages.join('')}</body></html>`;
  const htmlFile = path.join(tmp, 'immagini.html');
  await fsp.writeFile(htmlFile, html);
  await chromium.htmlToPdf(htmlFile, out, { preferCSSPageSize: true, margins: { top: 0, bottom: 0, left: 0, right: 0 }, signal });
}

// Avanzamento di una fase all'interno di un intervallo (es. 0..0.8)
function phase(ctx, from, to) {
  return { ...ctx, root: ctx.root || ctx, onProgress: ctx.onProgress ? (p) => ctx.onProgress(from + (to - from) * p) : null };
}

// PDF -> Word: pdf2docx per i PDF con testo, OCR per le scansioni
async function pdfToDocx(input, out, opts, ctx) {
  const title = path.basename(input, path.extname(input));
  if (tools().ocr && (await py.isScannedPdf(input, ctx))) {
    const text = await py.ocr(input, phase(ctx, 0, 0.9));
    await docs.fromPlainText(text, out, 'docx', title, opts, { ...ctx, onProgress: null });
    return;
  }
  await py.python('docx', [input, out], ctx, 'Impossibile convertire il PDF in Word');
}

const VIA_DOCX = new Set(['odt', 'rtf', 'html', 'md', 'epub', 'doc']);

async function convertPdf(input, out, targetId, opts, ctx) {
  const title = path.basename(input, path.extname(input));
  if (targetId === 'docx') {
    await pdfToDocx(input, out, opts, ctx);
    return [out];
  }
  if (VIA_DOCX.has(targetId)) {
    const docx = path.join(ctx.tmp, `${title}.docx`);
    await pdfToDocx(input, docx, opts, phase(ctx, 0, 0.85));
    return docs.convertDocument(docx, out, targetId, opts, { ...ctx, onProgress: null });
  }
  if (['xlsx', 'ods', 'csv'].includes(targetId)) {
    const json = path.join(ctx.tmp, 'tabelle.json');
    await py.python('tables', [input, json], ctx, 'Impossibile leggere le tabelle del PDF');
    const tables = JSON.parse(await fsp.readFile(json, 'utf8'));
    if (!tables.length) throw new ConversionError('Nel PDF non sono state trovate tabelle');
    return sheets.convertWorkbook({ data: null, wb: sheets.tablesToWorkbook(tables) }, title, out, targetId, opts, ctx);
  }
  if (targetId === 'pptx') return pdfToSlides(input, out, opts, ctx);
  if (targetId === 'txt' && tools().ocr && (await py.isScannedPdf(input, ctx))) {
    return docs.fromPlainText(await py.ocr(input, ctx), out, 'txt', title, opts, ctx);
  }
  return renderPdf(input, out, targetId, opts, ctx);
}

// Ogni pagina diventa una slide (come immagine)
async function pdfToSlides(input, out, opts, ctx) {
  const { chromium, tmp, signal } = ctx;
  const data = await fsp.readFile(input);
  const { docId, numPages } = await chromium.engine('pdf-open', { data });
  const dir = path.join(tmp, 'slide');
  await fsp.mkdir(dir, { recursive: true });
  const parts = [];
  try {
    for (let p = 1; p <= numPages; p++) {
      throwIfAborted(signal);
      const bytes = await chromium.engine('pdf-render', { docId, page: p, scale: 2, mime: 'image/png' });
      await fsp.writeFile(path.join(dir, `pagina-${p}.png`), Buffer.from(bytes));
      parts.push(`![](pagina-${p}.png)`);
      if (ctx.onProgress) ctx.onProgress((p / numPages) * 0.9);
    }
  } finally {
    chromium.engine('pdf-close', { docId }).catch(() => {});
  }
  const md = path.join(dir, 'slide.md');
  await fsp.writeFile(md, `${parts.join('\n\n---\n\n')}\n`);
  await run(tools().pandoc, ['-f', 'markdown', '-t', 'pptx', '--resource-path', dir, '-o', out, md], { signal, cwd: dir });
  return [out];
}

async function renderPdf(input, out, targetId, opts, ctx) {
  const { chromium, onProgress } = ctx;
  const data = await fsp.readFile(input);
  const { docId, numPages } = await chromium.engine('pdf-open', { data });
  try {
    if (targetId === 'txt') {
      const parts = [];
      for (let p = 1; p <= numPages; p++) {
        throwIfAborted(ctx.signal);
        const { text } = await chromium.engine('pdf-text', { docId, page: p });
        parts.push(text);
        if (onProgress) onProgress(p / numPages);
      }
      await fsp.writeFile(out, parts.join('\n\n\f'));
      return [out];
    }
    const dpi = Number(opts.pdfDpi) || 150;
    const ext = TARGETS[targetId].ext;
    let files;
    if (numPages === 1) files = [out];
    else {
      reserved.delete(out);
      const dir = reserveOutput(path.dirname(out), `${path.basename(out, `.${ext}`)} - pagine`, '');
      await fsp.mkdir(dir);
      const digits = String(numPages).length;
      files = Array.from({ length: numPages }, (_, i) => path.join(dir, `pagina-${String(i + 1).padStart(digits, '0')}.${ext}`));
      (ctx.root || ctx).createdDir = dir;
    }
    for (let p = 1; p <= numPages; p++) {
      throwIfAborted(ctx.signal);
      const bytes = await chromium.engine('pdf-render', {
        docId, page: p, scale: dpi / 72, mime: targetId === 'jpg' ? 'image/jpeg' : 'image/png', quality: (Number(opts.imageQuality) || 85) / 100,
      });
      await fsp.writeFile(files[p - 1], Buffer.from(bytes));
      if (onProgress) onProgress(p / numPages);
    }
    return numPages === 1 ? files : [path.dirname(files[0])];
  } finally {
    chromium.engine('pdf-close', { docId }).catch(() => {});
  }
}

function throwIfAborted(signal) {
  if (signal && signal.aborted) {
    const err = new Error('Conversione annullata');
    err.cancelled = true;
    throw err;
  }
}

async function route(input, out, targetId, opts, ctx) {
  const rawExt = path.extname(input).slice(1).toLowerCase();
  const family = familyOf(rawExt);
  switch (family) {
    case 'image':
    case 'imageMac':
    case 'svg':
    case 'gif':
      return convertImage(input, out, targetId, opts, ctx);
    case 'audio':
      await media.convertAudio(input, out, targetId, opts, ctx);
      return [out];
    case 'video':
      if (TARGETS[targetId].group === 'audio') await media.convertAudio(input, out, targetId, opts, ctx);
      else await media.convertVideo(input, out, targetId, opts, ctx);
      return [out];
    case 'doc':
    case 'docLegacy':
    case 'pages':
    case 'slides':
      if (targetId === 'png' || targetId === 'jpg') {
        // prima in PDF, poi un'immagine per pagina
        const pdf = path.join(ctx.tmp, `${path.basename(input, path.extname(input))}.pdf`);
        await docs.convertDocument(input, pdf, 'pdf', opts, phase(ctx, 0, 0.5));
        return renderPdf(pdf, out, targetId, opts, phase(ctx, 0.5, 1));
      }
      return docs.convertDocument(input, out, targetId, opts, ctx);
    case 'sheet':
    case 'data':
      if (targetId === 'pdf' && tools().libreoffice && ['xlsx', 'xlsm', 'xls', 'ods'].includes(rawExt)) {
        await docs.libreoffice(input, out, 'pdf', ctx);
        return [out];
      }
      return sheets.convertSheet(input, out, targetId, opts, ctx);
    case 'pdf':
      return convertPdf(input, out, targetId, opts, ctx);
    case 'subtitle':
      await media.convertSubtitle(input, out, ctx);
      return [out];
    default:
      throw new ConversionError(`Formato non supportato: .${rawExt}`);
  }
}

// job = { input, targetId, outDir?, options }
// ctx = { signal, onProgress, chromium }
async function convertFile(job, ctx) {
  const { input, targetId } = job;
  const opts = job.options || {};
  const rawExt = path.extname(input).slice(1).toLowerCase();
  if (!fs.existsSync(input)) throw new ConversionError('Il file non esiste più');
  if (!targetIdsFor(rawExt, env()).includes(targetId)) {
    throw new ConversionError(`Non è possibile convertire .${rawExt} in ${TARGETS[targetId] ? TARGETS[targetId].label : targetId}`);
  }
  const outDir = job.outDir || path.dirname(input);
  await fsp.mkdir(outDir, { recursive: true });
  const base = path.basename(input, path.extname(input));
  const out = reserveOutput(outDir, base, TARGETS[targetId].ext);
  const tmp = await makeTempDir();
  const local = { ...ctx, tmp };
  try {
    const outputs = await route(input, out, targetId, opts, local);
    for (const o of outputs) if (!fs.existsSync(o)) throw new ConversionError('La conversione non ha prodotto alcun file');
    return { outputs };
  } catch (err) {
    await fsp.rm(out, { force: true }).catch(() => {});
    if (local.createdDir) await removeDir(local.createdDir);
    throw err;
  } finally {
    reserved.delete(out);
    if (local.createdDir) reserved.delete(local.createdDir);
    await removeDir(tmp);
  }
}

// Unisce più immagini in un unico PDF.
async function mergeImagesToPdf(inputs, outDir, opts, ctx) {
  const dir = outDir || path.dirname(inputs[0]);
  const base = inputs.length > 1 ? `${path.basename(inputs[0], path.extname(inputs[0]))} e altre ${inputs.length - 1}` : path.basename(inputs[0], path.extname(inputs[0]));
  const out = reserveOutput(dir, base, 'pdf');
  const tmp = await makeTempDir();
  try {
    await imagesToPdf(inputs, out, opts, { ...ctx, tmp });
    return { outputs: [out] };
  } catch (err) {
    await fsp.rm(out, { force: true }).catch(() => {});
    throw err;
  } finally {
    reserved.delete(out);
    await removeDir(tmp);
  }
}

module.exports = { convertFile, mergeImagesToPdf };
