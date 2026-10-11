'use strict';

// `api` è esposto da preload.js tramite contextBridge (window.api).

const GROUPS = {
  image: { label: 'Immagine', icon: 'i-image' },
  video: { label: 'Video', icon: 'i-video' },
  audio: { label: 'Audio', icon: 'i-audio' },
  doc: { label: 'Documento', icon: 'i-doc' },
  slides: { label: 'Slide', icon: 'i-slides' },
  sheet: { label: 'Dati', icon: 'i-sheet' },
  subtitle: { label: 'Sottotitoli', icon: 'i-subtitle' },
};
const GROUP_ORDER = ['image', 'video', 'audio', 'doc', 'slides', 'sheet', 'subtitle'];

const CATEGORY_ICON = {
  image: 'i-image', video: 'i-video', audio: 'i-audio', doc: 'i-doc',
  sheet: 'i-sheet', pdf: 'i-pdf', slides: 'i-slides', subtitle: 'i-subtitle',
};
// Gruppo di uscita più naturale per ciascuna categoria di partenza
const NATURAL_GROUP = { image: 'image', video: 'video', audio: 'audio', doc: 'doc', sheet: 'sheet', pdf: 'image', slides: 'doc', subtitle: 'subtitle' };
const RECOMMENDED = new Set(['jpg', 'mp4', 'mp3', 'pdf', 'xlsx', 'srt']);

const FORMAT_CARDS = [
  { cat: 'image', title: 'Immagini', text: 'JPG, PNG, WebP, AVIF, HEIC, GIF, TIFF, SVG, PSD, RAW' },
  { cat: 'video', title: 'Video', text: 'MP4, MOV, MKV, WebM, AVI → anche GIF e solo audio' },
  { cat: 'audio', title: 'Audio', text: 'MP3, AAC, ALAC, WAV, FLAC, AIFF, OGG, Opus' },
  { cat: 'doc', title: 'Documenti', text: 'Word, ODT, RTF, Markdown, HTML, EPUB → PDF' },
  { cat: 'sheet', title: 'Fogli e dati', text: 'Excel, Numbers, ODS, CSV, JSON, YAML' },
  { cat: 'pdf', title: 'PDF', text: 'In immagini (una per pagina) o in testo' },
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
  optionsOpen: false,
};

const state = {
  env: null,
  files: [],
  running: false,
  tab: null,
  lastRun: null,
  options: loadOptions(),
};

let nextId = 1;
const rowEls = new Map();

// ============ Utilità ============

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
    /* preferenza non essenziale */
  }
}

const $ = (id) => document.getElementById(id);

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

function icon(id, cls = 'i') {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', cls);
  svg.setAttribute('aria-hidden', 'true');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#${id}`);
  svg.append(use);
  return svg;
}

function typeBadge(category, small) {
  return h('span', { class: `ftype${small ? ' sm' : ''} c-${category || 'none'}` }, icon(CATEGORY_ICON[category] || 'i-file'));
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

function plural(n, one, many) {
  return `${n} ${n === 1 ? one : many}`;
}

function baseName(p) {
  return String(p).split('/').pop();
}

let toastTimer = null;
function toast(text) {
  const el = $('toast');
  el.textContent = text;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.hidden = true;
  }, 3500);
}

function targetOf(file) {
  return file.targets.find((t) => t.id === file.targetId) || null;
}

// ============ Gestione file ============

function addDescribed(list) {
  const known = new Set(state.files.map((f) => f.path));
  let added = 0;
  let unsupported = 0;
  for (const d of list) {
    if (known.has(d.path)) continue;
    known.add(d.path);
    added += 1;
    if (!d.targets.length) unsupported += 1;
    // Se esiste già un file dello stesso tipo, eredita il suo formato di destinazione
    const sibling = state.files.find((f) => f.ext === d.ext && f.targetId);
    const inherited = sibling && d.targets.some((t) => t.id === sibling.targetId) ? sibling.targetId : '';
    state.files.push({ ...d, id: nextId++, targetId: inherited, status: 'idle', progress: null, outputs: [], error: '', details: '', showDetails: false });
  }
  if (!added && list.length) toast('Questi file sono già nell’elenco');
  else if (unsupported) toast(`${plural(unsupported, 'file non è', 'file non sono')} di un formato supportato`);
  if (added) state.lastRun = null;
  pickTab();
  render();
}

async function addPaths(paths) {
  if (!paths.length || state.running) return;
  addDescribed(await api.describe(paths));
}

async function pickFiles() {
  if (state.running) return;
  addDescribed(await api.pickFiles());
}

function removeFile(id) {
  state.files = state.files.filter((f) => f.id !== id);
  pickTab();
  render();
}

function setTarget(file, targetId) {
  if (file.status === 'running' || file.status === 'queued') return;
  file.targetId = targetId;
  file.status = 'idle';
  file.error = '';
  file.details = '';
  file.outputs = [];
}

function pending() {
  return state.files.filter((f) => f.targetId && ['idle', 'error', 'cancelled'].includes(f.status));
}

// Le immagini → PDF compaiono anche nella scheda Immagine, dove l'utente le cerca
function inGroup(file, target, group) {
  return target.group === group || (group === 'image' && target.id === 'pdf' && file.category === 'image');
}

function availableGroups() {
  const set = new Set();
  for (const f of state.files) for (const t of f.targets) set.add(t.group);
  return GROUP_ORDER.filter((g) => set.has(g));
}

// Sceglie la scheda di formati più utile per i file presenti
function pickTab() {
  const groups = availableGroups();
  if (state.tab && groups.includes(state.tab)) return;
  const votes = new Map();
  for (const f of state.files) {
    const g = NATURAL_GROUP[f.category];
    if (g && groups.includes(g)) votes.set(g, (votes.get(g) || 0) + 1);
  }
  const best = [...votes.entries()].sort((a, b) => b[1] - a[1])[0];
  state.tab = best ? best[0] : groups[0] || null;
}

// ============ Rendering ============

function render() {
  const has = state.files.length > 0;
  $('empty').hidden = has;
  $('work').hidden = !has;
  if (!has) return;
  renderQueueHead();
  renderSummary();
  renderList();
  renderTabs();
  renderTiles();
  renderOptions();
  renderDest();
  renderFoot();
}

function renderQueueHead() {
  const total = state.files.length;
  const ready = pending().length;
  const missing = state.files.filter((f) => f.targets.length && !f.targetId).length;
  $('queue-title').textContent = plural(total, 'file', 'file');
  let sub;
  if (state.running) sub = 'Conversione in corso: puoi continuare a usare il Mac';
  else if (missing) sub = `${plural(missing, 'file attende', 'file attendono')} un formato: sceglilo a destra`;
  else if (ready) sub = `${plural(ready, 'file pronto', 'file pronti')} da convertire`;
  else sub = 'Tutto convertito';
  $('queue-sub').textContent = sub;
  $('add').disabled = state.running;
  $('clear').disabled = state.running;
}

function renderSummary() {
  const el = $('summary');
  const run = state.lastRun;
  if (!run || state.running) {
    el.hidden = true;
    return;
  }
  const inRun = state.files.filter((f) => run.ids.includes(f.id));
  const ok = inRun.filter((f) => f.status === 'done').length;
  const failed = inRun.filter((f) => f.status === 'error').length;
  if (!ok && !failed) {
    el.hidden = true;
    return;
  }
  const firstOut = inRun.find((f) => f.outputs.length)?.outputs[0];
  const where = state.options.outMode === 'folder' && state.options.outDir
    ? 'I nuovi file sono nella cartella che hai scelto.'
    : 'I nuovi file sono accanto agli originali, con lo stesso nome.';
  let title = `Fatto! ${plural(ok, 'file convertito', 'file convertiti')}`;
  if (failed) title = ok ? `${plural(ok, 'file convertito', 'file convertiti')}, ${plural(failed, 'errore', 'errori')}` : 'La conversione non è riuscita';
  el.className = `summary${failed ? ' has-errors' : ''}`;
  el.replaceChildren(
    icon(failed ? 'i-alert' : 'i-check-circle', 'i big-icon'),
    h('div', { class: 'summary-text' },
      h('strong', {}, title),
      h('span', {}, failed ? 'Apri i dettagli sotto il file per capire cosa è successo.' : where)),
    h('div', { class: 'summary-actions' },
      firstOut ? h('button', { class: 'btn', type: 'button', onclick: () => api.reveal(firstOut) }, icon('i-folder'), 'Mostra nel Finder') : null,
      h('button', { class: 'btn ghost', type: 'button', onclick: clearDone }, 'Pulisci completati')),
  );
  el.hidden = false;
}

function clearDone() {
  state.files = state.files.filter((f) => f.status !== 'done');
  state.lastRun = null;
  pickTab();
  render();
}

function rowSelect(file) {
  const select = h('select', {
    class: `row-select${file.targetId ? '' : ' unset'}`,
    disabled: state.running || !file.targets.length,
    'aria-label': `Formato di destinazione per ${file.name}`,
    onchange: (e) => {
      setTarget(file, e.target.value);
      state.lastRun = null;
      render();
    },
  });
  if (!file.targets.length) {
    select.append(h('option', { value: '' }, 'Non supportato'));
    return select;
  }
  select.append(h('option', { value: '' }, 'Scegli formato…'));
  for (const g of GROUP_ORDER) {
    const items = file.targets.filter((t) => t.group === g);
    if (!items.length) continue;
    const og = h('optgroup', { label: GROUPS[g].label });
    for (const t of items) og.append(h('option', { value: t.id }, t.label));
    select.append(og);
  }
  select.value = file.targetId || '';
  return select;
}

function rowState(file) {
  switch (file.status) {
    case 'queued':
      return h('span', { class: 'state' }, 'In coda');
    case 'running':
      return h('span', { class: 'state' }, h('span', { class: 'spinner', 'aria-hidden': 'true' }), file.progress != null ? `${Math.round(file.progress * 100)}%` : 'In corso');
    case 'done':
      return h('button', { class: 'btn ghost', type: 'button', title: 'Mostra nel Finder', onclick: () => api.reveal(file.outputs[0]) }, icon('i-folder'), 'Mostra');
    case 'error':
      return h('span', { class: 'state err' }, icon('i-alert'), 'Errore');
    case 'cancelled':
      return h('span', { class: 'state' }, 'Interrotta');
    default:
      return null;
  }
}

function renderRow(file) {
  const target = targetOf(file);
  const sub = h('div', { class: 'sub' });
  if (file.status === 'done' && file.outputs.length) {
    sub.append(h('span', { class: 'state ok' }, icon('i-check')), h('span', { class: 'out-name' }, file.outputs.map(baseName).join(', ')));
  } else {
    sub.append(h('span', { class: 'pill' }, file.ext.toUpperCase() || '?'));
    if (target) sub.append(icon('i-arrow'), h('span', { class: 'pill to' }, target.ext.toUpperCase()));
    const info = [formatSize(file.size), file.targets.length ? '' : 'formato non riconosciuto'].filter(Boolean).join(' · ');
    if (info) sub.append(h('span', {}, info));
  }
  const meta = h('div', { class: 'meta' }, h('div', { class: 'name', title: file.path }, file.name), sub);
  if (file.status === 'running') {
    const pct = file.progress != null ? Math.round(file.progress * 100) : null;
    const bar = h('div', { class: `bar${pct == null ? ' indeterminate' : ''}`, role: 'progressbar', 'aria-label': `Avanzamento ${file.name}`, 'aria-valuemin': '0', 'aria-valuemax': '100', 'aria-valuenow': pct == null ? null : String(pct) }, h('div'));
    if (pct != null) bar.firstChild.style.width = `${pct}%`;
    meta.append(bar);
  }
  if (file.status === 'error') {
    meta.append(h('div', { class: 'err-msg' }, icon('i-alert'), h('span', {}, file.error, ' ',
      file.details ? h('button', { class: 'link', type: 'button', onclick: () => { file.showDetails = !file.showDetails; updateRow(file); } }, file.showDetails ? 'Nascondi dettagli' : 'Dettagli tecnici') : null)));
    if (file.showDetails && file.details) meta.append(h('pre', { class: 'err-details' }, file.details));
  }
  const cls = ['row'];
  if (file.status === 'done') cls.push('is-done');
  if (file.status === 'error') cls.push('is-error');
  if (!file.targets.length) cls.push('is-unsupported');
  const row = h('div', {
    class: cls.join(' '),
    role: 'listitem',
    tabindex: '0',
    'aria-label': file.name,
    onkeydown: (e) => {
      if ((e.key === 'Backspace' || e.key === 'Delete') && e.target === row && !state.running) removeFile(file.id);
    },
  },
  typeBadge(file.category),
  meta,
  rowSelect(file),
  h('div', { class: 'row-end' },
    rowState(file),
    h('button', { class: 'icon-btn', type: 'button', title: 'Rimuovi dall’elenco', 'aria-label': `Rimuovi ${file.name}`, disabled: state.running, onclick: () => removeFile(file.id) }, icon('i-x'))));
  return row;
}

function renderList() {
  const list = $('list');
  const scroll = list.scrollTop;
  const known = new Set(rowEls.keys());
  rowEls.clear();
  const nodes = state.files.map((f) => {
    const el = renderRow(f);
    // Solo le righe appena aggiunte si animano
    if (known.has(f.id)) el.style.animation = 'none';
    rowEls.set(f.id, el);
    return el;
  });
  list.replaceChildren(...nodes);
  list.scrollTop = scroll;
}

function updateRow(file) {
  const old = rowEls.get(file.id);
  if (!old) return;
  const el = renderRow(file);
  el.style.animation = 'none';
  old.replaceWith(el);
  rowEls.set(file.id, el);
}

function renderTabs() {
  const groups = availableGroups();
  const tabs = $('tabs');
  tabs.hidden = groups.length < 2;
  tabs.replaceChildren(...groups.map((g) => h('button', {
    class: `tab c-${g}`,
    type: 'button',
    role: 'tab',
    'aria-selected': String(state.tab === g),
    onclick: () => {
      state.tab = g;
      renderTabs();
      renderTiles();
    },
  }, icon(GROUPS[g].icon), GROUPS[g].label)));
}

function renderTiles() {
  const tiles = $('tiles');
  const note = $('tiles-note');
  const editable = state.files.filter((f) => f.targets.length);
  const chips = new Map();
  for (const f of editable) {
    for (const t of f.targets) {
      if (!inGroup(f, t, state.tab)) continue;
      if (!chips.has(t.id)) chips.set(t.id, { ...t, files: [] });
      chips.get(t.id).files.push(f);
    }
  }
  let anyPartial = false;
  tiles.replaceChildren(...[...chips.values()].map((c) => {
    const chosen = c.files.filter((f) => f.targetId === c.id).length;
    const selected = chosen > 0 && chosen === c.files.length;
    const partialApply = c.files.length < editable.length;
    if (selected && partialApply) anyPartial = true;
    let corner = null;
    if (selected) corner = h('span', { class: 'check' }, icon('i-check'));
    else if (partialApply) corner = h('span', { class: 'tile-count' }, `${c.files.length}/${editable.length}`);
    return h('button', {
      class: `tile${selected ? ' selected' : chosen ? ' partial' : ''}`,
      type: 'button',
      'aria-pressed': String(selected),
      disabled: state.running,
      title: partialApply ? `Si applica a ${c.files.length} file su ${editable.length}` : null,
      onclick: () => {
        for (const f of c.files) setTarget(f, c.id);
        state.lastRun = null;
        render();
      },
    },
    h('span', { class: 'tile-label' }, c.label),
    h('span', { class: 'tile-hint' }, c.hint || ''),
    corner,
    RECOMMENDED.has(c.id) && !selected && !partialApply ? h('span', { class: 'rec' }, 'Consigliato') : null);
  }));
  if (!chips.size) {
    note.hidden = false;
    note.replaceChildren(icon('i-alert'), 'Nessuno dei file aggiunti può essere convertito.');
  } else if (anyPartial) {
    note.hidden = false;
    note.replaceChildren('Questo formato vale solo per i file compatibili: per gli altri scegli da un’altra scheda o direttamente nell’elenco.');
  } else note.hidden = true;
}

// ---------- Opzioni ----------

function field(label, control, hint, value) {
  return h('label', { class: 'field' },
    h('span', { class: 'field-label' }, label, value || null),
    control,
    hint ? h('span', { class: 'field-hint' }, hint) : null);
}

function selectOpt(key, choices, { number = true } = {}) {
  const el = h('select', {
    class: 'select',
    disabled: state.running,
    onchange: (e) => {
      state.options[key] = number ? Number(e.target.value) : e.target.value;
      saveOptions();
      renderOptionsSummary();
    },
  });
  for (const [value, label] of choices) el.append(h('option', { value: String(value) }, label));
  el.value = String(state.options[key]);
  return el;
}

function toggleOpt(key, label, hint) {
  return h('label', { class: 'toggle' },
    h('input', {
      type: 'checkbox',
      role: 'switch',
      checked: !!state.options[key],
      disabled: state.running,
      onchange: (e) => {
        state.options[key] = e.target.checked;
        saveOptions();
        renderOptionsSummary();
      },
    }),
    h('span', { class: 'toggle-text' }, label, hint ? h('small', {}, hint) : null));
}

function activeContext() {
  const chosen = state.files.filter((f) => f.targetId);
  return {
    outGroups: new Set(chosen.map((f) => targetOf(f)?.group)),
    cats: new Set(chosen.map((f) => f.category)),
    targets: new Set(chosen.map((f) => f.targetId)),
    imagesToPdf: chosen.filter((f) => f.category === 'image' && f.targetId === 'pdf').length,
  };
}

function renderOptions() {
  const details = $('options');
  details.open = !!state.options.optionsOpen;
  details.ontoggle = () => {
    state.options.optionsOpen = details.open;
    saveOptions();
  };
  const o = state.options;
  const ctx = activeContext();
  const groups = [];

  if (ctx.outGroups.has('image') || ctx.imagesToPdf) {
    const value = h('span', { class: 'muted' }, String(o.imageQuality));
    const range = h('input', { type: 'range', min: '10', max: '100', step: '1', value: String(o.imageQuality), disabled: state.running, 'aria-label': 'Qualità immagine' });
    range.addEventListener('input', () => {
      value.textContent = range.value;
      o.imageQuality = Number(range.value);
      saveOptions();
      renderOptionsSummary();
    });
    groups.push(h('div', { class: 'opt-group' }, h('h4', {}, 'Immagini'),
      field('Qualità', range, 'Più alta = file più grande. 85 è un ottimo compromesso.', value),
      field('Dimensione massima', selectOpt('maxSize', [[0, 'Originale'], [3840, '3840 px (4K)'], [2560, '2560 px'], [1920, '1920 px (Full HD)'], [1280, '1280 px'], [800, '800 px'], [512, '512 px']]), 'Lato più lungo. Le immagini non vengono mai ingrandite.'),
      ctx.imagesToPdf > 1 ? toggleOpt('mergePdf', 'Unisci in un solo PDF', `Le ${ctx.imagesToPdf} immagini diventano le pagine di un unico documento`) : null));
  }
  if (ctx.outGroups.has('audio')) {
    groups.push(h('div', { class: 'opt-group' }, h('h4', {}, 'Audio'),
      field('Qualità', selectOpt('audioBitrate', [[96, 'Voce · 96 kbps'], [128, 'Buona · 128 kbps'], [192, 'Alta · 192 kbps'], [256, 'Molto alta · 256 kbps'], [320, 'Massima · 320 kbps']]), 'Vale per MP3, AAC, OGG e Opus. WAV, FLAC, AIFF e ALAC sono già senza perdita.')));
  }
  if (ctx.outGroups.has('video') || ctx.targets.has('mp4') || ctx.targets.has('webm')) {
    groups.push(h('div', { class: 'opt-group' }, h('h4', {}, 'Video'),
      field('Qualità', selectOpt('videoQuality', [['high', 'Alta'], ['balanced', 'Bilanciata (consigliata)'], ['small', 'File più leggero']], { number: false })),
      field('Risoluzione', selectOpt('videoHeight', [[0, 'Come l’originale'], [2160, '4K · 2160p'], [1080, 'Full HD · 1080p'], [720, 'HD · 720p'], [480, '480p']])),
      ctx.targets.has('gif') ? field('Fluidità della GIF', selectOpt('gifFps', [[8, '8 fotogrammi/s'], [12, '12 fotogrammi/s'], [15, '15 fotogrammi/s'], [24, '24 fotogrammi/s']])) : null,
      toggleOpt('fastCopy', 'Conversione rapida', 'Cambia solo il “contenitore” senza ricodificare, quando possibile (es. MKV → MP4). Molto più veloce.')));
  }
  if (ctx.cats.has('pdf') && (ctx.targets.has('png') || ctx.targets.has('jpg'))) {
    groups.push(h('div', { class: 'opt-group' }, h('h4', {}, 'Da PDF a immagine'),
      field('Risoluzione', selectOpt('pdfDpi', [[72, 'Schermo · 72 DPI'], [150, 'Standard · 150 DPI'], [300, 'Stampa · 300 DPI']]), 'Ogni pagina diventa un’immagine, raccolte in una cartella.')));
  }
  if (ctx.targets.has('csv')) {
    groups.push(h('div', { class: 'opt-group' }, h('h4', {}, 'CSV'),
      field('Separatore', selectOpt('csvSeparator', [[',', 'Virgola ( , )'], [';', 'Punto e virgola ( ; )']], { number: false }), 'Scegli il punto e virgola se aprirai il file con Excel in italiano.')));
  }
  if (!groups.length) groups.push(h('p', { class: 'muted small' }, 'Scegli un formato per vedere le opzioni disponibili. Le impostazioni predefinite vanno bene nella maggior parte dei casi.'));
  $('options-body').replaceChildren(...groups);
  renderOptionsSummary();
}

function renderOptionsSummary() {
  const o = state.options;
  const ctx = activeContext();
  const parts = [];
  if (ctx.outGroups.has('image')) parts.push(`Qualità ${o.imageQuality}`);
  if (ctx.outGroups.has('audio')) parts.push(`${o.audioBitrate} kbps`);
  if (ctx.outGroups.has('video')) parts.push({ high: 'Video alta qualità', balanced: 'Video bilanciato', small: 'Video leggero' }[o.videoQuality]);
  $('options-summary').textContent = parts.join(' · ') || 'Predefinite';
}

function renderDest() {
  const o = state.options;
  const choose = async () => {
    const dir = await api.pickFolder();
    if (!dir) return;
    o.outDir = dir;
    o.outMode = 'folder';
    saveOptions();
    renderDest();
  };
  const btn = (mode, label) => h('button', {
    type: 'button',
    role: 'radio',
    'aria-checked': String(o.outMode === mode),
    disabled: state.running,
    onclick: async () => {
      if (mode === 'folder' && !o.outDir) return choose();
      o.outMode = mode;
      saveOptions();
      renderDest();
    },
  }, label);
  $('dest').replaceChildren(btn('same', 'Accanto agli originali'), btn('folder', 'In una cartella'));
  const path = $('dest-path');
  if (o.outMode === 'folder' && o.outDir) {
    path.replaceChildren(h('span', {}, o.outDir), h('button', { class: 'link', type: 'button', disabled: state.running, onclick: choose }, 'Cambia'));
  } else {
    path.replaceChildren('Ogni file convertito viene salvato nella stessa cartella dell’originale. Nulla viene sovrascritto.');
  }
}

function renderFoot() {
  const n = pending().length;
  const btn = $('convert');
  btn.hidden = state.running;
  btn.disabled = n === 0;
  let label = 'Converti';
  if (n) label = `Converti ${plural(n, 'file', 'file')}`;
  else if (state.files.some((f) => f.targets.length && !f.targetId)) label = 'Scegli un formato';
  $('convert-label').textContent = label;
  $('cancel').hidden = !state.running;
  renderOverall();
}

function renderOverall() {
  const el = $('overall');
  const run = state.lastRun;
  if (!state.running || !run) {
    el.hidden = true;
    return;
  }
  el.hidden = false;
  const files = state.files.filter((f) => run.ids.includes(f.id));
  const finished = files.filter((f) => ['done', 'error', 'cancelled'].includes(f.status)).length;
  const partial = files.reduce((acc, f) => acc + (f.status === 'running' ? f.progress || 0 : 0), 0);
  const ratio = files.length ? (finished + partial) / files.length : 0;
  $('overall-label').textContent = 'Conversione in corso…';
  $('overall-count').textContent = `${finished} di ${files.length}`;
  $('overall-bar').style.width = `${Math.round(ratio * 100)}%`;
}

function renderFormatCards() {
  const lo = state.env && state.env.engines.libreoffice;
  $('formats').replaceChildren(...FORMAT_CARDS.map((c) => h('div', { class: 'format-card' },
    typeBadge(c.cat, true),
    h('div', {},
      h('h3', {}, c.title),
      h('p', {}, c.text),
      c.needsLO && !lo ? h('p', { class: 'needs' }, 'Richiede LibreOffice (gratuito)') : null))));
}

function renderEngines() {
  const e = state.env.engines;
  const items = [
    ['Audio, video e immagini', e.ffmpeg],
    ['Documenti', e.pandoc],
  ];
  if (state.env.platform === 'darwin') items.push(['Formati Apple (HEIC, RAW, DOC)', e.sips && e.textutil]);
  const el = $('engines');
  el.replaceChildren(...items.map(([name, ok]) => h('span', { class: `engine${ok ? '' : ' off'}` }, name)));
  el.append(e.libreoffice
    ? h('span', { class: 'engine' }, 'Office e Keynote (LibreOffice)')
    : h('span', { class: 'engine off' }, 'Office e Keynote: ', h('button', { class: 'link', type: 'button', onclick: () => api.openLibreOfficeSite() }, 'installa LibreOffice')));
  $('version').textContent = `v${state.env.version}`;
}

// ============ Conversione ============

async function startConversion() {
  const jobs = pending();
  if (!jobs.length || state.running) return;
  for (const f of jobs) {
    f.status = 'queued';
    f.error = '';
    f.details = '';
    f.progress = null;
    f.showDetails = false;
  }
  state.running = true;
  state.lastRun = { ids: jobs.map((f) => f.id) };
  render();
  const o = state.options;
  const res = await api.convert(
    jobs.map((f) => ({ id: f.id, input: f.path, targetId: f.targetId })),
    { ...o, outDir: o.outMode === 'folder' ? o.outDir : null },
  );
  if (!res.started) {
    state.running = false;
    for (const f of jobs) f.status = 'idle';
    toast('Una conversione è già in corso');
    render();
  }
}

api.onJobUpdate((msg) => {
  const file = state.files.find((f) => f.id === msg.id);
  if (!file) return;
  const statusChanged = file.status !== msg.status;
  file.status = msg.status;
  file.progress = msg.progress ?? null;
  if (msg.outputs) file.outputs = msg.outputs;
  if (msg.error) file.error = msg.error;
  if (msg.details) file.details = msg.details;
  updateRow(file);
  renderOverall();
  if (statusChanged) renderQueueHead();
});

api.onQueueDone(() => {
  state.running = false;
  for (const f of state.files) if (f.status === 'queued') f.status = 'idle';
  render();
});

api.onOpenFiles((paths) => addPaths(paths));

// ============ Eventi ============

$('dropzone').addEventListener('click', pickFiles);
$('add').addEventListener('click', pickFiles);
$('convert').addEventListener('click', startConversion);
$('cancel').addEventListener('click', () => api.cancel());
$('clear').addEventListener('click', () => {
  state.files = [];
  state.lastRun = null;
  state.tab = null;
  render();
});

window.addEventListener('keydown', (e) => {
  const mod = e.metaKey || e.ctrlKey;
  if (mod && e.key.toLowerCase() === 'o') {
    e.preventDefault();
    pickFiles();
  } else if (mod && e.key === 'Enter') {
    e.preventDefault();
    startConversion();
  }
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
