'use strict';

// `api` è esposto da preload.js tramite contextBridge (window.api).


const GROUP_LABELS = {
  image: 'Immagini', audio: 'Audio', video: 'Video', doc: 'Documenti',
  slides: 'Presentazioni', sheet: 'Fogli e dati', subtitle: 'Sottotitoli',
};
const GROUP_ORDER = ['image', 'video', 'audio', 'doc', 'slides', 'sheet', 'subtitle'];

const FORMAT_CARDS = [
  { cat: 'image', title: 'Immagini', text: 'JPG, PNG, WebP, AVIF, HEIC, GIF, TIFF, BMP, ICO, SVG, PSD, RAW → anche in PDF' },
  { cat: 'video', title: 'Video', text: 'MP4, MOV, MKV, WebM, AVI, WMV, FLV → GIF animate ed estrazione audio' },
  { cat: 'audio', title: 'Audio', text: 'MP3, AAC/M4A, ALAC, WAV, FLAC, AIFF, OGG, Opus, WMA' },
  { cat: 'doc', title: 'Documenti', text: 'Word (DOCX/DOC), ODT, RTF, Markdown, HTML, TXT, EPUB, LaTeX → PDF' },
  { cat: 'sheet', title: 'Fogli e dati', text: 'Excel, Numbers, ODS, CSV, TSV, JSON, YAML' },
  { cat: 'pdf', title: 'PDF', text: 'Da PDF a PNG/JPG (una immagine per pagina) e a testo' },
  { cat: 'slides', title: 'Presentazioni', text: 'PowerPoint, Keynote, ODP → PDF', needsLO: true },
  { cat: 'subtitle', title: 'Sottotitoli', text: 'SRT, WebVTT, ASS' },
];

const DEFAULT_OPTIONS = {
  imageQuality: 85,
  maxSize: 0,
  mergePdf: false,
  audioBitrate: 192,
  videoQuality: 'balanced',
  videoHeight: 0,
  fastCopy: false,
  gifFps: 12,
  pdfDpi: 150,
  csvSeparator: ',',
  outMode: 'same',
  outDir: null,
};

const state = {
  env: null,
  files: [],
  running: false,
  options: loadOptions(),
};

let nextId = 1;

// ---------- Utilità ----------

function loadOptions() {
  try {
    return { ...DEFAULT_OPTIONS, ...JSON.parse(localStorage.getItem('options') || '{}') };
  } catch {
    return { ...DEFAULT_OPTIONS };
  }
}

function saveOptions() {
  try {
    localStorage.setItem('options', JSON.stringify(state.options));
  } catch {
    /* non essenziale */
  }
}

function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'value') el.value = v;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}

function formatSize(bytes) {
  if (!bytes) return '';
  const units = ['byte', 'KB', 'MB', 'GB'];
  let i = 0;
  let n = bytes;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i += 1;
  }
  return `${n.toLocaleString('it-IT', { maximumFractionDigits: i ? 1 : 0 })} ${units[i]}`;
}

const $ = (id) => document.getElementById(id);

// ---------- File ----------

function addDescribed(list) {
  const known = new Set(state.files.map((f) => f.path));
  for (const d of list) {
    if (known.has(d.path)) continue;
    known.add(d.path);
    const lastTarget = state.files.find((f) => f.ext === d.ext && f.targetId)?.targetId;
    state.files.push({
      ...d,
      id: nextId++,
      targetId: lastTarget && d.targets.some((t) => t.id === lastTarget) ? lastTarget : '',
      status: 'idle',
      progress: null,
      outputs: [],
      error: '',
      details: '',
      showDetails: false,
    });
  }
  render();
}

async function addPaths(paths) {
  if (!paths.length) return;
  addDescribed(await api.describe(paths));
}

function removeFile(id) {
  state.files = state.files.filter((f) => f.id !== id);
  render();
}

function setTarget(file, targetId) {
  file.targetId = targetId;
  if (file.status !== 'running') {
    file.status = 'idle';
    file.error = '';
    file.outputs = [];
  }
}

function convertible() {
  return state.files.filter((f) => f.targetId && ['idle', 'error', 'cancelled'].includes(f.status));
}

// ---------- Rendering ----------

function render() {
  const has = state.files.length > 0;
  $('empty').hidden = has;
  $('work').hidden = !has;
  $('clear').hidden = !has || state.running;
  $('cancel').hidden = !state.running;
  $('add').disabled = state.running;
  const n = convertible().length;
  const convertBtn = $('convert');
  convertBtn.disabled = state.running || n === 0;
  convertBtn.textContent = state.running ? 'Conversione…' : n > 1 ? `Converti ${n} file` : 'Converti';
  if (has) {
    renderChips();
    renderList();
    renderOptions();
  }
}

function renderChips() {
  const chips = new Map();
  for (const f of state.files) {
    for (const t of f.targets) {
      if (!chips.has(t.id)) chips.set(t.id, { ...t, files: [] });
      chips.get(t.id).files.push(f);
    }
  }
  const supported = state.files.filter((f) => f.targets.length).length;
  const groups = new Map();
  for (const chip of chips.values()) {
    if (!groups.has(chip.group)) groups.set(chip.group, []);
    groups.get(chip.group).push(chip);
  }
  const container = $('chips');
  container.replaceChildren();
  if (!chips.size) {
    container.append(h('span', { class: 'sub' }, 'Nessuno dei file aggiunti è convertibile.'));
    return;
  }
  for (const group of GROUP_ORDER) {
    const list = groups.get(group);
    if (!list) continue;
    const groupEl = h('div', { class: 'chip-group' }, h('span', { class: 'chip-group-label' }, GROUP_LABELS[group]));
    for (const chip of list) {
      const active = chip.files.every((f) => f.targetId === chip.id);
      groupEl.append(
        h(
          'button',
          {
            class: `chip${active ? ' active' : ''}`,
            type: 'button',
            disabled: state.running,
            title: chip.files.length < supported ? `Applicabile a ${chip.files.length} file su ${supported}` : null,
            onclick: () => {
              for (const f of chip.files) if (f.status !== 'running') setTarget(f, chip.id);
              render();
            },
          },
          chip.label,
          chip.files.length < supported ? h('span', { class: 'count' }, `${chip.files.length}`) : null,
        ),
      );
    }
    container.append(groupEl);
  }
}

function targetSelect(file) {
  const select = h('select', {
    disabled: state.running || !file.targets.length,
    'aria-label': `Formato di destinazione per ${file.name}`,
    onchange: (e) => {
      setTarget(file, e.target.value);
      render();
    },
  });
  if (!file.targets.length) {
    select.append(h('option', { value: '' }, 'Non supportato'));
    return select;
  }
  select.append(h('option', { value: '' }, 'Scegli formato…'));
  for (const group of GROUP_ORDER) {
    const items = file.targets.filter((t) => t.group === group);
    if (!items.length) continue;
    const og = h('optgroup', { label: GROUP_LABELS[group] });
    for (const t of items) og.append(h('option', { value: t.id }, t.label));
    select.append(og);
  }
  select.value = file.targetId || '';
  return select;
}

function statusCell(file) {
  switch (file.status) {
    case 'queued':
      return h('div', { class: 'status' }, 'In coda');
    case 'running':
      return h('div', { class: 'status' }, h('span', { class: 'spinner' }), file.progress != null ? `${Math.round(file.progress * 100)}%` : 'In corso');
    case 'done':
      return h(
        'div',
        { class: 'status done' },
        '✓',
        h('button', { class: 'link', type: 'button', onclick: () => api.reveal(file.outputs[0]) }, 'Mostra nel Finder'),
      );
    case 'error':
      return h('div', { class: 'status error' }, 'Errore');
    case 'cancelled':
      return h('div', { class: 'status' }, 'Annullata');
    default:
      return h('div', { class: 'status' });
  }
}

function renderList() {
  const list = $('list');
  const scroll = list.scrollTop;
  list.replaceChildren();
  for (const file of state.files) {
    const sub = [file.ext.toUpperCase(), formatSize(file.size)].filter(Boolean).join(' · ');
    const meta = h('div', { class: 'meta' }, h('div', { class: 'name', title: file.path }, file.name), h('div', { class: 'sub' }, file.status === 'done' && file.outputs.length ? `→ ${file.outputs.map((o) => o.split('/').pop()).join(', ')}` : sub));
    if (!file.targets.length) meta.append(h('div', { class: 'sub' }, 'Formato non riconosciuto'));
    if (file.status === 'running') {
      const bar = h('div', { class: `bar${file.progress == null ? ' indeterminate' : ''}` }, h('div'));
      if (file.progress != null) bar.firstChild.style.width = `${Math.round(file.progress * 100)}%`;
      meta.append(bar);
    }
    if (file.status === 'error') {
      meta.append(
        h('div', { class: 'err-msg' }, file.error, ' ', file.details ? h('button', { class: 'link', type: 'button', onclick: () => { file.showDetails = !file.showDetails; render(); } }, file.showDetails ? 'Nascondi dettagli' : 'Dettagli') : null),
      );
      if (file.showDetails && file.details) meta.append(h('pre', { class: 'err-details' }, file.details));
    }
    list.append(
      h(
        'div',
        { class: `row${file.targets.length ? '' : ' unsupported'}`, role: 'listitem' },
        h('div', { class: `ficon cat-${file.category || 'none'}` }, file.ext.slice(0, 4) || '?'),
        meta,
        targetSelect(file),
        statusCell(file),
        h('button', { class: 'remove', type: 'button', title: 'Rimuovi', 'aria-label': `Rimuovi ${file.name}`, disabled: state.running && file.status === 'running', onclick: () => removeFile(file.id) }, '×'),
      ),
    );
  }
  list.scrollTop = scroll;
}

function field(label, control, hint) {
  return h('label', { class: 'field' }, h('span', {}, label), control, hint ? h('span', { class: 'hint' }, hint) : null);
}

function selectOpt(key, choices, { number = true } = {}) {
  const el = h('select', {
    disabled: state.running,
    onchange: (e) => {
      state.options[key] = number ? Number(e.target.value) : e.target.value;
      saveOptions();
    },
  });
  for (const [value, label] of choices) el.append(h('option', { value: String(value) }, label));
  el.value = String(state.options[key]);
  return el;
}

function checkOpt(key, label, hint) {
  return h(
    'label',
    { class: 'check' },
    h('input', {
      type: 'checkbox',
      checked: !!state.options[key],
      disabled: state.running,
      onchange: (e) => {
        state.options[key] = e.target.checked;
        saveOptions();
      },
    }),
    h('span', {}, label, hint ? h('small', {}, hint) : null),
  );
}

function renderOptions() {
  const cats = new Set(state.files.map((f) => f.category));
  const targets = new Set(state.files.map((f) => f.targetId).filter(Boolean));
  const groupsOut = new Set(state.files.flatMap((f) => f.targets.filter((t) => t.id === f.targetId).map((t) => t.group)));
  const panel = $('options');
  panel.replaceChildren();

  // Destinazione
  const o = state.options;
  const dest = h('div', { class: 'opt-section' }, h('h4', {}, 'Salva in'));
  const radio = (value, label) => h('label', { class: 'radio' }, h('input', {
    type: 'radio', name: 'outMode', checked: o.outMode === value, disabled: state.running,
    onchange: async () => {
      if (value === 'folder' && !o.outDir) {
        const dir = await api.pickFolder();
        if (!dir) return render();
        o.outDir = dir;
      }
      o.outMode = value;
      saveOptions();
      render();
    },
  }), label);
  dest.append(radio('same', 'Stessa cartella dell’originale'), radio('folder', 'Una cartella a scelta'));
  if (o.outMode === 'folder' && o.outDir) {
    dest.append(h('div', { class: 'folder' }, o.outDir, ' ', h('button', { class: 'link', type: 'button', disabled: state.running, onclick: async () => {
      const dir = await api.pickFolder();
      if (dir) {
        o.outDir = dir;
        saveOptions();
        render();
      }
    } }, 'Cambia')));
  }
  panel.append(dest);

  if (cats.has('image') || groupsOut.has('image')) {
    const range = h('input', { type: 'range', min: '10', max: '100', step: '1', value: String(o.imageQuality), disabled: state.running });
    const out = h('output', {}, String(o.imageQuality));
    range.addEventListener('input', () => {
      out.textContent = range.value;
      o.imageQuality = Number(range.value);
      saveOptions();
    });
    const sec = h('div', { class: 'opt-section' }, h('h4', {}, 'Immagini'),
      field('Qualità', h('div', { class: 'range-row' }, range, out), 'Per JPG, WebP, AVIF e HEIC'),
      field('Dimensione massima', selectOpt('maxSize', [[0, 'Originale'], [4096, '4096 px'], [2560, '2560 px'], [1920, '1920 px'], [1280, '1280 px'], [800, '800 px'], [512, '512 px'], [256, '256 px']]), 'Lato più lungo; non ingrandisce mai'),
    );
    const imagesToPdf = state.files.filter((f) => f.category === 'image' && f.targetId === 'pdf').length;
    if (imagesToPdf > 1) sec.append(checkOpt('mergePdf', `Unisci le ${imagesToPdf} immagini in un solo PDF`, 'Una pagina per immagine, nell’ordine dell’elenco'));
    panel.append(sec);
  }

  if (groupsOut.has('audio') || cats.has('audio')) {
    panel.append(h('div', { class: 'opt-section' }, h('h4', {}, 'Audio'),
      field('Qualità (bitrate)', selectOpt('audioBitrate', [[96, '96 kbps'], [128, '128 kbps'], [192, '192 kbps'], [256, '256 kbps'], [320, '320 kbps']]), 'Per MP3, AAC, OGG e Opus. WAV, FLAC, AIFF e ALAC sono senza perdita'),
    ));
  }

  if (cats.has('video')) {
    const sec = h('div', { class: 'opt-section' }, h('h4', {}, 'Video'),
      field('Qualità', selectOpt('videoQuality', [['high', 'Alta'], ['balanced', 'Bilanciata'], ['small', 'File più leggero']], { number: false })),
      field('Risoluzione', selectOpt('videoHeight', [[0, 'Originale'], [2160, '4K (2160p)'], [1080, 'Full HD (1080p)'], [720, 'HD (720p)'], [480, '480p']])),
      checkOpt('fastCopy', 'Conversione rapida', 'Cambia solo il contenitore senza ricodificare, quando possibile (es. MKV → MP4)'),
    );
    if (targets.has('gif')) sec.append(field('Fotogrammi al secondo (GIF)', selectOpt('gifFps', [[8, '8'], [10, '10'], [12, '12'], [15, '15'], [20, '20'], [24, '24']])));
    panel.append(sec);
  }

  if (targets.has('csv')) {
    panel.append(h('div', { class: 'opt-section' }, h('h4', {}, 'CSV'),
      field('Separatore', selectOpt('csvSeparator', [[',', 'Virgola ( , )'], [';', 'Punto e virgola ( ; )']], { number: false }), 'Il punto e virgola è quello che si aspetta Excel in italiano'),
    ));
  }

  if (cats.has('pdf')) {
    panel.append(h('div', { class: 'opt-section' }, h('h4', {}, 'Da PDF a immagine'),
      field('Risoluzione', selectOpt('pdfDpi', [[72, '72 DPI (schermo)'], [150, '150 DPI'], [300, '300 DPI (stampa)']]), 'Ogni pagina diventa un’immagine'),
    ));
  }
}

function renderFormatCards() {
  const lo = state.env && state.env.engines.libreoffice;
  $('formats').replaceChildren(
    ...FORMAT_CARDS.map((c) => h('div', { class: 'format-card' },
      h('h3', {}, h('span', { class: `ficon cat-${c.cat}` }), c.title),
      h('p', {}, c.text),
      c.needsLO && !lo ? h('p', { class: 'note' }, 'Richiede LibreOffice (gratuito)') : null,
    )),
  );
  for (const icon of document.querySelectorAll('.format-card .ficon')) {
    icon.style.width = '10px';
    icon.style.height = '10px';
    icon.style.borderRadius = '3px';
  }
}

function renderEngines() {
  const e = state.env.engines;
  const items = [
    ['ffmpeg', 'Audio, video e immagini', e.ffmpeg],
    ['pandoc', 'Documenti', e.pandoc],
  ];
  if (state.env.platform === 'darwin') items.push(['macOS', 'HEIC, RAW, DOC', e.sips && e.textutil]);
  const el = $('engines');
  el.replaceChildren(...items.map(([name, desc, ok]) => h('span', { class: `engine${ok ? '' : ' off'}`, title: desc }, name)));
  el.append(
    e.libreoffice
      ? h('span', { class: 'engine', title: 'PowerPoint, Keynote, Pages e PDF ad alta fedeltà' }, 'LibreOffice')
      : h('span', { class: 'engine off' }, 'LibreOffice non installato · ', h('button', { class: 'link', type: 'button', onclick: () => api.openLibreOfficeSite() }, 'scaricalo (opzionale)')),
  );
}

// ---------- Conversione ----------

async function startConversion() {
  const jobs = convertible();
  if (!jobs.length) return;
  for (const f of jobs) {
    f.status = 'queued';
    f.error = '';
    f.details = '';
    f.progress = null;
  }
  state.running = true;
  render();
  const o = state.options;
  const res = await api.convert(
    jobs.map((f) => ({ id: f.id, input: f.path, targetId: f.targetId })),
    { ...o, outDir: o.outMode === 'folder' ? o.outDir : null },
  );
  if (!res.started) {
    state.running = false;
    for (const f of jobs) f.status = 'idle';
    render();
  }
}

api.onJobUpdate((msg) => {
  const file = state.files.find((f) => f.id === msg.id);
  if (!file) return;
  file.status = msg.status;
  file.progress = msg.progress ?? null;
  if (msg.outputs) file.outputs = msg.outputs;
  if (msg.error) file.error = msg.error;
  if (msg.details) file.details = msg.details;
  render();
});

api.onQueueDone(() => {
  state.running = false;
  for (const f of state.files) if (f.status === 'queued') f.status = 'idle';
  render();
});

api.onOpenFiles((paths) => addPaths(paths));

// ---------- Eventi ----------

async function pickFiles() {
  if (state.running) return;
  addDescribed(await api.pickFiles());
}

$('dropzone').addEventListener('click', pickFiles);
$('add').addEventListener('click', pickFiles);
$('convert').addEventListener('click', startConversion);
$('cancel').addEventListener('click', () => api.cancel());
$('clear').addEventListener('click', () => {
  state.files = [];
  render();
});

let dragDepth = 0;
window.addEventListener('dragenter', (e) => {
  e.preventDefault();
  if (state.running) return;
  dragDepth += 1;
  $('overlay').hidden = false;
});
window.addEventListener('dragleave', (e) => {
  e.preventDefault();
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) $('overlay').hidden = true;
});
window.addEventListener('dragover', (e) => e.preventDefault());
window.addEventListener('drop', (e) => {
  e.preventDefault();
  dragDepth = 0;
  $('overlay').hidden = true;
  if (state.running) return;
  const paths = [...(e.dataTransfer?.files || [])].map((f) => api.pathForFile(f)).filter(Boolean);
  addPaths(paths);
});

(async () => {
  state.env = await api.env();
  renderEngines();
  renderFormatCards();
  render();
})();
