'use strict';

// Fogli di calcolo e dati strutturati: Excel, ODS, Numbers, CSV/TSV, JSON, YAML.

const fsp = require('fs/promises');
const path = require('path');
const XLSX = require('xlsx');
const yaml = require('js-yaml');
const { ConversionError, uniquePath } = require('./tools');
const { normExt } = require('./formats');
const { readTextSmart, escapeHtml } = require('./docs');

function detectDelimiter(text) {
  const firstLines = text.split(/\r?\n/).slice(0, 5).join('\n');
  let best = ',';
  let bestCount = 0;
  for (const d of [',', ';', '\t', '|']) {
    let count = 0;
    let quoted = false;
    for (const ch of firstLines) {
      if (ch === '"') quoted = !quoted;
      else if (ch === d && !quoted) count += 1;
    }
    if (count > bestCount) {
      best = d;
      bestCount = count;
    }
  }
  return best;
}

// I CSV vengono letti come testo: i numeri "puri" diventano numeri, il resto
// (date, importi con la virgola, codici con zeri iniziali) resta com'è.
function parseDelimited(text, delimiter) {
  const wb = XLSX.read(text, { type: 'string', FS: delimiter, raw: true });
  for (const name of wb.SheetNames) {
    const ws = wb.Sheets[name];
    for (const addr of Object.keys(ws)) {
      if (addr[0] === '!') continue;
      const cell = ws[addr];
      if (cell.t === 's' && /^-?(0|[1-9]\d{0,14})(\.\d+)?$/.test(cell.v)) {
        cell.t = 'n';
        cell.v = Number(cell.v);
      }
    }
  }
  return wb;
}

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function flattenRow(row) {
  if (!isPlainObject(row)) return { valore: row };
  const out = {};
  for (const [k, v] of Object.entries(row)) {
    out[k] = v !== null && typeof v === 'object' && !(v instanceof Date) ? JSON.stringify(v) : v;
  }
  return out;
}

function rowsToSheet(rows) {
  if (rows.length && rows.every(Array.isArray)) return XLSX.utils.aoa_to_sheet(rows);
  return XLSX.utils.json_to_sheet(rows.map(flattenRow));
}

function safeSheetName(name, used) {
  let base = String(name).replace(/[\\/?*[\]:]/g, ' ').slice(0, 31) || 'Foglio';
  let candidate = base;
  let i = 2;
  while (used.has(candidate)) candidate = `${base.slice(0, 28)} ${i++}`;
  used.add(candidate);
  return candidate;
}

function dataToWorkbook(data) {
  const wb = XLSX.utils.book_new();
  const used = new Set();
  if (Array.isArray(data)) {
    XLSX.utils.book_append_sheet(wb, rowsToSheet(data), safeSheetName('Dati', used));
  } else if (isPlainObject(data) && Object.keys(data).length && Object.values(data).every(Array.isArray)) {
    for (const [name, rows] of Object.entries(data)) XLSX.utils.book_append_sheet(wb, rowsToSheet(rows), safeSheetName(name, used));
  } else {
    XLSX.utils.book_append_sheet(wb, rowsToSheet([data]), safeSheetName('Dati', used));
  }
  return wb;
}

function workbookToData(wb) {
  const sheets = wb.SheetNames.map((name) => [name, XLSX.utils.sheet_to_json(wb.Sheets[name], { defval: null, raw: true })]);
  if (sheets.length === 1) return sheets[0][1];
  return Object.fromEntries(sheets);
}

async function readInput(input) {
  const ext = normExt(path.extname(input));
  if (ext === 'json' || ext === 'yaml') {
    const text = await readTextSmart(input);
    let data;
    try {
      data = ext === 'json' ? JSON.parse(text) : yaml.load(text);
    } catch (err) {
      throw new ConversionError(`Il file ${ext.toUpperCase()} non è valido`, err.message);
    }
    return { data, wb: null };
  }
  if (ext === 'csv' || ext === 'tsv') {
    const text = await readTextSmart(input);
    return { data: null, wb: parseDelimited(text, ext === 'tsv' ? '\t' : detectDelimiter(text)) };
  }
  const buf = await fsp.readFile(input);
  try {
    return { data: null, wb: XLSX.read(buf, { type: 'buffer', cellDates: true }) };
  } catch (err) {
    throw new ConversionError('Impossibile leggere il foglio di calcolo', err.message);
  }
}

function markdownTable(ws) {
  const rows = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '', raw: false });
  if (!rows.length) return '';
  const width = Math.max(...rows.map((r) => r.length));
  const cell = (v) => String(v ?? '').replace(/\|/g, '\\|').replace(/\r?\n/g, '<br>');
  const line = (r) => `| ${Array.from({ length: width }, (_, i) => cell(r[i])).join(' | ')} |`;
  return [line(rows[0]), `|${' --- |'.repeat(width)}`, ...rows.slice(1).map(line)].join('\n');
}

const SHEET_PRINT_CSS = `
  body { font: 10pt -apple-system, "Helvetica Neue", Arial, sans-serif; color: #111; margin: 0; }
  h2 { font-size: 13pt; margin: 0 0 8px; }
  section + section { break-before: page; }
  table { border-collapse: collapse; }
  td, th { border: 1px solid #bbb; padding: 3px 6px; white-space: nowrap; }
  tr:first-child td { background: #f0f0f0; font-weight: 600; }
  tr { break-inside: avoid; }
`;

function workbookToHtml(wb, title) {
  const sections = wb.SheetNames.map((name) => {
    const table = XLSX.utils.sheet_to_html(wb.Sheets[name], { header: '', footer: '' });
    const heading = wb.SheetNames.length > 1 ? `<h2>${escapeHtml(name)}</h2>` : '';
    return `<section>${heading}${table}</section>`;
  });
  return `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><style>${SHEET_PRINT_CSS}</style></head><body>${sections.join('\n')}</body></html>`;
}

async function convertSheet(input, out, targetId, opts, ctx) {
  const title = path.basename(input, path.extname(input));
  return convertWorkbook(await readInput(input), title, out, targetId, opts, ctx);
}

// Numeri scritti all'italiana o all'inglese ("12.500", "3,14", "1,234.5") -> numero
function coerceNumber(value) {
  if (typeof value !== 'string') return value;
  const v = value.trim().replace(/^€\s*|\s*€$/g, '');
  if (/^-?\d{1,3}(\.\d{3})+(,\d+)?$/.test(v)) return Number(v.replace(/\./g, '').replace(',', '.'));
  if (/^-?\d{1,3}(,\d{3})+(\.\d+)?$/.test(v)) return Number(v.replace(/,/g, ''));
  if (/^-?\d+,\d+$/.test(v)) return Number(v.replace(',', '.'));
  if (/^-?(0|[1-9]\d{0,14})(\.\d+)?$/.test(v)) return Number(v);
  return value;
}

// Tabelle estratte da un PDF -> cartella di lavoro, una tabella per foglio
function tablesToWorkbook(tables) {
  const wb = XLSX.utils.book_new();
  const used = new Set();
  for (const table of tables) {
    const rows = table.rows.map((r, i) => (i === 0 ? r : r.map(coerceNumber)));
    const name = tables.length === 1 ? 'Tabella' : `Tabella ${table.index}${table.page ? ` (pag. ${table.page})` : ''}`;
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet(rows), safeSheetName(name, used));
  }
  return wb;
}

async function convertWorkbook(source, title, out, targetId, opts, ctx) {
  const { tmp, chromium, signal } = ctx;
  let { data, wb } = source;
  const getWb = () => (wb = wb || dataToWorkbook(data));
  const getData = () => (data !== null && data !== undefined ? data : workbookToData(getWb()));

  switch (targetId) {
    case 'json':
      await fsp.writeFile(out, `${JSON.stringify(getData(), null, 2)}\n`);
      return [out];
    case 'yaml':
      await fsp.writeFile(out, yaml.dump(getData(), { noRefs: true, lineWidth: 120 }));
      return [out];
    case 'xlsx':
    case 'ods':
      XLSX.writeFile(getWb(), out, { bookType: targetId, compression: true });
      return [out];
    case 'csv':
    case 'tsv': {
      const book = getWb();
      const outputs = [];
      const dir = path.dirname(out);
      book.SheetNames.forEach((name, i) => {
        const separator = opts.csvSeparator === ';' ? ';' : ',';
        const text = XLSX.utils.sheet_to_csv(book.Sheets[name], { FS: targetId === 'tsv' ? '\t' : separator, blankrows: false });
        const file = i === 0 ? out : uniquePath(dir, `${title} - ${name.replace(/[/:\\]/g, '-')}`, targetId);
        outputs.push({ file, text: targetId === 'csv' ? `﻿${text}` : text });
      });
      for (const o of outputs) await fsp.writeFile(o.file, o.text);
      return outputs.map((o) => o.file);
    }
    case 'html':
      await fsp.writeFile(out, workbookToHtml(getWb(), title));
      return [out];
    case 'md': {
      const book = getWb();
      const parts = book.SheetNames.map((name) => {
        const table = markdownTable(book.Sheets[name]);
        return book.SheetNames.length > 1 ? `## ${name}\n\n${table}` : table;
      });
      await fsp.writeFile(out, `${parts.join('\n\n')}\n`);
      return [out];
    }
    case 'docx':
    case 'odt': {
      const html = path.join(tmp, `${title}.html`);
      await fsp.writeFile(html, workbookToHtml(getWb(), title));
      return require('./docs').convertDocument(html, out, targetId, opts, ctx);
    }
    case 'pdf': {
      const html = path.join(tmp, 'foglio.html');
      await fsp.writeFile(html, workbookToHtml(getWb(), title));
      await chromium.htmlToPdf(html, out, { landscape: true, signal });
      return [out];
    }
    default:
      throw new ConversionError(`Formato di destinazione non supportato: ${targetId}`);
  }
}

module.exports = { convertSheet, convertWorkbook, tablesToWorkbook, coerceNumber, detectDelimiter };
