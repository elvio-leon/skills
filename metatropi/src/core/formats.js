'use strict';

// Catalogo dei formati: per ogni estensione in ingresso stabilisce la "famiglia"
// (che decide quale motore la elabora) e quali formati di uscita sono possibili
// in base ai motori disponibili sul computer.

const RAW_EXT = ['dng', 'cr2', 'cr3', 'nef', 'arw', 'raf', 'orf', 'rw2', 'srw', 'pef'];

const FAMILIES = {
  image: ['jpg', 'jpeg', 'png', 'webp', 'bmp', 'tif', 'tiff', 'avif', 'ico', 'tga', 'jp2'],
  gif: ['gif'],
  // Formati letti solo tramite `sips` (ImageIO di macOS)
  imageMac: ['heic', 'heif', 'psd', ...RAW_EXT],
  svg: ['svg'],
  audio: ['mp3', 'wav', 'aac', 'm4a', 'flac', 'ogg', 'oga', 'opus', 'aiff', 'aif', 'wma', 'amr', 'caf', 'ac3', 'mka'],
  video: ['mp4', 'mov', 'mkv', 'webm', 'avi', 'm4v', 'wmv', 'flv', 'mpeg', 'mpg', '3gp', 'ts', 'mts', 'm2ts', 'ogv'],
  doc: ['md', 'markdown', 'txt', 'html', 'htm', 'docx', 'odt', 'rtf', 'epub', 'tex', 'rst', 'org', 'ipynb', 'textile', 'typ', 'fb2'],
  // Formati letti solo tramite `textutil` (macOS) o LibreOffice
  docLegacy: ['doc', 'wordml', 'webarchive'],
  slides: ['pptx', 'ppt', 'odp', 'key'],
  pages: ['pages'],
  sheet: ['xlsx', 'xlsm', 'xlsb', 'xls', 'ods', 'csv', 'tsv', 'numbers'],
  data: ['json', 'yaml', 'yml'],
  pdf: ['pdf'],
  subtitle: ['srt', 'vtt', 'ass', 'ssa'],
};

const EXT_TO_FAMILY = {};
for (const [family, exts] of Object.entries(FAMILIES)) {
  for (const ext of exts) EXT_TO_FAMILY[ext] = family;
}

const CATEGORY_OF_FAMILY = {
  image: 'image', gif: 'image', imageMac: 'image', svg: 'image',
  audio: 'audio', video: 'video',
  doc: 'doc', docLegacy: 'doc', pages: 'doc', slides: 'slides',
  sheet: 'sheet', data: 'sheet', pdf: 'pdf', subtitle: 'subtitle',
};

const CATEGORY_LABELS = {
  image: 'Immagini', audio: 'Audio', video: 'Video', doc: 'Documenti',
  slides: 'Presentazioni', sheet: 'Fogli e dati', pdf: 'PDF', subtitle: 'Sottotitoli',
};

// Definizione dei formati di uscita: id -> { ext, label, group }
const TARGETS = {
  // immagini
  jpg: { ext: 'jpg', label: 'JPG', group: 'image', hint: 'Foto, compatibile ovunque' },
  png: { ext: 'png', label: 'PNG', group: 'image', hint: 'Grafica nitida, trasparenza' },
  webp: { ext: 'webp', label: 'WebP', group: 'image', hint: 'Leggero, ideale per il web' },
  avif: { ext: 'avif', label: 'AVIF', group: 'image', hint: 'Il più leggero, moderno' },
  heic: { ext: 'heic', label: 'HEIC', group: 'image', hint: 'Formato foto di iPhone' },
  gif: { ext: 'gif', label: 'GIF', group: 'image', hint: 'Animazioni semplici' },
  bmp: { ext: 'bmp', label: 'BMP', group: 'image', hint: 'Senza compressione' },
  tiff: { ext: 'tiff', label: 'TIFF', group: 'image', hint: 'Stampa e archivio' },
  ico: { ext: 'ico', label: 'ICO', group: 'image', hint: 'Icone per siti e Windows' },
  // audio
  mp3: { ext: 'mp3', label: 'MP3', group: 'audio', hint: 'Musica, compatibile ovunque' },
  m4a: { ext: 'm4a', label: 'M4A (AAC)', group: 'audio', hint: 'Apple, ottima qualità' },
  alac: { ext: 'm4a', label: 'ALAC (lossless)', group: 'audio', hint: 'Apple senza perdita' },
  wav: { ext: 'wav', label: 'WAV', group: 'audio', hint: 'Non compresso, per editing' },
  flac: { ext: 'flac', label: 'FLAC', group: 'audio', hint: 'Senza perdita, compresso' },
  aiff: { ext: 'aiff', label: 'AIFF', group: 'audio', hint: 'Non compresso, Apple' },
  ogg: { ext: 'ogg', label: 'OGG', group: 'audio', hint: 'Libero e leggero' },
  opus: { ext: 'opus', label: 'Opus', group: 'audio', hint: 'Ottimo per voce e podcast' },
  // video
  mp4: { ext: 'mp4', label: 'MP4', group: 'video', hint: 'Video, compatibile ovunque' },
  mov: { ext: 'mov', label: 'MOV', group: 'video', hint: 'QuickTime, Apple' },
  mkv: { ext: 'mkv', label: 'MKV', group: 'video', hint: 'Contenitore versatile' },
  webm: { ext: 'webm', label: 'WebM', group: 'video', hint: 'Per siti web' },
  avi: { ext: 'avi', label: 'AVI', group: 'video', hint: 'Per vecchi lettori' },
  // documenti
  pdf: { ext: 'pdf', label: 'PDF', group: 'doc', hint: 'Da condividere e stampare' },
  docx: { ext: 'docx', label: 'Word (DOCX)', group: 'doc', hint: 'Modificabile in Word e Pages' },
  doc: { ext: 'doc', label: 'Word 97 (DOC)', group: 'doc', hint: 'Word 97–2003' },
  odt: { ext: 'odt', label: 'ODT', group: 'doc', hint: 'LibreOffice Writer' },
  rtf: { ext: 'rtf', label: 'RTF', group: 'doc', hint: 'Testo formattato universale' },
  html: { ext: 'html', label: 'HTML', group: 'doc', hint: 'Pagina web' },
  md: { ext: 'md', label: 'Markdown', group: 'doc', hint: 'Testo con formattazione semplice' },
  txt: { ext: 'txt', label: 'Testo (TXT)', group: 'doc', hint: 'Solo testo' },
  epub: { ext: 'epub', label: 'EPUB', group: 'doc', hint: 'eBook per lettori digitali' },
  tex: { ext: 'tex', label: 'LaTeX', group: 'doc', hint: 'Documenti scientifici' },
  rst: { ext: 'rst', label: 'reStructuredText', group: 'doc', hint: 'Documentazione tecnica' },
  pptx: { ext: 'pptx', label: 'PowerPoint (PPTX)', group: 'slides', hint: 'Presentazione PowerPoint' },
  odp: { ext: 'odp', label: 'ODP', group: 'slides', hint: 'LibreOffice Impress' },
  // fogli e dati
  xlsx: { ext: 'xlsx', label: 'Excel (XLSX)', group: 'sheet', hint: 'Foglio Excel' },
  ods: { ext: 'ods', label: 'ODS', group: 'sheet', hint: 'LibreOffice Calc' },
  csv: { ext: 'csv', label: 'CSV', group: 'sheet', hint: 'Dati tabellari universali' },
  tsv: { ext: 'tsv', label: 'TSV', group: 'sheet', hint: 'Dati separati da tab' },
  json: { ext: 'json', label: 'JSON', group: 'sheet', hint: 'Dati per sviluppatori' },
  yaml: { ext: 'yaml', label: 'YAML', group: 'sheet', hint: 'Configurazioni leggibili' },
  // sottotitoli
  srt: { ext: 'srt', label: 'SRT', group: 'subtitle', hint: 'Sottotitoli universali' },
  vtt: { ext: 'vtt', label: 'WebVTT', group: 'subtitle', hint: 'Sottotitoli per il web' },
  ass: { ext: 'ass', label: 'ASS', group: 'subtitle', hint: 'Sottotitoli con stile' },
};

const IMAGE_OUT = ['jpg', 'png', 'webp', 'avif', 'heic', 'gif', 'bmp', 'tiff', 'ico', 'pdf'];
const AUDIO_OUT = ['mp3', 'm4a', 'alac', 'wav', 'flac', 'aiff', 'ogg', 'opus'];
const VIDEO_OUT = ['mp4', 'mov', 'mkv', 'webm', 'avi', 'gif'];
const DOC_OUT = ['pdf', 'docx', 'doc', 'odt', 'rtf', 'html', 'md', 'txt', 'epub', 'tex', 'rst', 'pptx'];
const SHEET_OUT = ['xlsx', 'ods', 'csv', 'tsv', 'json', 'yaml', 'html', 'md', 'pdf'];

function normExt(ext) {
  const e = String(ext || '').toLowerCase().replace(/^\./, '');
  if (e === 'jpeg') return 'jpg';
  if (e === 'tif') return 'tiff';
  if (e === 'yml') return 'yaml';
  if (e === 'htm') return 'html';
  if (e === 'markdown') return 'md';
  if (e === 'aif') return 'aiff';
  return e;
}

function familyOf(ext) {
  return EXT_TO_FAMILY[String(ext || '').toLowerCase().replace(/^\./, '')] || null;
}

// Restituisce gli id dei formati di uscita possibili per un'estensione
// `env` = { mac, ffmpeg, pandoc, libreoffice }
function targetIdsFor(ext, env) {
  const family = familyOf(ext);
  const self = normExt(ext);
  const lo = !!env.libreoffice;
  const ocr = env.ocr ? ['txt', 'docx'] : [];
  let ids = [];
  switch (family) {
    case 'image':
      if (env.ffmpeg) ids = [...IMAGE_OUT.filter((t) => t !== 'heic' || env.mac), ...ocr];
      break;
    case 'svg':
      if (env.ffmpeg) ids = IMAGE_OUT.filter((t) => t !== 'heic' || env.mac);
      else ids = ['png', 'pdf'];
      break;
    case 'imageMac':
      if (env.mac) ids = [...IMAGE_OUT, ...ocr];
      break;
    case 'gif':
      if (env.ffmpeg) ids = [...IMAGE_OUT.filter((t) => t !== 'heic' || env.mac), 'mp4', 'webm', ...ocr];
      break;
    case 'audio':
      if (env.ffmpeg) ids = AUDIO_OUT.slice();
      break;
    case 'video':
      if (env.ffmpeg) ids = [...VIDEO_OUT, ...AUDIO_OUT];
      break;
    case 'doc':
      if (env.pandoc) ids = DOC_OUT.filter((t) => t !== 'doc' || env.mac || lo);
      else if (env.mac && ['docx', 'odt', 'rtf', 'html', 'txt'].includes(self)) ids = ['docx', 'doc', 'odt', 'rtf', 'html', 'txt', 'pdf'];
      break;
    case 'docLegacy':
      if (self === 'doc' && !env.mac && lo) ids = ['pdf', 'docx', 'odt', 'rtf', 'html', 'txt'];
      else if (env.mac) ids = env.pandoc ? DOC_OUT.slice() : ['docx', 'doc', 'odt', 'rtf', 'html', 'txt', 'pdf'];
      break;
    case 'pages':
      if (lo) ids = ['pdf', 'docx', 'odt', 'rtf', 'txt'];
      break;
    case 'slides':
      if (lo) ids = ['pdf', 'pptx', 'odp'];
      // Dai .pptx si estraggono testo, tabelle e immagini anche senza LibreOffice
      if (self === 'pptx' && env.python && env.pandoc) ids = [...new Set([...ids, 'pdf', 'docx', 'odt', 'html', 'md', 'txt', 'epub'])];
      break;
    case 'sheet':
      ids = SHEET_OUT.slice();
      if (env.pandoc) ids.push('docx', 'odt');
      break;
    case 'data':
      ids = ['json', 'yaml', 'csv', 'xlsx', 'ods'];
      break;
    case 'pdf':
      ids = ['png', 'jpg', 'txt'];
      if (env.python) {
        ids.unshift('docx');
        if (env.pandoc) ids.push('odt', 'rtf', 'html', 'md', 'epub', 'pptx');
        if (env.mac) ids.push('doc');
        ids.push('xlsx', 'csv', 'ods');
      }
      break;
    case 'subtitle':
      if (env.ffmpeg) ids = ['srt', 'vtt', 'ass'];
      break;
    default:
      ids = [];
  }
  // Qualunque cosa diventi un PDF può diventare anche un'immagine per pagina
  if (['doc', 'docLegacy', 'pages'].includes(family) && ids.includes('pdf')) ids.push('png', 'jpg');
  if (family === 'slides' && lo) ids.push('png', 'jpg');
  // Ricomprimere nello stesso formato ha senso solo per i media (qualità/dimensioni)
  const recompress = ['image', 'gif', 'audio', 'video'].includes(family);
  return [...new Set(ids)].filter((id) => recompress || TARGETS[id].ext !== self);
}

// Descrizioni più precise quando il significato dipende dal file di partenza
const OCR_HINTS = { txt: 'Testo riconosciuto (OCR)', docx: 'Testo riconosciuto (OCR)' };
const PAGE_IMAGES = { png: 'Un’immagine per pagina', jpg: 'Un’immagine per pagina' };
const HINTS = {
  image: OCR_HINTS,
  imageMac: OCR_HINTS,
  gif: OCR_HINTS,
  doc: PAGE_IMAGES,
  docLegacy: PAGE_IMAGES,
  pages: PAGE_IMAGES,
  slides: { png: 'Un’immagine per slide', jpg: 'Un’immagine per slide', docx: 'Testo, tabelle e immagini delle slide', md: 'Testo delle slide', txt: 'Solo il testo delle slide' },
  sheet: { docx: 'Tabelle in un documento Word', odt: 'Tabelle in un documento ODT' },
  pdf: {
    docx: 'Modificabile, mantiene l’impaginazione',
    txt: 'Solo il testo (OCR se è una scansione)',
    xlsx: 'Le tabelle del PDF, una per foglio',
    ods: 'Le tabelle del PDF, una per foglio',
    csv: 'Le tabelle del PDF',
    pptx: 'Una slide per pagina',
    ...PAGE_IMAGES,
  },
};

function describeTargets(ext, env) {
  const hints = { ...(HINTS[familyOf(ext)] || {}) };
  if (familyOf(ext) === 'slides' && !env.libreoffice) hints.pdf = 'Testo e immagini delle slide';
  return targetIdsFor(ext, env).map((id) => ({ id, ...TARGETS[id], ...(hints[id] ? { hint: hints[id] } : {}) }));
}

module.exports = {
  FAMILIES,
  TARGETS,
  CATEGORY_LABELS,
  CATEGORY_OF_FAMILY,
  normExt,
  familyOf,
  targetIdsFor,
  describeTargets,
};
