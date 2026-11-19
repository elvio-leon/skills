/* Moviola — interfaccia, anteprima, audio, esportazione */
(function () {
'use strict';
const M = window.MV, PRE = window.PRESETS, { W, H } = M;
const $ = s => document.querySelector(s);
const el = (tag, attrs = {}, ...kids) => { const e = document.createElement(tag); for (const [k, v] of Object.entries(attrs)) { if (k === 'class') e.className = v; else if (k === 'text') e.textContent = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (v !== false && v != null) e.setAttribute(k, v === true ? '' : v); } kids.flat().forEach(c => c != null && e.append(c)); return e; };
const store = { get(k, d) { try { const v = localStorage.getItem('moviola:' + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem('moviola:' + k, JSON.stringify(v)); } catch (e) { } } };
const CATS = ['Titoli', 'Informazioni', 'Dati', 'Tattica', 'Transizioni', 'Texture', 'Camera'];
const CAT_NOTE = { Titoli: 'Aperture, capitoli, citazioni', Informazioni: 'Nomi, luoghi, protagonisti', Dati: 'Numeri, risultati, classifiche', Tattica: 'Lavagna e mappe', Transizioni: 'Stacchi tra due clip', Texture: 'Strati da tenere sopra', Camera: 'Movimenti sulle tue foto' };

/* ---------- stato ---------- */
const S = {
  id: store.get('preset', 'apertura'), vals: {}, t: 0, playing: false, loop: true, audio: store.get('audio', true),
  bg: store.get('bg', 'Scacchiera'), safe: false, media: null, activePoint: 'punto',
  fps: store.get('fps', 25), res: store.get('res', '1080p'), fmt: store.get('fmt', 'mp4'), outBg: store.get('outBg', 'Nero'), withAudio: store.get('withAudio', true)
};
const byId = id => PRE.find(p => p.id === id) || PRE[0];
/* passaggio al look HD: azzera una volta sola grana, vignetta e polvere salvate in precedenza */
try { if (!store.get('hd', false)) { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (!/^moviola:v:/.test(k) || /:o-/.test(k)) continue; const v = JSON.parse(localStorage.getItem(k) || '{}'); if ('grana' in v) v.grana = 0; if ('vignetta' in v) v.vignetta = 0; if ('polvere' in v) v.polvere = false; localStorage.setItem(k, JSON.stringify(v)); } store.set('hd', true); } } catch (e) { }
function defaults(p) { const v = { durata: p.dur }; p.params.forEach(q => { if (q.type !== 'info') v[q.k] = Array.isArray(q.def) ? q.def.slice() : q.def; }); return v; }
function valsOf(p) { if (!S.vals[p.id]) S.vals[p.id] = Object.assign(defaults(p), store.get('v:' + p.id, {})); return S.vals[p.id]; }
const cur = () => byId(S.id);
const dur = () => +valsOf(cur()).durata || cur().dur;

/* ---------- motore di rendering ---------- */
const layers = [];
function makeEnv(ctx, scale, fps) {
  let li = 0;
  return {
    scale, fps, media: S.media ? S.media.el : null, mediaKey: S.media ? S.media.key : null,
    layer() {
      const cw = ctx.canvas.width, ch = ctx.canvas.height; let c = layers[li]; if (!c) { c = M.mk(cw, ch); layers[li] = c; } li++;
      if (c.width !== cw || c.height !== ch) { c.width = cw; c.height = ch; }
      const g = c.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.globalAlpha = 1; g.globalCompositeOperation = 'source-over'; g.filter = 'none'; g.clearRect(0, 0, cw, ch); g.setTransform(ctx.getTransform()); return g;
    },
    flush(g) { li = Math.max(0, li - 1); ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.drawImage(g.canvas, 0, 0); ctx.restore(); }
  };
}
function drawBg(ctx, kind, scale) {
  ctx.save(); ctx.setTransform(scale, 0, 0, scale, 0, 0);
  if (kind === 'Verde campo') { const g = ctx.createRadialGradient(W / 2, H * .45, 40, W / 2, H * .5, W * .62); g.addColorStop(0, '#1d4537'); g.addColorStop(.55, M.PAL.verde); g.addColorStop(1, M.PAL.verdeScuro); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }
  else if (kind === 'Nero') { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); }
  else if (kind === 'Grigio 50%') { ctx.fillStyle = '#808080'; ctx.fillRect(0, 0, W, H); }
  else if (kind === 'Verde chroma') { ctx.fillStyle = '#00b140'; ctx.fillRect(0, 0, W, H); }
  else if (kind === 'Il tuo materiale') { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); M.cover(ctx, S.media ? S.media.el : M.samplePhoto(), 0, 0, W, H); }
  ctx.restore();
}
function render(ctx, p, t, vals, scale, bg, fps = 25) {
  ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; ctx.filter = 'none';
  ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
  if (bg && bg !== 'Scacchiera' && bg !== 'Trasparente') drawBg(ctx, bg, scale);
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  const D = +vals.durata || p.dur;
  ctx.save();
  try { p.draw(ctx, Math.max(0, Math.min(D - 1e-4, t)), D, vals, makeEnv(ctx, scale, fps)); } catch (e) { console.error(p.id, e); }
  ctx.restore();
}

/* ---------- anteprima ---------- */
const cv = $('#stage'), cx = cv.getContext('2d');
let dirty = true, lastTs = 0;
function sizeStage() {
  const r = cv.getBoundingClientRect(); const dpr = Math.min(2, window.devicePixelRatio || 1);
  const w = Math.max(320, Math.min(1920, Math.round(r.width * dpr))); const h = Math.round(w * 9 / 16);
  if (cv.width !== w) { cv.width = w; cv.height = h; dirty = true; }
}
function frame(ts) {
  const dt = lastTs ? (ts - lastTs) / 1000 : 0; lastTs = ts;
  if (S.playing) {
    S.t += dt; const D = dur();
    if (S.t >= D) { if (S.loop) { S.t = S.t % D; restartAudio(); } else { S.t = D - 1e-3; pause(); } }
    syncVideo(); dirty = true;
  }
  if (dirty) {
    dirty = false; sizeStage(); const p = cur();
    const pm = S.pointMode && !S.playing && p.params.some(q => q.type === 'point');
    $('#markers').hidden = !pm; $('#stagewrap').classList.toggle('pointmode', pm);
    if (pm) { cx.setTransform(1, 0, 0, 1, 0, 0); cx.clearRect(0, 0, cv.width, cv.height); drawBg(cx, 'Il tuo materiale', cv.width / W); cx.fillStyle = 'rgba(0,0,0,.25)'; cx.fillRect(0, 0, cv.width, cv.height); }
    else render(cx, p, S.t, valsOf(p), cv.width / W, S.bg === 'Il tuo materiale' && !p.media ? 'Il tuo materiale' : (S.bg === 'Scacchiera' ? null : S.bg), +S.fps);
    updateTransport();
  }
  requestAnimationFrame(frame);
}
function syncVideo() {
  const m = S.media; if (!m || m.type !== 'video') return; const v = m.el;
  if (S.playing) { if (v.paused) v.play().catch(() => { }); if (Math.abs(v.currentTime - S.t % (v.duration || 1e9)) > .25) v.currentTime = S.t % (v.duration || 1e9); }
}
function seek(t) { S.t = Math.max(0, Math.min(dur() - 1e-3, t)); dirty = true; if (S.media && S.media.type === 'video') { const v = S.media.el; v.currentTime = S.t % (v.duration || 1e9); } if (S.playing) restartAudio(); }
function play() { if (S.t >= dur() - .02) S.t = 0; S.playing = true; lastTs = 0; restartAudio(); $('#play').setAttribute('aria-label', 'Pausa'); $('#play').innerHTML = ICON.pause; if (S.media && S.media.type === 'video') S.media.el.play().catch(() => { }); }
function pause() { S.playing = false; stopAudio(); $('#play').setAttribute('aria-label', 'Riproduci'); $('#play').innerHTML = ICON.play; if (S.media && S.media.type === 'video') S.media.el.pause(); dirty = true; }
const fmtTC = (t, fps) => { const f = Math.floor(t * fps + 1e-6); const ff = f % fps, s = Math.floor(f / fps); return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}:${String(ff).padStart(2, '0')}`; };
function updateTransport() {
  const D = dur(), fps = +S.fps; $('#tc').textContent = fmtTC(S.t, fps); $('#tcd').textContent = fmtTC(D, fps);
  const sc = $('#scrub'); sc.max = D; sc.value = S.t; sc.style.setProperty('--p', (S.t / D * 100).toFixed(2) + '%');
}

/* ---------- audio di anteprima ---------- */
let actx = null, abuf = null, asrc = null, audioJob = 0;
async function buildAudio() {
  const p = cur(), v = valsOf(p), D = dur(); const job = ++audioJob;
  let cues = []; try { cues = (p.sfx ? p.sfx.call(p, v, D) : []) || []; } catch (e) { cues = []; }
  const b = await M.SFX.render(cues, D).catch(() => null); if (job !== audioJob) return; abuf = b; if (S.playing) restartAudio();
}
let audioTimer = 0; const rebuildAudio = () => { clearTimeout(audioTimer); audioTimer = setTimeout(buildAudio, 250); };
function stopAudio() { if (asrc) { try { asrc.stop(); } catch (e) { } asrc = null; } }
function restartAudio() {
  stopAudio(); if (!S.audio || !S.playing || !abuf) return;
  try { if (!actx) actx = new (window.AudioContext || window.webkitAudioContext)(); if (actx.state === 'suspended') actx.resume(); asrc = actx.createBufferSource(); asrc.buffer = abuf; asrc.connect(actx.destination); asrc.start(0, Math.min(S.t, abuf.duration - .01)); } catch (e) { }
}

/* ---------- icone ---------- */
const svg = d => `<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ICON = {
  play: svg('<path d="M7 5l12 7-12 7z" fill="currentColor"/>'), pause: svg('<path d="M8 5v14M16 5v14" stroke-width="3"/>'),
  prev: svg('<path d="M15 6l-6 6 6 6"/>'), next: svg('<path d="M9 6l6 6-6 6"/>'), loop: svg('<path d="M4 12a7 7 0 0 1 12-5l2 2M20 12a7 7 0 0 1-12 5l-2-2"/><path d="M18 4v5h-5M6 20v-5h5"/>'),
  sound: svg('<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>'), mute: svg('<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M17 9l5 6M22 9l-5 6"/>'),
  safe: svg('<rect x="3" y="5" width="18" height="14"/><rect x="6" y="8" width="12" height="8" stroke-dasharray="2 2"/>'), up: svg('<path d="M12 16V4M7 9l5-5 5 5M4 20h16"/>'), x: svg('<path d="M6 6l12 12M18 6L6 18"/>'),
  down: svg('<path d="M12 4v12M7 11l5 5 5-5M4 20h16"/>')
};

/* ---------- libreria ---------- */
const thumbs = new Map();
function buildLibrary() {
  const lib = $('#library'); lib.innerHTML = '';
  CATS.forEach(cat => {
    const items = PRE.filter(p => p.cat === cat); if (!items.length) return;
    const sec = el('section', { class: 'cat' }, el('h3', {}, el('span', { text: cat }), el('small', { text: items.length })), el('p', { class: 'catnote', text: CAT_NOTE[cat] }));
    const ul = el('ul', { class: 'items' });
    items.forEach(p => {
      const c = el('canvas', { width: 192, height: 108, 'aria-hidden': 'true' }); thumbs.set(p.id, c);
      const btn = el('button', { class: 'item' + (p.id === S.id ? ' on' : ''), type: 'button', 'data-id': p.id, 'aria-pressed': p.id === S.id ? 'true' : 'false', onclick: () => select(p.id) },
        el('span', { class: 'thumb' }, c), el('span', { class: 'meta' }, el('b', { text: p.name }), el('small', { text: (p.kind === 'transition' ? 'Transizione' : p.kind === 'loop' ? 'In loop' : p.media ? 'Usa il tuo materiale' : 'Grafica') + ' · ' + String(p.dur).replace('.', ',') + ' s' })));
      btn.addEventListener('mouseenter', () => hoverThumb(p, c, true)); btn.addEventListener('mouseleave', () => hoverThumb(p, c, false));
      ul.append(el('li', {}, btn));
    });
    sec.append(ul); lib.append(sec);
  });
}
function drawThumb(p, c, t) { const g = c.getContext('2d'); render(g, p, t, valsOf(p), c.width / W, p.kind === 'transition' || p.kind === 'loop' || ['sottopancia', 'luogo', 'macchina'].includes(p.id) ? 'Il tuo materiale' : null, 25); }
let hoverRaf = 0;
function hoverThumb(p, c, on) {
  cancelAnimationFrame(hoverRaf); if (!on) { drawThumb(p, c, p.thumbT); return; }
  const t0 = performance.now(); const D = p.dur; const step = () => { drawThumb(p, c, ((performance.now() - t0) / 1000) % D); hoverRaf = requestAnimationFrame(step); }; step();
}
function renderThumbs() { const list = PRE.slice(); const next = () => { const p = list.shift(); if (!p) return; const c = thumbs.get(p.id); if (c) drawThumb(p, c, p.thumbT ?? p.dur / 2); setTimeout(next, 16); }; next(); }

function select(id) {
  if (S.playing) pause(); S.id = id; store.set('preset', id); S.t = Math.min(byId(id).thumbT ?? 0, dur() - .01); S.activePoint = 'punto';
  document.querySelectorAll('.item').forEach(b => { const on = b.dataset.id === id; b.classList.toggle('on', on); b.setAttribute('aria-pressed', on ? 'true' : 'false'); });
  buildInspector(); buildInfo(); rebuildAudio(); dirty = true; clearReady();
}

/* ---------- pannello informazioni ---------- */
function buildInfo() {
  const p = cur(); const box = $('#info'); box.innerHTML = '';
  const chips = [el('span', { class: 'chip', text: p.cat })];
  if (p.kind === 'transition') chips.push(el('span', { class: 'chip red', text: 'Taglio a ' + (dur() * p.cut).toFixed(2).replace('.', ',') + ' s' }));
  if (p.kind === 'loop') chips.push(el('span', { class: 'chip', text: 'Ripetibile senza stacchi' }));
  if (p.media) chips.push(el('span', { class: 'chip', text: S.media ? 'Sul tuo materiale' : 'Foto di esempio: carica la tua' }));
  box.append(el('div', { class: 'info-head' }, el('h2', { text: p.name }), el('div', { class: 'chips' }, chips)), el('p', { class: 'desc', text: p.desc }),
    el('div', { class: 'tip' }, el('h4', { text: 'Consiglio del montatore' }), el('p', { text: p.tip })));
  const mk = $('#cutmark'); if (p.kind === 'transition') { mk.hidden = false; mk.style.left = (p.cut * 100) + '%'; } else mk.hidden = true;
}

/* ---------- ispettore ---------- */
function control(p, q, v, onChange) {
  const id = 'f-' + p.id + '-' + q.k; const lab = el('label', { for: id, text: q.label });
  const set = (val, rerender = false) => { v[q.k] = val; store.set('v:' + p.id, v); onChange(q, rerender); };
  if (q.type === 'text') return el('div', { class: 'field' }, lab, el('input', { id, class: 'inp', type: 'text', value: v[q.k], oninput: e => set(e.target.value) }));
  if (q.type === 'textarea') return el('div', { class: 'field' }, lab, el('textarea', { id, class: 'inp', rows: Math.min(8, Math.max(2, String(v[q.k]).split('\n').length + 1)), oninput: e => set(e.target.value) }, String(v[q.k])));
  if (q.type === 'select') { const s = el('select', { id, class: 'inp', onchange: e => set(e.target.value) }, q.opts.map(o => el('option', { value: o, selected: o === v[q.k] }, o))); return el('div', { class: 'field' }, lab, s); }
  if (q.type === 'range') {
    const out = el('output', { for: id, text: fmtNum(v[q.k], q.step) });
    return el('div', { class: 'field' }, el('div', { class: 'row' }, lab, out), el('input', { id, type: 'range', min: q.min, max: q.max, step: q.step, value: v[q.k], oninput: e => { out.textContent = fmtNum(+e.target.value, q.step); set(+e.target.value); } }));
  }
  if (q.type === 'bool') return el('div', { class: 'field check' }, el('input', { id, type: 'checkbox', checked: !!v[q.k], onchange: e => set(e.target.checked) }), lab);
  if (q.type === 'color') {
    const inp = el('input', { id, type: 'color', value: v[q.k], oninput: e => { set(e.target.value); mark(); } });
    const sw = el('div', { class: 'swatches', role: 'group', 'aria-label': q.label });
    const mark = () => sw.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.c.toLowerCase() === String(v[q.k]).toLowerCase() ? 'true' : 'false'));
    M.SWATCHES.forEach(([n, c]) => sw.append(el('button', { type: 'button', class: 'sw', 'data-c': c, style: `--c:${c}`, 'aria-label': n, title: n, onclick: () => { inp.value = c; set(c); mark(); } })));
    mark(); return el('div', { class: 'field' }, el('div', { class: 'row' }, lab, inp), sw);
  }
  if (q.type === 'point') {
    const rb = el('input', { type: 'radio', name: 'pt-' + p.id, id: id + '-r', checked: S.activePoint === q.k, onchange: () => { S.activePoint = q.k; dirty = true; drawMarkers(); } });
    const out = el('output', { text: `${Math.round(v[q.k][0] * 100)}% · ${Math.round(v[q.k][1] * 100)}%` });
    return el('div', { class: 'field check pt' }, rb, el('label', { for: id + '-r', text: q.label }), out);
  }
  return null;
}
const fmtNum = (n, st) => (+n).toFixed(st < .1 ? 2 : st < 1 ? (st < .5 ? 2 : 1) : 0).replace('.', ',');
function buildInspector() {
  const p = cur(), v = valsOf(p); const f = $('#params'); f.innerHTML = '';
  const onChange = (q, re) => { dirty = true; rebuildAudio(); clearReady(); if (q && q.k === 'durata') { buildInfo(); } if (q && q.type === 'point') buildInspector(); };
  const dq = { k: 'durata', label: 'Durata (secondi)', type: 'range', min: p.kind === 'transition' ? .4 : 1, max: p.kind === 'loop' ? 30 : 20, step: .1 };
  f.append(control(p, dq, v, onChange));
  p.params.forEach(q => { const c = control(p, q, v, onChange); if (c) f.append(c); });
  const pts = p.params.filter(q => q.type === 'point');
  if (pts.length && !pts.some(q => q.k === S.activePoint)) S.activePoint = pts[0].k;
  $('#pointhint').hidden = !pts.length; drawMarkers();
  buildVariants();
}
/* versioni salvate */
function buildVariants() {
  const p = cur(); const box = $('#variants'); box.innerHTML = ''; const list = store.get('var:' + p.id, []);
  const name = el('input', { id: 'varname', class: 'inp', type: 'text', placeholder: 'Nome della versione, es. "Intro Capitolo 1"' });
  box.append(el('div', { class: 'field' }, el('label', { for: 'varname', text: 'Salva questa impostazione come tua versione' }), el('div', { class: 'row gap' }, name, el('button', { type: 'button', class: 'btn sm', onclick: () => { const n = name.value.trim() || ('Versione ' + (list.length + 1)); list.push({ n, v: JSON.parse(JSON.stringify(valsOf(p))) }); store.set('var:' + p.id, list); buildVariants(); toast('Versione salvata: ' + n); } }, 'Salva'))));
  if (list.length) box.append(el('ul', { class: 'vlist' }, list.map((it, i) => el('li', {}, el('button', { type: 'button', class: 'linkish', onclick: () => { S.vals[p.id] = Object.assign(defaults(p), it.v); store.set('v:' + p.id, S.vals[p.id]); buildInspector(); buildInfo(); rebuildAudio(); dirty = true; toast('Applicata: ' + it.n); } }, it.n), el('button', { type: 'button', class: 'icon sm', 'aria-label': 'Elimina ' + it.n, onclick: () => { list.splice(i, 1); store.set('var:' + p.id, list); buildVariants(); } }, el('span', { class: 'ic' }))))));
  box.querySelectorAll('.ic').forEach(s => s.innerHTML = ICON.x);
  box.append(el('button', { type: 'button', class: 'linkish', onclick: () => { S.vals[p.id] = defaults(p); store.set('v:' + p.id, {}); buildInspector(); buildInfo(); rebuildAudio(); dirty = true; } }, 'Ripristina i valori predefiniti'));
}

/* ---------- punti sull'anteprima ---------- */
function drawMarkers() {
  const lay = $('#markers'); lay.innerHTML = ''; const p = cur(); const v = valsOf(p); $('#stagewrap').classList.toggle('has-point', p.params.some(q => q.type === 'point'));
  p.params.filter(q => q.type === 'point').forEach(q => { const m = el('span', { class: 'pm' + (q.k === S.activePoint ? ' on' : ''), style: `left:${v[q.k][0] * 100}%;top:${v[q.k][1] * 100}%` }, el('i', { text: q.k === 'punto2' ? 'B' : (p.params.filter(x => x.type === 'point').length > 1 ? 'A' : '') })); lay.append(m); });
}
let pmTimer = 0; const sw = $('#stagewrap');
const hasPts = () => cur().params.some(q => q.type === 'point');
sw.addEventListener('pointerenter', e => { if (e.pointerType === 'mouse' && hasPts()) { S.pointMode = true; dirty = true; } });
sw.addEventListener('pointerleave', e => { if (e.pointerType === 'mouse') { S.pointMode = false; dirty = true; } });
sw.addEventListener('pointerdown', e => { if (e.pointerType !== 'mouse' && hasPts()) { S.pointMode = true; dirty = true; clearTimeout(pmTimer); pmTimer = setTimeout(() => { S.pointMode = false; dirty = true; }, 2500); } });
sw.addEventListener('click', e => {
  const p = cur(); const q = p.params.find(x => x.k === S.activePoint && x.type === 'point'); if (!q) return;
  if (S.playing) pause(); S.pointMode = true;
  const r = cv.getBoundingClientRect(); const u = M.clamp((e.clientX - r.left) / r.width), w = M.clamp((e.clientY - r.top) / r.height);
  const v = valsOf(p); v[q.k] = [+u.toFixed(3), +w.toFixed(3)]; store.set('v:' + p.id, v); dirty = true; buildInspector();
});

/* ---------- materiale dell'utente ---------- */
function setMedia(file) {
  if (!file) return; const isV = /^video\//.test(file.type) || /\.(mp4|mov|webm|m4v)$/i.test(file.name); const url = URL.createObjectURL(file);
  const done = (elm, type) => { if (S.media && S.media.url) URL.revokeObjectURL(S.media.url); S.media = { el: elm, type, url, name: file.name, key: file.name + ':' + file.size + ':' + Date.now() }; for (const k of [...M.cache.keys()]) if (/^(tone|ht|page):/.test(k)) M.cache.delete(k); mediaUI(); buildInfo(); dirty = true; renderThumbs(); toast('Materiale caricato: ' + file.name); };
  if (isV) { const v = document.createElement('video'); v.muted = true; v.playsInline = true; v.loop = true; v.preload = 'auto'; v.src = url; v.addEventListener('loadeddata', () => done(v, 'video'), { once: true }); v.addEventListener('error', () => toast('Questo video non si apre nel browser. Prova MP4 (H.264) o WebM.'), { once: true }); v.addEventListener('seeked', () => { dirty = true; }); }
  else { const im = new Image(); im.onload = () => done(im, 'image'); im.onerror = () => toast('Questa immagine non si apre. Prova JPG o PNG.'); im.src = url; }
}
function mediaUI() {
  const box = $('#mediabox'); const m = S.media;
  $('#medianame').textContent = m ? m.name : 'Nessun file: i preset "Camera" usano una foto di esempio';
  $('#mediaclear').hidden = !m; box.classList.toggle('has', !!m);
  const th = $('#mediathumb'); const g = th.getContext('2d'); g.clearRect(0, 0, th.width, th.height); M.cover(g, m ? m.el : M.samplePhoto(), 0, 0, th.width, th.height);
}
$('#mediafile').addEventListener('change', e => { setMedia(e.target.files[0]); e.target.value = ''; });
$('#mediaclear').addEventListener('click', () => { if (S.media && S.media.url) URL.revokeObjectURL(S.media.url); S.media = null; for (const k of [...M.cache.keys()]) if (/^(tone|ht|page):/.test(k)) M.cache.delete(k); mediaUI(); buildInfo(); renderThumbs(); dirty = true; });
['dragenter', 'dragover'].forEach(t => document.addEventListener(t, e => { if (e.dataTransfer && [...e.dataTransfer.types].includes('Files')) { e.preventDefault(); document.body.classList.add('dragging'); } }));
['dragleave', 'drop'].forEach(t => document.addEventListener(t, e => { if (t === 'dragleave' && e.relatedTarget) return; document.body.classList.remove('dragging'); }));
document.addEventListener('drop', e => { if (e.dataTransfer && e.dataTransfer.files.length) { e.preventDefault(); setMedia(e.dataTransfer.files[0]); } });

/* ---------- trasporto ---------- */
$('#play').addEventListener('click', () => S.playing ? pause() : play());
$('#prev').addEventListener('click', () => { if (S.playing) pause(); seek(S.t - 1 / S.fps); });
$('#next').addEventListener('click', () => { if (S.playing) pause(); seek(S.t + 1 / S.fps); });
$('#scrub').addEventListener('input', e => seek(+e.target.value));
$('#loop').addEventListener('click', e => { S.loop = !S.loop; e.currentTarget.setAttribute('aria-pressed', S.loop); });
$('#snd').addEventListener('click', e => { S.audio = !S.audio; store.set('audio', S.audio); e.currentTarget.setAttribute('aria-pressed', S.audio); e.currentTarget.innerHTML = S.audio ? ICON.sound : ICON.mute; if (S.audio) restartAudio(); else stopAudio(); });
$('#safe').addEventListener('click', e => { S.safe = !S.safe; e.currentTarget.setAttribute('aria-pressed', S.safe); $('#safeov').hidden = !S.safe; });
$('#bgsel').addEventListener('change', e => { S.bg = e.target.value; store.set('bg', S.bg); $('#stagewrap').classList.toggle('checker', S.bg === 'Scacchiera'); dirty = true; });
document.addEventListener('keydown', e => {
  if (e.target.closest('input, textarea, select, [contenteditable]')) return;
  if (e.code === 'Space' && e.target === document.body) { e.preventDefault(); S.playing ? pause() : play(); }
  else if (e.key === 'ArrowLeft' && e.target === document.body) { if (S.playing) pause(); seek(S.t - 1 / S.fps); }
  else if (e.key === 'ArrowRight' && e.target === document.body) { if (S.playing) pause(); seek(S.t + 1 / S.fps); }
});

/* ---------- toast ---------- */
let toastT = 0; function toast(msg) { const t = $('#toast'); t.textContent = msg; t.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => { t.hidden = true; }, 3600); }

/* ---------- salvataggio file ---------- */
let dl = null; try { (window.claude && window.claude.use ? window.claude.use('downloads') : Promise.resolve(null)).then(x => { dl = x; }).catch(() => { }); } catch (e) { }
async function saveFile(name, blob) {
  if (dl) { try { await dl.save({ filename: name, data: blob }); toast('File salvato: ' + name); return; } catch (e) { if (e && e.code === 'declined') { toast('Salvataggio annullato.'); return; } if (e && e.code === 'rate_limited') { toast('C\'è già una richiesta di salvataggio aperta.'); return; } } }
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 60000);
}

/* ---------- esportazione ---------- */
const RES = { '1080p': 1920, '1440p': 2560, '4K': 3840 };
let ready = null, cancel = false, busy = false;
function clearReady() { ready = null; $('#savebtn').hidden = true; $('#exportmsg').textContent = ''; }
function slug(s) { return String(s).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40); }
async function pickH264(w, h, fps, br) {
  if (!window.VideoEncoder) return null;
  for (const codec of ['avc1.640034', 'avc1.640033', 'avc1.640032', 'avc1.640028', 'avc1.4d0034', 'avc1.4d0028', 'avc1.42e034', 'avc1.42e028']) {
    const c = { codec, width: w, height: h, bitrate: br, framerate: fps, avc: { format: 'avc' }, latencyMode: 'quality' };
    try { if ((await VideoEncoder.isConfigSupported(c)).supported) return c; } catch (e) { }
  } return null;
}
async function pickVP9(w, h, fps, br, alpha) {
  if (!window.VideoEncoder) return null;
  for (const codec of ['vp09.00.51.08', 'vp09.00.41.08', 'vp09.00.40.08', 'vp09.00.31.08', 'vp8']) {
    const c = { codec, width: w, height: h, bitrate: br, framerate: fps, latencyMode: 'quality' }; if (alpha) c.alpha = 'keep';
    try { const r = await VideoEncoder.isConfigSupported(c); if (r.supported && (!alpha || r.config.alpha === 'keep')) return c; } catch (e) { }
  } return null;
}
async function pickAudio(container) {
  if (!window.AudioEncoder) return null;
  const opts = container === 'mp4' ? [['aac', 'mp4a.40.2'], ['opus', 'opus']] : [['A_OPUS', 'opus']];
  for (const [mux, codec] of opts) { const c = { codec, sampleRate: 48000, numberOfChannels: 2, bitrate: 192000 }; try { if ((await AudioEncoder.isConfigSupported(c)).supported) return { mux, cfg: c }; } catch (e) { } }
  return null;
}
async function encodeAudio(buf, a, muxer) {
  const enc = new AudioEncoder({ output: (ch, meta) => muxer.addAudioChunk(ch, meta), error: e => console.error(e) }); enc.configure(a.cfg);
  const n = buf.length, CH = 2, block = 4800; const L = buf.getChannelData(0), R = buf.numberOfChannels > 1 ? buf.getChannelData(1) : L;
  for (let i = 0; i < n; i += block) { const len = Math.min(block, n - i); const data = new Float32Array(len * CH); data.set(L.subarray(i, i + len), 0); data.set(R.subarray(i, i + len), len); const ad = new AudioData({ format: 'f32-planar', sampleRate: 48000, numberOfFrames: len, numberOfChannels: CH, timestamp: Math.round(i / 48000 * 1e6), data }); enc.encode(ad); ad.close(); }
  await enc.flush(); enc.close();
}
async function seekVideo(v, t) { if (!v || !(v instanceof HTMLVideoElement)) return; const tt = v.duration ? t % v.duration : t; if (Math.abs(v.currentTime - tt) < 1e-3 && v.readyState >= 2) return; await new Promise(res => { const done = () => { v.removeEventListener('seeked', done); res(); }; v.addEventListener('seeked', done); v.currentTime = tt; setTimeout(done, 1500); }); }
function progress(k, label) { $('#bar').style.setProperty('--p', (k * 100).toFixed(1) + '%'); $('#exportmsg').textContent = label; }

async function doExport() {
  if (busy) { cancel = true; return; }
  const p = cur(), v = JSON.parse(JSON.stringify(valsOf(p))), D = +v.durata || p.dur; const fps = +S.fps; const w = RES[S.res], h = Math.round(w * 9 / 16); const scale = w / W;
  const fmt = S.fmt; const N = Math.max(1, Math.round(D * fps)); const base = `${slug(p.name)}-${slug(v.titolo || v.nome || v.testo || v.luogo || v.parole || '') || 'moviola'}`.replace(/-+$/, '');
  if (S.playing) pause();
  busy = true; cancel = false; clearReady(); $('#exportbtn').textContent = 'Annulla'; $('#exportbtn').classList.add('busy'); $('#bar').hidden = false;
  const transparentOut = fmt === 'webm' || fmt === 'png' || fmt === 'matte' || fmt === 'frame';
  const outBg = transparentOut ? null : (p.media ? null : S.outBg);
  const c = M.mk(w, h); const g = c.getContext('2d', { alpha: true, willReadFrequently: false });
  const vid = S.media && S.media.type === 'video' ? S.media.el : null; const wasPlaying = vid && !vid.paused; if (vid) vid.pause();
  try {
    await M.loadFonts();
    if (fmt === 'frame') {
      await seekVideo(vid, S.t); render(g, p, S.t, v, scale, null, fps);
      const blob = await new Promise(r => c.toBlob(r, 'image/png')); ready = { name: `${base}-${fmtTC(S.t, fps).replace(/:/g, '')}.png`, blob }; return;
    }
    let audioBuf = null;
    if (S.withAudio && fmt !== 'png') { try { audioBuf = await M.SFX.render(p.sfx ? p.sfx.call(p, v, D) : [], D); } catch (e) { audioBuf = null; } }
    if (fmt === 'png') {
      const parts = []; const zip = new fflate.Zip((err, dat) => { if (!err) parts.push(dat); });
      for (let i = 0; i < N; i++) {
        if (cancel) throw new Error('annullato');
        await seekVideo(vid, i / fps); render(g, p, i / fps, v, scale, null, fps);
        const b = await new Promise(r => c.toBlob(r, 'image/png')); const f = new fflate.ZipPassThrough(`${base}/${base}_${String(i).padStart(5, '0')}.png`); zip.add(f); f.push(new Uint8Array(await b.arrayBuffer()), true);
        progress((i + 1) / N, `Fotogramma ${i + 1} di ${N}`); await new Promise(r => setTimeout(r, 0));
      }
      zip.end(); ready = { name: `${base}-png-${fps}fps.zip`, blob: new Blob(parts, { type: 'application/zip' }) }; return;
    }
    const br = Math.round((w * h * fps) * (S.res === '4K' ? .26 : .34));
    let vcfg, container, muxer, matteMuxer = null, matteEnc = null, mc = null;
    if (fmt === 'webm') {
      vcfg = await pickVP9(w, h, fps, br, true); container = 'webm';
      if (!vcfg) throw new Error('Il tuo browser non sa codificare video con trasparenza. Usa la sequenza PNG o "MP4 + maschera".');
    } else {
      vcfg = await pickH264(w, h, fps, br); container = 'mp4';
      if (!vcfg) { vcfg = await pickVP9(w, h, fps, br, false); container = 'webm'; if (!vcfg) throw new Error('Questo browser non può creare video. Usa Chrome o Edge aggiornati, oppure la sequenza PNG.'); toast('Il browser non codifica H.264: esporto in WebM.'); }
    }
    const a = audioBuf ? await pickAudio(container) : null;
    const mkMuxer = (withAudio, alpha) => container === 'mp4'
      ? new Mp4Muxer.Muxer({ target: new Mp4Muxer.ArrayBufferTarget(), video: { codec: vcfg.codec.startsWith('avc') ? 'avc' : 'vp9', width: w, height: h, frameRate: fps }, audio: withAudio && a ? { codec: a.mux, numberOfChannels: 2, sampleRate: 48000 } : undefined, fastStart: 'in-memory', firstTimestampBehavior: 'offset' })
      : new WebMMuxer.Muxer({ target: new WebMMuxer.ArrayBufferTarget(), video: { codec: vcfg.codec.startsWith('vp8') ? 'V_VP8' : 'V_VP9', width: w, height: h, frameRate: fps, alpha: !!alpha }, audio: withAudio && a ? { codec: 'A_OPUS', numberOfChannels: 2, sampleRate: 48000 } : undefined, firstTimestampBehavior: 'offset' });
    muxer = mkMuxer(true, fmt === 'webm');
    let err = null; const enc = new VideoEncoder({ output: (ch, meta) => muxer.addVideoChunk(ch, meta), error: e => { err = e; } }); enc.configure(vcfg);
    let flat = null;
    if (fmt === 'matte') { matteMuxer = mkMuxer(false, false); matteEnc = new VideoEncoder({ output: (ch, meta) => matteMuxer.addVideoChunk(ch, meta), error: e => { err = e; } }); matteEnc.configure(vcfg); mc = M.mk(w, h); flat = M.mk(w, h); }
    else if (container === 'mp4' || !vcfg.alpha) flat = M.mk(w, h);
    const fg = flat && flat.getContext('2d'), mg = mc && mc.getContext('2d');
    for (let i = 0; i < N; i++) {
      if (cancel) throw new Error('annullato'); if (err) throw err;
      const t = i / fps; await seekVideo(vid, t);
      render(g, p, t, v, scale, outBg, fps);
      let src = c;
      if (fg) { fg.globalCompositeOperation = 'source-over'; fg.fillStyle = '#000'; fg.fillRect(0, 0, w, h); fg.drawImage(c, 0, 0); src = flat; }
      const ts = Math.round(i * 1e6 / fps), d = Math.round(1e6 / fps); const key = i % (fps * 2) === 0;
      const vf = new VideoFrame(src, { timestamp: ts, duration: d, alpha: vcfg.alpha === 'keep' ? 'keep' : 'discard' }); enc.encode(vf, { keyFrame: key }); vf.close();
      if (mg) { mg.globalCompositeOperation = 'source-over'; mg.clearRect(0, 0, w, h); mg.drawImage(c, 0, 0); mg.globalCompositeOperation = 'source-in'; mg.fillStyle = '#fff'; mg.fillRect(0, 0, w, h); mg.globalCompositeOperation = 'destination-over'; mg.fillStyle = '#000'; mg.fillRect(0, 0, w, h); const mf = new VideoFrame(mc, { timestamp: ts, duration: d }); matteEnc.encode(mf, { keyFrame: key }); mf.close(); }
      while (enc.encodeQueueSize > 6 || (matteEnc && matteEnc.encodeQueueSize > 6)) await new Promise(r => setTimeout(r, 4));
      progress((i + 1) / N * .97, `Fotogramma ${i + 1} di ${N}`); if (i % 2 === 0) await new Promise(r => setTimeout(r, 0));
    }
    await enc.flush(); enc.close(); if (matteEnc) { await matteEnc.flush(); matteEnc.close(); }
    if (audioBuf && a) { progress(.98, 'Codifica audio…'); await encodeAudio(audioBuf, a, muxer); }
    muxer.finalize(); const ext = container;
    const main = new Blob([muxer.target.buffer], { type: container === 'mp4' ? 'video/mp4' : 'video/webm' });
    if (fmt === 'matte') {
      matteMuxer.finalize(); const parts = []; const zip = new fflate.Zip((e2, dat) => { if (!e2) parts.push(dat); });
      const add = async (n, b) => { const f = new fflate.ZipPassThrough(n); zip.add(f); f.push(new Uint8Array(await b.arrayBuffer()), true); };
      await add(`${base}_colore.${ext}`, main); await add(`${base}_maschera.${ext}`, new Blob([matteMuxer.target.buffer])); zip.end();
      ready = { name: `${base}-con-maschera.zip`, blob: new Blob(parts, { type: 'application/zip' }) };
    } else ready = { name: `${base}-${S.res}-${fps}fps${fmt === 'webm' ? '-trasparente' : ''}.${ext}`, blob: main };
    if (audioBuf && !a) toast('Audio non incluso: il browser non sa codificarlo. Scarica gli effetti sonori a parte.');
  } catch (e) {
    ready = null; $('#exportmsg').textContent = e.message === 'annullato' ? 'Esportazione annullata.' : ('Errore: ' + (e.message || e));
  } finally {
    busy = false; $('#exportbtn').textContent = 'Esporta'; $('#exportbtn').classList.remove('busy'); $('#bar').hidden = true; if (vid && wasPlaying) vid.play().catch(() => { }); dirty = true;
    if (ready) { $('#exportmsg').textContent = `Pronto: ${ready.name} · ${(ready.blob.size / 1048576).toFixed(1).replace('.', ',')} MB`; const b = $('#savebtn'); b.hidden = false; b.textContent = 'Salva il file'; b.focus(); }
  }
}
$('#exportbtn').addEventListener('click', doExport);
$('#savebtn').addEventListener('click', () => { if (ready) saveFile(ready.name, ready.blob); });
$('#sfxbtn').addEventListener('click', async () => {
  const p = cur(), v = valsOf(p), D = dur(); const cues = p.sfx ? p.sfx.call(p, v, D) : []; if (!cues.length) { toast('Questo preset non ha effetti sonori.'); return; }
  const b = await M.SFX.render(cues, D); const parts = []; const zip = new fflate.Zip((e, d) => { if (!e) parts.push(d); }); const f = new fflate.ZipPassThrough(`${slug(p.name)}-effetti.wav`); zip.add(f); f.push(M.SFX.wav(b), true); zip.end();
  saveFile(`${slug(p.name)}-effetti-sonori.zip`, new Blob(parts, { type: 'application/zip' }));
});
function exportUI() {
  const sel = (id, key, cb) => { const s = $(id); s.value = S[key]; s.addEventListener('change', e => { S[key] = e.target.value; store.set(key, S[key]); clearReady(); if (cb) cb(); }); };
  sel('#fmt', 'fmt', fmtHint); sel('#res', 'res'); sel('#fps', 'fps', () => { dirty = true; }); sel('#outbg', 'outBg');
  const wa = $('#withaudio'); wa.checked = S.withAudio; wa.addEventListener('change', e => { S.withAudio = e.target.checked; store.set('withAudio', S.withAudio); });
  fmtHint();
}
function fmtHint() {
  const h = { mp4: 'Un unico file pronto per il montaggio, con l\'audio. Gli elementi senza sfondo vengono messi sullo sfondo scelto qui sotto.', matte: 'Due video nello stesso .zip: colore e maschera in bianco e nero. In Premiere usa l\'effetto "Track Matte Key", in DaVinci "Usa come maschera". Funziona in ogni programma.', webm: 'Un file con la trasparenza vera (VP9 alfa). Leggero e comodo, ma non tutti i programmi lo leggono: provalo nel tuo prima di usarlo in serie.', png: 'Una sequenza di immagini PNG con trasparenza, in un .zip. Il formato più compatibile: importa la cartella come "sequenza di immagini".', frame: 'Il fotogramma che vedi ora, in PNG trasparente, alla risoluzione scelta.' }[S.fmt];
  $('#fmthint').textContent = h; $('#outbgfield').hidden = S.fmt !== 'mp4'; $('#audiofield').hidden = S.fmt === 'png' || S.fmt === 'frame';
}

/* ---------- avvio ---------- */
(async function boot() {
  $('#play').innerHTML = ICON.play; $('#prev').innerHTML = ICON.prev; $('#next').innerHTML = ICON.next; $('#loop').innerHTML = ICON.loop; $('#safe').innerHTML = ICON.safe;
  $('#snd').innerHTML = S.audio ? ICON.sound : ICON.mute; $('#snd').setAttribute('aria-pressed', S.audio); $('#loop').setAttribute('aria-pressed', S.loop);
  $('#uplicon').innerHTML = ICON.up; $('#sfxbtn').innerHTML = ICON.down + '<span>Effetti sonori (.wav)</span>';
  $('#bgsel').value = S.bg; $('#stagewrap').classList.toggle('checker', S.bg === 'Scacchiera');
  if (!PRE.some(p => p.id === S.id)) S.id = PRE[0].id;
  $('#count').textContent = PRE.length + ' preset';
  buildLibrary(); buildInspector(); buildInfo(); exportUI(); mediaUI();
  pickVP9(1920, 1080, 25, 2e7, true).then(ok => { if (ok) return; const o = $('#fmt option[value="webm"]'); o.disabled = true; o.textContent = 'WebM con trasparenza (non disponibile in questo browser)'; if (S.fmt === 'webm') { S.fmt = 'png'; $('#fmt').value = 'png'; fmtHint(); } }).catch(() => { });
  S.t = Math.min(cur().thumbT ?? 0, dur() - .01);
  requestAnimationFrame(frame);
  await M.loadFonts(); dirty = true; renderThumbs(); mediaUI(); buildAudio();
  window.addEventListener('resize', () => { dirty = true; });
  document.fonts && document.fonts.addEventListener && document.fonts.addEventListener('loadingdone', () => { dirty = true; });
})();
window.MOVIOLA = { S, render, cur, valsOf, select, seek };
})();
