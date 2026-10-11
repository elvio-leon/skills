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
  jpg: { ext: 'jpg', label: 'JPG', group: 'image' },
  png: { ext: 'png', label: 'PNG', group: 'image' },
  webp: { ext: 'webp', label: 'WebP', group: 'image' },
  avif: { ext: 'avif', label: 'AVIF', group: 'image' },
  heic: { ext: 'heic', label: 'HEIC', group: 'image' },
  gif: { ext: 'gif', label: 'GIF', group: 'image' },
  bmp: { ext: 'bmp', label: 'BMP', group: 'image' },
  tiff: { ext: 'tiff', label: 'TIFF', group: 'image' },
  ico: { ext: 'ico', label: 'ICO', group: 'image' },
  // audio
  mp3: { ext: 'mp3', label: 'MP3', group: 'audio' },
  m4a: { ext: 'm4a', label: 'M4A (AAC)', group: 'audio' },
  alac: { ext: 'm4a', label: 'ALAC (lossless)', group: 'audio' },
  wav: { ext: 'wav', label: 'WAV', group: 'audio' },
  flac: { ext: 'flac', label: 'FLAC', group: 'audio' },
  aiff: { ext: 'aiff', label: 'AIFF', group: 'audio' },
  ogg: { ext: 'ogg', label: 'OGG', group: 'audio' },
  opus: { ext: 'opus', label: 'Opus', group: 'audio' },
  // video
  mp4: { ext: 'mp4', label: 'MP4', group: 'video' },
  mov: { ext: 'mov', label: 'MOV', group: 'video' },
  mkv: { ext: 'mkv', label: 'MKV', group: 'video' },
  webm: { ext: 'webm', label: 'WebM', group: 'video' },
  avi: { ext: 'avi', label: 'AVI', group: 'video' },
  // documenti
  pdf: { ext: 'pdf', label: 'PDF', group: 'doc' },
  docx: { ext: 'docx', label: 'Word (DOCX)', group: 'doc' },
  doc: { ext: 'doc', label: 'Word 97 (DOC)', group: 'doc' },
  odt: { ext: 'odt', label: 'ODT', group: 'doc' },
  rtf: { ext: 'rtf', label: 'RTF', group: 'doc' },
  html: { ext: 'html', label: 'HTML', group: 'doc' },
  md: { ext: 'md', label: 'Markdown', group: 'doc' },
  txt: { ext: 'txt', label: 'Testo (TXT)', group: 'doc' },
  epub: { ext: 'epub', label: 'EPUB', group: 'doc' },
  tex: { ext: 'tex', label: 'LaTeX', group: 'doc' },
  rst: { ext: 'rst', label: 'reStructuredText', group: 'doc' },
  pptx: { ext: 'pptx', label: 'PowerPoint (PPTX)', group: 'slides' },
  odp: { ext: 'odp', label: 'ODP', group: 'slides' },
  // fogli e dati
  xlsx: { ext: 'xlsx', label: 'Excel (XLSX)', group: 'sheet' },
  ods: { ext: 'ods', label: 'ODS', group: 'sheet' },
  csv: { ext: 'csv', label: 'CSV', group: 'sheet' },
  tsv: { ext: 'tsv', label: 'TSV', group: 'sheet' },
  json: { ext: 'json', label: 'JSON', group: 'sheet' },
  yaml: { ext: 'yaml', label: 'YAML', group: 'sheet' },
  // sottotitoli
  srt: { ext: 'srt', label: 'SRT', group: 'subtitle' },
  vtt: { ext: 'vtt', label: 'WebVTT', group: 'subtitle' },
  ass: { ext: 'ass', label: 'ASS', group: 'subtitle' },
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
  let ids = [];
  switch (family) {
    case 'image':
    case 'svg':
      if (env.ffmpeg) ids = IMAGE_OUT.filter((t) => t !== 'heic' || env.mac);
      else if (family === 'svg') ids = ['png', 'pdf'];
      break;
    case 'imageMac':
      if (env.mac) ids = IMAGE_OUT.slice();
      break;
    case 'gif':
      if (env.ffmpeg) ids = [...IMAGE_OUT.filter((t) => t !== 'heic' || env.mac), 'mp4', 'webm'];
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
      break;
    case 'sheet':
      ids = SHEET_OUT.slice();
      break;
    case 'data':
      ids = ['json', 'yaml', 'csv', 'xlsx', 'ods'];
      break;
    case 'pdf':
      ids = ['png', 'jpg', 'txt'];
      break;
    case 'subtitle':
      if (env.ffmpeg) ids = ['srt', 'vtt', 'ass'];
      break;
    default:
      ids = [];
  }
  // Ricomprimere nello stesso formato ha senso solo per i media (qualità/dimensioni)
  const recompress = ['image', 'gif', 'audio', 'video'].includes(family);
  return ids.filter((id) => recompress || TARGETS[id].ext !== self);
}

function describeTargets(ext, env) {
  return targetIdsFor(ext, env).map((id) => ({ id, ...TARGETS[id] }));
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
