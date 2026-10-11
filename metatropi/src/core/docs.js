'use strict';

// Conversioni di documenti: pandoc per i formati di testo, textutil (macOS)
// per i vecchi .doc, LibreOffice (se installato) per la massima fedeltà
// verso PDF e per presentazioni/Pages. I PDF vengono stampati da Chromium.

const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const { pathToFileURL } = require('url');
const { tools, run, moveFile, ConversionError } = require('./tools');
const { familyOf, normExt } = require('./formats');
const py = require('./pytools');

const PANDOC_READERS = {
  md: 'markdown', html: 'html', docx: 'docx', odt: 'odt', rtf: 'rtf', epub: 'epub',
  tex: 'latex', rst: 'rst', org: 'org', ipynb: 'ipynb', textile: 'textile', typ: 'typst', fb2: 'fb2',
};

const PANDOC_WRITERS = {
  docx: 'docx', odt: 'odt', rtf: 'rtf', html: 'html5', md: 'gfm', txt: 'plain',
  epub: 'epub3', tex: 'latex', rst: 'rst', pptx: 'pptx',
};

const TEXTUTIL_IN = new Set(['doc', 'docx', 'rtf', 'html', 'odt', 'txt', 'wordml', 'webarchive']);
const TEXTUTIL_OUT = new Set(['doc', 'docx', 'rtf', 'html', 'odt', 'txt']);
const LO_PDF_FIDELITY = new Set(['doc', 'docx', 'odt', 'rtf', 'wordml', 'pages', 'pptx', 'ppt', 'odp', 'key']);

const LO_FILTERS = {
  pdf: 'pdf',
  docx: 'docx:MS Word 2007 XML',
  doc: 'doc:MS Word 97',
  odt: 'odt',
  rtf: 'rtf',
  html: 'html',
  txt: 'txt:Text (encoded):UTF8',
  pptx: 'pptx:Impress MS PowerPoint 2007 XML',
  odp: 'odp',
  xlsx: 'xlsx:Calc MS Excel 2007 XML',
  ods: 'ods',
};

const DOC_PRINT_CSS = `
  html, body { background: #fff !important; color: #111 !important; }
  body { max-width: none !important; margin: 0 !important; padding: 0 !important;
         font: 11pt/1.5 -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif !important; hyphens: auto; }
  h1, h2, h3, h4 { line-height: 1.25; page-break-after: avoid; break-after: avoid; }
  h1 { font-size: 1.9em; } h2 { font-size: 1.45em; } h3 { font-size: 1.2em; }
  img, svg, video { max-width: 100% !important; height: auto; }
  table { border-collapse: collapse; width: auto; max-width: 100%; margin: 1em 0; font-size: 0.95em; }
  th, td { border: 1px solid #c8c8c8; padding: 4px 8px; vertical-align: top; }
  th { background: #f2f2f2; }
  tr, img, pre, blockquote { break-inside: avoid; }
  pre, code { font-family: Menlo, Consolas, monospace; font-size: 0.9em; }
  pre { background: #f6f6f6; padding: 10px 12px; border-radius: 4px; white-space: pre-wrap; word-wrap: break-word; }
  blockquote { margin-left: 0; padding-left: 1em; border-left: 3px solid #ddd; color: #444; }
  header#title-block-header { margin-bottom: 2em; }
`;

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
}

async function readTextSmart(file) {
  const buf = await fsp.readFile(file);
  let text = new TextDecoder('utf-8').decode(buf);
  if (text.includes('�')) text = new TextDecoder('windows-1252').decode(buf);
  return text.replace(/^﻿/, '');
}

// Testo semplice -> HTML: paragrafi separati da righe vuote, a capo mantenuti.
async function txtToHtml(input, outHtml, title) {
  const text = await readTextSmart(input);
  const paragraphs = text
    .replace(/\r\n?/g, '\n')
    .split(/\n{2,}/)
    .map((p) => `<p>${escapeHtml(p).replace(/\n/g, '<br>\n')}</p>`)
    .join('\n');
  await fsp.writeFile(outHtml, `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title></head><body>\n${paragraphs}\n</body></html>`);
}

async function pandoc(input, reader, out, writer, { signal, cwd, title, extractMedia } = {}) {
  const bin = tools().pandoc;
  if (!bin) throw new ConversionError('pandoc non è disponibile');
  const args = ['-f', reader, '-t', writer, '--resource-path', `${path.dirname(input)}${path.delimiter}.`];
  if (['html5', 'rtf', 'latex', 'plain', 'rst', 'gfm'].includes(writer)) args.push('-s');
  if (writer === 'html5') args.push('--embed-resources', '--metadata', `pagetitle=${title}`);
  if (writer === 'epub3' || writer === 'pptx') args.push('--metadata', `title=${title}`);
  if (extractMedia) args.push(`--extract-media=${extractMedia}`);
  args.push('-o', out, input);
  await run(bin, args, { signal, cwd: cwd || path.dirname(out) });
  if (!fs.existsSync(out)) throw new ConversionError('pandoc non ha prodotto alcun file');
}

async function textutil(input, out, format, { signal } = {}) {
  const bin = tools().textutil;
  if (!bin) throw new ConversionError('textutil è disponibile solo su macOS');
  const args = ['-convert', format, '-output', out];
  if (format === 'txt' || format === 'html') args.push('-encoding', 'UTF-8');
  args.push(input);
  await run(bin, args, { signal });
  if (!fs.existsSync(out)) throw new ConversionError('textutil non ha prodotto alcun file');
}

async function libreoffice(input, out, targetId, { signal, tmp }) {
  const bin = tools().libreoffice;
  if (!bin) throw new ConversionError('LibreOffice non è installato');
  const filter = LO_FILTERS[targetId];
  if (!filter) throw new ConversionError(`LibreOffice non può creare ${targetId}`);
  const profile = path.join(tmp, 'lo-profile');
  const outdir = path.join(tmp, 'lo-out');
  await fsp.mkdir(outdir, { recursive: true });
  await run(
    bin,
    [`-env:UserInstallation=${pathToFileURL(profile).href}`, '--headless', '--norestore', '--nologo', '--nodefault', '--nolockcheck',
      '--convert-to', filter, '--outdir', outdir, input],
    { signal },
  );
  const produced = (await fsp.readdir(outdir)).filter((f) => !f.startsWith('.'));
  if (!produced.length) throw new ConversionError('LibreOffice non è riuscito a convertire il file');
  await moveFile(path.join(outdir, produced[0]), out);
}

// Converte un documento qualsiasi in HTML autonomo (immagini incorporate).
async function toHtml(input, ext, tmp, { signal, title }) {
  if (ext === 'html') return input;
  const htmlOut = path.join(tmp, 'documento.html');
  if (ext === 'txt') {
    await txtToHtml(input, htmlOut, title);
    return htmlOut;
  }
  const reader = PANDOC_READERS[ext];
  if (!reader) throw new ConversionError(`Formato di documento non supportato: ${ext}`);
  await pandoc(input, reader, htmlOut, 'html5', { signal, title, cwd: tmp });
  return htmlOut;
}

async function convertDocument(input, out, targetId, opts, ctx) {
  const { signal, tmp, chromium } = ctx;
  const t = tools();
  const rawExt = path.extname(input).slice(1).toLowerCase();
  const ext = normExt(rawExt);
  const family = familyOf(rawExt);
  const title = path.basename(input, path.extname(input));

  // PowerPoint senza LibreOffice (o verso formati di testo): si estraggono testo, tabelle e immagini
  if (family === 'slides' && !(t.libreoffice && ['pdf', 'pptx', 'odp'].includes(targetId))) {
    if (ext !== 'pptx' || !t.python) {
      throw new ConversionError('Per questo formato serve LibreOffice (gratuito): installalo da libreoffice.org');
    }
    return pptxViaMarkdown(input, out, targetId, opts, ctx, title);
  }

  const useLibreOffice =
    t.libreoffice &&
    (family === 'slides' || family === 'pages' ||
      (targetId === 'pdf' && LO_PDF_FIDELITY.has(ext)) ||
      (family === 'docLegacy' && !t.textutil) ||
      (targetId === 'doc' && !t.textutil));
  if (useLibreOffice) {
    await libreoffice(input, out, targetId, { signal, tmp });
    return [out];
  }
  if (family === 'slides' || family === 'pages') {
    throw new ConversionError('Per questo formato serve LibreOffice (gratuito): installalo da libreoffice.org');
  }

  // textutil diretto per i formati Word/RTF quando è coinvolto il vecchio .doc
  if (t.textutil && TEXTUTIL_IN.has(ext) && TEXTUTIL_OUT.has(targetId) && (family === 'docLegacy' || targetId === 'doc' || !t.pandoc)) {
    await textutil(input, out, targetId, { signal });
    return [out];
  }

  let src = input;
  let srcExt = ext;
  if (family === 'docLegacy') {
    src = path.join(tmp, `${title}.docx`);
    await textutil(input, src, 'docx', { signal });
    srcExt = 'docx';
  }

  if (targetId === 'pdf') {
    const html = await toHtml(src, srcExt, tmp, { signal, title });
    await chromium.htmlToPdf(html, out, { css: srcExt === 'html' && html === input ? null : DOC_PRINT_CSS, signal });
    return [out];
  }

  if (targetId === 'doc') {
    const docx = path.join(tmp, 'intermedio.docx');
    if (srcExt === 'txt') {
      const html = await toHtml(src, srcExt, tmp, { signal, title });
      await textutil(html, out, 'doc', { signal });
    } else {
      await pandoc(src, PANDOC_READERS[srcExt], docx, 'docx', { signal, title });
      await textutil(docx, out, 'doc', { signal });
    }
    return [out];
  }

  const writer = PANDOC_WRITERS[targetId];
  if (!writer) throw new ConversionError(`Formato di destinazione non supportato: ${targetId}`);
  let reader = PANDOC_READERS[srcExt];
  if (srcExt === 'txt') {
    src = path.join(tmp, 'testo.html');
    await txtToHtml(input, src, title);
    reader = 'html';
  }
  if (!reader) throw new ConversionError(`Formato di documento non supportato: ${srcExt}`);

  // Da Word/ODT/EPUB a formati testuali le immagini vengono salvate in una cartella accanto
  const textual = ['md', 'html', 'tex', 'rst'].includes(targetId) && ['docx', 'odt', 'epub'].includes(srcExt);
  const extractMedia = textual && targetId !== 'html' ? `${path.basename(out, path.extname(out))}-immagini` : null;
  await pandoc(src, reader, out, writer, { signal, title, extractMedia, cwd: path.dirname(out) });
  const outputs = [out];
  if (extractMedia && fs.existsSync(path.join(path.dirname(out), extractMedia))) outputs.push(path.join(path.dirname(out), extractMedia));
  return outputs;
}

async function pptxViaMarkdown(input, out, targetId, opts, ctx, title) {
  const dir = path.join(ctx.tmp, 'slide');
  const stdout = await py.python('pptx', [input, dir], ctx, 'Impossibile leggere la presentazione');
  const md = path.join(dir, `${title}.md`);
  await fsp.rename(py.lastLine(stdout), md);
  const step = { ...ctx, onProgress: null };
  if (targetId === 'md') {
    // passando da Word le immagini finiscono in una cartella accanto al file
    const docx = path.join(ctx.tmp, `${title}.docx`);
    await convertDocument(md, docx, 'docx', opts, step);
    return convertDocument(docx, out, 'md', opts, step);
  }
  return convertDocument(md, out, targetId, opts, step);
}

// Testo semplice (es. da OCR) -> qualunque formato di documento
async function fromPlainText(text, out, targetId, title, opts, ctx) {
  const clean = String(text).replace(/\r\n?/g, '\n').replace(/\n?\f\n?/g, '\n\n').trim();
  if (!clean) throw new ConversionError('Non è stato trovato alcun testo');
  if (targetId === 'txt') {
    await fsp.writeFile(out, `${clean}\n`);
    return [out];
  }
  const txt = path.join(ctx.tmp, `${title}.txt`);
  await fsp.writeFile(txt, clean);
  return convertDocument(txt, out, targetId, opts, ctx);
}

module.exports = { convertDocument, fromPlainText, libreoffice, readTextSmart, escapeHtml, DOC_PRINT_CSS };
