'use strict';

// Autodiagnosi: `Convertitutto --selftest` genera file di prova e li converte
// in tutti i formati principali, stampando un resoconto. Usato dalla CI.

const fs = require('fs');
const fsp = require('fs/promises');
const os = require('os');
const path = require('path');
const { tools, env, run } = require('./tools');
const { targetIdsFor } = require('./formats');
const { convertFile, mergeImagesToPdf } = require('./convert');

const MD = `# Rapporto Convertitutto

Questo è un documento di **prova** con *accenti*: àèìòù.

- primo punto
- secondo punto

| Colonna | Valore |
|---------|--------|
| uno     | 1      |
| due     | 2      |
`;

const CSV = 'nome;città;importo;codice\nMario;Milano;12.5;007\nGiulia;Roma;3;010\n';
const JSON_DATA = JSON.stringify([{ nome: 'Mario', età: 40, tags: ['a', 'b'] }, { nome: 'Giulia', età: 35 }]);
const SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60"><rect width="100" height="60" fill="#2b6cb0"/><circle cx="50" cy="30" r="20" fill="#fff"/></svg>';
const SRT = '1\n00:00:00,000 --> 00:00:01,500\nCiao mondo\n\n2\n00:00:02,000 --> 00:00:03,000\nSeconda riga\n';
const HTML = '<!doctype html><html><head><meta charset="utf-8"><title>Pagina</title></head><body><h1>Titolo</h1><p>Paragrafo di prova.</p></body></html>';

async function makeFixtures(dir) {
  const ff = tools().ffmpeg;
  const lavfi = async (args, out) => run(ff, ['-hide_banner', '-nostdin', '-y', ...args, path.join(dir, out)]);
  await lavfi(['-f', 'lavfi', '-i', 'testsrc2=s=320x240:d=1', '-frames:v', '1'], 'immagine.png');
  await lavfi(['-f', 'lavfi', '-i', 'color=c=red@0.5:s=200x120,format=rgba', '-frames:v', '1'], 'trasparente.png');
  await lavfi(['-f', 'lavfi', '-i', 'sine=frequency=440:duration=2'], 'suono.wav');
  await lavfi(['-f', 'lavfi', '-i', 'testsrc2=s=320x240:d=2:r=25', '-f', 'lavfi', '-i', 'sine=d=2', '-shortest', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac'], 'video.mp4');
  await lavfi(['-f', 'lavfi', '-i', 'testsrc2=s=160x120:d=1:r=10'], 'animata.gif');
  await fsp.writeFile(path.join(dir, 'documento.md'), MD);
  await fsp.writeFile(path.join(dir, 'note.txt'), 'Prima riga\nseconda riga\n\nNuovo paragrafo con è.');
  await fsp.writeFile(path.join(dir, 'pagina.html'), HTML);
  await fsp.writeFile(path.join(dir, 'tabella.csv'), CSV);
  await fsp.writeFile(path.join(dir, 'dati.json'), JSON_DATA);
  await fsp.writeFile(path.join(dir, 'disegno.svg'), SVG);
  await fsp.writeFile(path.join(dir, 'sottotitoli.srt'), SRT);
}

const MAGIC = {
  pdf: '%PDF',
  png: '\x89PNG',
  jpg: '\xff\xd8\xff',
  gif: 'GIF8',
  docx: 'PK',
  xlsx: 'PK',
  ods: 'PK',
  odt: 'PK',
  epub: 'PK',
  pptx: 'PK',
};

async function checkOutput(file, targetId) {
  const st = await fsp.stat(file);
  if (st.isDirectory()) {
    const entries = await fsp.readdir(file);
    if (!entries.length) throw new Error('cartella vuota');
    return `${entries.length} file`;
  }
  if (st.size === 0) throw new Error('file vuoto');
  const magic = MAGIC[targetId];
  if (magic) {
    const fd = await fsp.open(file, 'r');
    const buf = Buffer.alloc(magic.length);
    await fd.read(buf, 0, magic.length, 0);
    await fd.close();
    if (buf.toString('latin1') !== magic) throw new Error(`intestazione inattesa per ${targetId}`);
  }
  return `${st.size} byte`;
}

async function runSelfTest({ chromium }) {
  const t = tools();
  const e = env();
  console.log('Convertitutto self-test');
  console.log('Motori:', JSON.stringify(Object.fromEntries(Object.entries(t).map(([k, v]) => [k, v || null])), null, 2));
  if (!t.ffmpeg) {
    console.error('ffmpeg non trovato: impossibile proseguire');
    return 1;
  }
  const dir = await fsp.mkdtemp(path.join(os.tmpdir(), 'convertitutto-selftest-'));
  const outDir = path.join(dir, 'out');
  await fsp.mkdir(outDir);
  await makeFixtures(dir);
  const ctx = { chromium, signal: new AbortController().signal, onProgress: () => {} };
  const results = [];

  // Su GitHub Actions la build Intel gira tradotta da Rosetta in una macchina virtuale,
  // dove la decodifica HEIC di sips non è disponibile: lì quei casi vengono segnalati ma non bloccano.
  const translated = process.platform === 'darwin' && process.arch === 'x64' && os.cpus().some((c) => /Apple/.test(c.model));

  async function attempt(input, targetId, { soft = false } = {}) {
    const label = `${path.basename(input)} -> ${targetId}`;
    const started = Date.now();
    try {
      const { outputs } = await convertFile({ input, targetId, outDir, options: { imageQuality: 80, audioBitrate: 128, videoQuality: 'small' } }, ctx);
      const info = await checkOutput(outputs[0], targetId);
      results.push({ label, ok: true, info, ms: Date.now() - started });
      return outputs[0];
    } catch (err) {
      if (soft) {
        results.push({ label, ok: true, skipped: true, info: `saltato: ${err.message}`, ms: Date.now() - started });
        return null;
      }
      results.push({ label, ok: false, info: `${err.message}${err.details ? `\n      ${err.details.split('\n').slice(-4).join('\n      ')}` : ''}`, ms: Date.now() - started });
      return null;
    }
  }

  const f = (name) => path.join(dir, name);
  const all = async (input, skip = []) => {
    const ext = path.extname(input).slice(1);
    for (const id of targetIdsFor(ext, e)) if (!skip.includes(id)) await attempt(input, id);
  };

  await all(f('immagine.png'));
  await attempt(f('trasparente.png'), 'jpg');
  await all(f('animata.gif'));
  await all(f('disegno.svg'));
  await all(f('suono.wav'));
  await all(f('video.mp4'));
  await all(f('sottotitoli.srt'));
  await all(f('documento.md'));
  await all(f('note.txt'));
  await attempt(f('pagina.html'), 'pdf');
  await attempt(f('pagina.html'), 'docx');
  await all(f('tabella.csv'));
  await all(f('dati.json'));

  // Conversioni a catena sui file appena prodotti
  const docx = await attempt(f('documento.md'), 'docx');
  if (docx) for (const id of ['pdf', 'odt', 'md', 'txt', 'html']) await attempt(docx, id);
  const pdf = await attempt(f('documento.md'), 'pdf');
  if (pdf) {
    for (const id of ['png', 'jpg']) await attempt(pdf, id);
    const pdfText = await attempt(pdf, 'txt');
    if (pdfText) {
      const content = fs.readFileSync(pdfText, 'utf8');
      results.push({ label: 'testo estratto dal PDF', ok: content.includes('Rapporto Convertitutto'), info: JSON.stringify(content.slice(0, 60)) });
    }
  }
  const xlsx = await attempt(f('tabella.csv'), 'xlsx');
  if (xlsx) for (const id of targetIdsFor('xlsx', e)) await attempt(xlsx, id);
  const yaml = await attempt(f('dati.json'), 'yaml');
  if (yaml) await all(yaml);
  if (e.mac) {
    const heic = await attempt(f('immagine.png'), 'heic');
    if (heic) for (const id of ['jpg', 'png', 'webp', 'pdf']) await attempt(heic, id, { soft: translated });
    const doc = await attempt(f('documento.md'), 'doc');
    if (doc) for (const id of ['docx', 'pdf', 'md', 'txt']) await attempt(doc, id);
  }
  if (e.libreoffice && docx) {
    const pptx = await attempt(f('documento.md'), 'pptx');
    if (pptx) await all(pptx);
  }

  // Unione di immagini in un PDF
  try {
    const { outputs } = await mergeImagesToPdf([f('immagine.png'), f('disegno.svg'), f('animata.gif')], outDir, {}, ctx);
    results.push({ label: '3 immagini -> PDF unico', ok: true, info: await checkOutput(outputs[0], 'pdf') });
  } catch (err) {
    results.push({ label: '3 immagini -> PDF unico', ok: false, info: err.message });
  }

  const failed = results.filter((r) => !r.ok);
  if (translated) console.log('Nota: app Intel eseguita tramite Rosetta; la lettura HEIC può non essere disponibile.');
  for (const r of results) console.log(`${r.skipped ? 'SKIP' : r.ok ? 'OK  ' : 'FAIL'} ${r.label}  (${r.info}${r.ms != null ? `, ${r.ms} ms` : ''})`);
  const skipped = results.filter((r) => r.skipped).length;
  console.log(`\n${results.length - failed.length - skipped}/${results.length} conversioni riuscite${skipped ? `, ${skipped} saltate` : ''}`);
  if (process.env.SELFTEST_KEEP) console.log(`File di prova in ${dir}`);
  else await fsp.rm(dir, { recursive: true, force: true });
  return failed.length ? 1 : 0;
}

module.exports = { runSelfTest };
