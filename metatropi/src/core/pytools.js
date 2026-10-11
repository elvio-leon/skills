'use strict';

// Ponte verso gli strumenti esterni "intelligenti": lo script Python
// (pdf2docx, PyMuPDF, lettura delle slide) e l'OCR di macOS.

const { tools, pythonScript, run, ConversionError } = require('./tools');

// Converte le righe "PROGRESS fatto totale" su stderr in avanzamento 0..1
function progressReader(onProgress) {
  let buffer = '';
  return (chunk) => {
    if (!onProgress) return;
    buffer += chunk;
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      const m = line.match(/^PROGRESS (\d+) (\d+)/);
      if (m && Number(m[2]) > 0) onProgress(Math.min(0.99, Number(m[1]) / Number(m[2])));
    }
  };
}

function cleanDetails(details) {
  return String(details || '')
    .split('\n')
    .filter((l) => !l.startsWith('PROGRESS') && !/fitz` API is deprecated|pymupdf_layout/.test(l))
    .join('\n');
}

async function python(command, args, { signal, onProgress } = {}, failure = 'Conversione non riuscita') {
  const bin = tools().python;
  if (!bin) throw new ConversionError('Il motore per i PDF non è disponibile');
  try {
    const { stdout } = await run(bin, ['-I', '-B', pythonScript(), command, ...args], {
      signal,
      onStderr: progressReader(onProgress),
      env: { PYTHONIOENCODING: 'utf-8' },
    });
    return stdout;
  } catch (err) {
    if (err.cancelled) throw err;
    throw new ConversionError(failure, cleanDetails(err.details));
  }
}

function lastLine(stdout) {
  const lines = String(stdout).trim().split('\n');
  return lines[lines.length - 1] || '';
}

async function pdfInfo(input, ctx) {
  return JSON.parse(lastLine(await python('info', [input], { signal: ctx.signal }, 'Impossibile leggere il PDF')));
}

// Un PDF senza testo (o quasi) è una scansione: serve l'OCR
async function isScannedPdf(input, ctx) {
  if (!tools().python) return false;
  const info = await pdfInfo(input, ctx);
  return info.pages > 0 && info.chars < 25 * info.pages;
}

async function ocr(input, { signal, onProgress } = {}) {
  const bin = tools().ocr;
  if (!bin) throw new ConversionError('Il riconoscimento del testo (OCR) è disponibile solo su macOS');
  try {
    const { stdout } = await run(bin, [input], { signal, onStderr: progressReader(onProgress) });
    return stdout;
  } catch (err) {
    if (err.cancelled) throw err;
    throw new ConversionError('Riconoscimento del testo non riuscito', cleanDetails(err.details));
  }
}

module.exports = { python, pdfInfo, isScannedPdf, ocr, lastLine };
