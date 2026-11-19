/* Moviola — motore di rendering. Tutto è disegnato su canvas 2D in uno spazio logico
   1920×1080 ed è funzione pura del tempo t: lo stesso fotogramma esce identico in
   anteprima e in esportazione. */
(function () {
'use strict';
const W = 1920, H = 1080;

const PAL = {
  verde: '#183A2F', verdeScuro: '#0c1f19', carta: '#F5EFE6', cartaOmbra: '#e9dfcd',
  rosso: '#B5323C', inchiostro: '#22324a', fosforo: '#7CFF9B', nero: '#0b0d0c',
  oro: '#C9A45C', ghiaccio: '#DDE6E1'
};
const SWATCHES = [
  ['Carta', PAL.carta], ['Rosso', PAL.rosso], ['Verde campo', PAL.verde], ['Inchiostro', PAL.inchiostro],
  ['Fosforo', PAL.fosforo], ['Oro', PAL.oro], ['Nero', PAL.nero], ['Bianco', '#ffffff']
];

/* ---------- matematica ---------- */
const clamp = (v, a = 0, b = 1) => v < a ? a : v > b ? b : v;
const lerp = (a, b, t) => a + (b - a) * t;
const inv = (a, b, v) => clamp((v - a) / (b - a));
const smooth = (a, b, v) => { const x = inv(a, b, v); return x * x * (3 - 2 * x); };
function bezier(x1, y1, x2, y2) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const sx = t => ((ax * t + bx) * t + cx) * t, sy = t => ((ay * t + by) * t + cy) * t;
  const dx = t => (3 * ax * t + 2 * bx) * t + cx;
  return x => {
    if (x <= 0) return 0; if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 6; i++) { const e = sx(t) - x, d = dx(t); if (Math.abs(e) < 1e-5) break; if (Math.abs(d) < 1e-6) break; t -= e / d; }
    t = clamp(t);
    return sy(t);
  };
}
const E = {
  lin: t => clamp(t),
  in2: t => clamp(t) ** 2, out2: t => 1 - (1 - clamp(t)) ** 2,
  out3: t => 1 - (1 - clamp(t)) ** 3, in3: t => clamp(t) ** 3,
  io3: t => { t = clamp(t); return t < .5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2; },
  out5: t => 1 - (1 - clamp(t)) ** 5,
  io5: t => { t = clamp(t); return t < .5 ? 16 * t ** 5 : 1 - (-2 * t + 2) ** 5 / 2; },
  outExpo: t => { t = clamp(t); return t === 1 ? 1 : 1 - Math.pow(2, -10 * t); },
  inExpo: t => { t = clamp(t); return t === 0 ? 0 : Math.pow(2, 10 * t - 10); },
  ioExpo: t => { t = clamp(t); if (t === 0 || t === 1) return t; return t < .5 ? Math.pow(2, 20 * t - 10) / 2 : (2 - Math.pow(2, -20 * t + 10)) / 2; },
  outBack: t => { t = clamp(t); const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2; },
  film: bezier(.16, .84, .24, 1),    /* uscita lunga e morbida, "80% influenza" */
  swift: bezier(.72, 0, .18, 1),     /* in-out deciso, da motion design */
  glide: bezier(.45, .05, .2, 1),
  spring: (t, f = 4.2, d = 5.2) => { t = Math.max(0, t); return 1 - Math.exp(-d * t) * Math.cos(f * Math.PI * 2 * t * .5); }
};
/* progresso di una fase: inizio, durata, curva */
const ph = (t, a, d, ease = E.film) => ease(inv(a, a + d, t));
/* entrata + uscita in un colpo: 0→1→0 */
function inOut(t, D, ia, id, od, ei = E.film, eo = E.swift) {
  const i = ei(inv(ia, ia + id, t)); const o = eo(inv(D - od, D, t)); return { i, o, v: i * (1 - o) };
}

/* ---------- casuale deterministico ---------- */
function rng(seed) { let a = (seed >>> 0) || 1; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
function hash(n) { n = Math.sin(n * 127.1 + 311.7) * 43758.5453; return n - Math.floor(n); }
function hash2(x, y) { return hash(x * 157.31 + y * 913.17); }
function vnoise(x, y) {
  const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
  const a = hash2(xi, yi), b = hash2(xi + 1, yi), c = hash2(xi, yi + 1), d = hash2(xi + 1, yi + 1);
  return lerp(lerp(a, b, u), lerp(c, d, u), v);
}
function fbm(x, y, o = 4) { let s = 0, a = .5, f = 1; for (let i = 0; i < o; i++) { s += a * vnoise(x * f, y * f); f *= 2.03; a *= .5; } return s / (1 - Math.pow(.5, o)); }
/* rumore 1D liscio, per tremolii e derive */
function wobble(t, seed = 0, f = 1) { const x = t * f + seed * 13.7, i = Math.floor(x), k = x - i, u = k * k * (3 - 2 * k); return lerp(hash(i + seed * 91), hash(i + 1 + seed * 91), u) * 2 - 1; }

/* ---------- font ---------- */
const F = {
  display: "'Anton', 'Impact', 'Arial Narrow', sans-serif",
  body: "'Inter', 'Helvetica Neue', Arial, sans-serif",
  hand: "'Shadows Into Light Two', 'Comic Sans MS', cursive",
  marker: "'Permanent Marker', 'Shadows Into Light Two', cursive",
  mono: "'VT323', 'Courier New', monospace",
  type: "'Special Elite', 'Courier New', monospace",
  serif: "'Playfair Display', Georgia, 'Times New Roman', serif",
  black: "'UnifrakturMaguntia', 'Playfair Display', Georgia, serif"
};
const FONT_LOADS = ["400 40px Anton", "400 40px Inter", "500 40px Inter", "600 40px Inter", "700 40px Inter", "400 40px 'Shadows Into Light Two'",
  "400 40px 'Permanent Marker'", "400 40px VT323", "400 40px 'Special Elite'", "700 40px 'Playfair Display'", "900 40px 'Playfair Display'",
  "italic 400 40px 'Playfair Display'", "italic 700 40px 'Playfair Display'", "400 40px UnifrakturMaguntia"];
async function loadFonts() {
  try { await Promise.all(FONT_LOADS.map(f => document.fonts.load(f, 'AÀèÉ09'))); } catch (e) { }
  try { await document.fonts.ready; } catch (e) { }
}
function font(ctx, size, fam = F.display, weight = 400, style = '') { ctx.font = `${style} ${weight} ${size}px ${fam}`.trim(); }
function track(ctx, px) { if ('letterSpacing' in ctx) ctx.letterSpacing = px + 'px'; }

/* misura caratteri con crenatura reale: x di ogni lettera = larghezza del prefisso */
function chars(ctx, text, tracking = 0) {
  track(ctx, 0);
  const out = []; let prev = 0;
  const arr = Array.from(text);
  for (let i = 0; i < arr.length; i++) {
    const pre = arr.slice(0, i + 1).join('');
    const w = ctx.measureText(pre).width;
    out.push({ ch: arr[i], x: prev + i * tracking, w: w - prev });
    prev = w;
  }
  const width = prev + Math.max(0, arr.length - 1) * tracking;
  return { list: out, width };
}
function textW(ctx, text, tracking = 0) { track(ctx, 0); return ctx.measureText(text).width + Math.max(0, Array.from(text).length - 1) * tracking; }
function wrap(ctx, text, maxW, tracking = 0) {
  const out = [];
  for (const para of String(text).split('\n')) {
    const words = para.split(/\s+/).filter(Boolean); let cur = '';
    for (const w of words) { const t = cur ? cur + ' ' + w : w; if (cur && textW(ctx, t, tracking) > maxW) { out.push(cur); cur = w; } else cur = t; }
    out.push(cur);
  }
  return out;
}
/* riduce la dimensione finché il testo sta nella larghezza */
function fit(ctx, text, fam, maxSize, maxW, weight = 400, tracking = 0, style = '') {
  let s = maxSize;
  for (let i = 0; i < 40; i++) { font(ctx, s, fam, weight, style); if (textW(ctx, text, tracking * s) <= maxW) break; s *= .94; }
  return s;
}
function lines(p) { return String(p || '').split('\n').map(s => s.trim()).filter(Boolean); }
function rows(p, n = 2) { return lines(p).map(l => { const a = l.split('|').map(s => s.trim()); while (a.length < n) a.push(''); return a; }); }

/* ---------- forme ---------- */
function rr(ctx, x, y, w, h, r) { ctx.beginPath(); if (ctx.roundRect) ctx.roundRect(x, y, w, h, r); else ctx.rect(x, y, w, h); }
/* croce di registro (+) del design system */
function cross(ctx, x, y, s = 16, lw = 2) { ctx.lineWidth = lw; ctx.beginPath(); ctx.moveTo(x - s, y); ctx.lineTo(x + s, y); ctx.moveTo(x, y - s); ctx.lineTo(x, y + s); ctx.stroke(); }
/* cornice di registro: i lati crescono dagli angoli */
function regFrame(ctx, x, y, w, h, p, color = PAL.carta, alpha = .5, lw = 2) {
  if (p <= 0) return;
  ctx.save(); ctx.strokeStyle = color; ctx.lineCap = 'butt';
  ctx.globalAlpha = alpha * clamp(p * 3);
  const lx = w / 2 * p, ly = h / 2 * p; ctx.lineWidth = lw; ctx.beginPath();
  for (const [cx, cy, sx, sy] of [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]]) {
    ctx.moveTo(cx, cy); ctx.lineTo(cx + sx * lx, cy); ctx.moveTo(cx, cy); ctx.lineTo(cx, cy + sy * ly);
  }
  ctx.stroke(); ctx.globalAlpha = Math.min(1, alpha * 2 * clamp(p * 2));
  for (const [cx, cy] of [[x, y], [x + w, y], [x, y + h], [x + w, y + h]]) cross(ctx, cx, cy, 16, lw);
  ctx.restore();
}
/* bordo strappato: poligono irregolare (come la cartolina del design system) */
function roughRect(x, y, w, h, amp, step, seed, bites = false) {
  const r = rng(seed); const pts = [];
  const edge = (x0, y0, x1, y1, nx, ny) => {
    const len = Math.hypot(x1 - x0, y1 - y0), n = Math.max(2, Math.round(len / step));
    for (let i = 0; i < n; i++) { const t = i / n; let d = r() * amp; if (bites && r() < .04) d += amp * (1.5 + r() * 2); pts.push([x0 + (x1 - x0) * t + nx * d, y0 + (y1 - y0) * t + ny * d]); }
  };
  edge(x, y, x + w, y, 0, 1); edge(x + w, y, x + w, y + h, -1, 0); edge(x + w, y + h, x, y + h, 0, -1); edge(x, y + h, x, y, 1, 0);
  return pts;
}
function poly(ctx, pts) { ctx.beginPath(); pts.forEach((p, i) => i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])); ctx.closePath(); }
/* linea strappata orizzontale (per strappi di carta), restituisce punti x→y */
function tearLine(x0, x1, y, amp, seed, step = 7) {
  const r = rng(seed); const pts = []; let drift = 0;
  for (let x = x0; x <= x1 + step; x += step) { drift = drift * .82 + (r() - .5) * amp * .9; pts.push([x, y + drift + (r() - .5) * amp * .35 + Math.sin(x * .004 + seed) * amp * .8]); }
  return pts;
}
/* tratti a mano: punti con tremolio, disegno progressivo, spessore variabile da pennarello */
function handLine(x0, y0, x1, y1, seed = 1, wob = 4, n = 40) {
  const pts = []; for (let i = 0; i <= n; i++) { const t = i / n; const w = wobble(t * 3, seed) * wob * Math.sin(t * Math.PI); pts.push([lerp(x0, x1, t) - (y1 - y0) / Math.hypot(x1 - x0, y1 - y0 || 1) * w, lerp(y0, y1, t) + (x1 - x0) / Math.hypot(x1 - x0 || 1, y1 - y0) * w]); }
  return pts;
}
function handEllipse(cx, cy, rx, ry, seed = 1, turns = 1.12, n = 90) {
  const pts = []; const a0 = -2.3 + hash(seed) * .6;
  for (let i = 0; i <= n; i++) {
    const t = i / n, a = a0 + t * Math.PI * 2 * turns;
    const k = 1 + wobble(t * 4, seed) * .05 + t * .06;
    pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k * (1 + wobble(t * 2, seed + 3) * .04)]);
  }
  return pts;
}
function handCurve(x0, y0, x1, y1, bend = .25, seed = 1, n = 50) {
  const mx = (x0 + x1) / 2, my = (y0 + y1) / 2, dx = x1 - x0, dy = y1 - y0;
  const cx = mx - dy * bend, cy = my + dx * bend; const pts = [];
  for (let i = 0; i <= n; i++) { const t = i / n, u = 1 - t; const w = wobble(t * 3, seed) * 3; pts.push([u * u * x0 + 2 * u * t * cx + t * t * x1 + w, u * u * y0 + 2 * u * t * cy + t * t * y1 + w * .6]); }
  return pts;
}
function stroke(ctx, pts, p, width, color, opt = {}) {
  if (p <= 0 || pts.length < 2) return null;
  const n = pts.length - 1, upto = p * n, k = Math.floor(upto);
  ctx.save(); ctx.strokeStyle = color; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  if (opt.alpha != null) ctx.globalAlpha *= opt.alpha;
  if (opt.taper) {
    for (let i = 0; i < Math.min(k + 1, n); i++) {
      const a = pts[i], b = i + 1 <= k ? pts[i + 1] : [lerp(pts[i][0], pts[i + 1][0], upto - k), lerp(pts[i][1], pts[i + 1][1], upto - k)];
      const t = i / n; ctx.lineWidth = width * (.55 + .45 * Math.sin(Math.min(1, t * 1.1) * Math.PI) + .12 * wobble(t * 9, 4));
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke();
    }
  } else {
    ctx.lineWidth = width; ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i <= Math.min(k, n); i++) ctx.lineTo(pts[i][0], pts[i][1]);
    if (k < n) ctx.lineTo(lerp(pts[k][0], pts[k + 1][0], upto - k), lerp(pts[k][1], pts[k + 1][1], upto - k));
    ctx.stroke();
  }
  ctx.restore();
  const j = Math.min(n, Math.max(1, Math.ceil(upto)));
  const tip = k < n ? [lerp(pts[k][0], pts[k + 1][0], upto - k), lerp(pts[k][1], pts[k + 1][1], upto - k)] : pts[n];
  return { tip, ang: Math.atan2(tip[1] - pts[j - 1][1], tip[0] - pts[j - 1][0]) };
}
function arrowHead(ctx, x, y, ang, size, color, lw, p = 1) {
  if (p <= 0) return;
  ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.lineCap = 'round'; ctx.globalAlpha *= clamp(p * 2);
  const s = size * E.outBack(p);
  ctx.beginPath(); ctx.moveTo(x + Math.cos(ang + 2.55) * s, y + Math.sin(ang + 2.55) * s); ctx.lineTo(x, y); ctx.lineTo(x + Math.cos(ang - 2.55) * s, y + Math.sin(ang - 2.55) * s); ctx.stroke();
  ctx.restore();
}

/* ---------- texture ---------- */
const cache = new Map();
function mk(w, h) { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
function grainTiles() {
  if (cache.has('grain')) return cache.get('grain');
  const tiles = [];
  for (let k = 0; k < 6; k++) {
    const c = mk(256, 256), g = c.getContext('2d'), im = g.createImageData(256, 256), r = rng(77 + k * 31);
    for (let i = 0; i < im.data.length; i += 4) {
      const v = (r() + r() + r()) / 3 - .5; const white = v > 0;
      im.data[i] = im.data[i + 1] = im.data[i + 2] = white ? 255 : 0; im.data[i + 3] = Math.min(255, Math.abs(v) * 2 * 255 * 1.15);
    }
    g.putImageData(im, 0, 0); tiles.push(c);
  }
  cache.set('grain', tiles); return tiles;
}
/* grana: atop=true la applica solo a ciò che è già disegnato (testi, carta) */
function grain(ctx, t, amount, atop = false, fps = 24) {
  if (amount <= 0) return;
  const tiles = grainTiles(); const f = Math.floor(t * fps);
  const tile = tiles[f % tiles.length]; const pat = ctx.createPattern(tile, 'repeat');
  const ox = Math.floor(hash(f) * 256), oy = Math.floor(hash(f + .5) * 256);
  ctx.save(); ctx.globalCompositeOperation = atop ? 'source-atop' : 'source-over'; ctx.globalAlpha = clamp(amount);
  ctx.translate(-ox, -oy); ctx.fillStyle = pat; ctx.fillRect(ox, oy, W + 256, H + 256); ctx.restore();
}
function vignette(ctx, strength = .5, color = '0,0,0', inner = .45) {
  if (strength <= 0) return;
  const g = ctx.createRadialGradient(W / 2, H / 2, H * inner, W / 2, H / 2, H * 1.05);
  g.addColorStop(0, `rgba(${color},0)`); g.addColorStop(1, `rgba(${color},${strength})`);
  ctx.save(); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); ctx.restore();
}
function paperTex() {
  if (cache.has('paper')) return cache.get('paper');
  const S = 512, c = mk(S, S), g = c.getContext('2d'), im = g.createImageData(S, S);
  for (let y = 0; y < S; y++) for (let x = 0; x < S; x++) {
    const i = (y * S + x) * 4;
    const n = fbm(x / 70, y / 70, 4), f = vnoise(x / 2.2, y / 40) * .5 + vnoise(x / 40, y / 2.2) * .5;
    const v = 238 + (n - .5) * 26 + (f - .5) * 10 + (hash2(x, y) - .5) * 9;
    im.data[i] = v + 3; im.data[i + 1] = v - 3; im.data[i + 2] = v - 15; im.data[i + 3] = 255;
  }
  g.putImageData(im, 0, 0); cache.set('paper', c); return c;
}
/* riempie un tracciato con carta texturizzata */
function paperFill(ctx, tint = null, scale = 1.4) {
  const pat = ctx.createPattern(paperTex(), 'repeat'); if (pat.setTransform) pat.setTransform(new DOMMatrix().scale(scale));
  ctx.fillStyle = pat; ctx.fill();
  if (tint) { ctx.save(); ctx.globalCompositeOperation = 'multiply'; ctx.fillStyle = tint; ctx.fill(); ctx.restore(); }
}
/* polvere, peli e graffi di pellicola: cambiano a 24 fps */
function filmDirt(ctx, t, amount = 1, opts = {}) {
  if (amount <= 0) return;
  const f = Math.floor(t * 24), r = rng(1000 + f * 7);
  ctx.save();
  const nDust = Math.floor((3 + r() * 9) * amount);
  for (let i = 0; i < nDust; i++) {
    const x = r() * W, y = r() * H, s = .8 + r() ** 3 * 7, light = r() < .3;
    ctx.fillStyle = light ? 'rgba(255,250,240,.55)' : 'rgba(10,8,6,.62)';
    ctx.beginPath(); ctx.ellipse(x, y, s, s * (.5 + r() * .7), r() * 3, 0, 7); ctx.fill();
  }
  if (r() < .22 * amount) {
    const x = r() * W, y = r() * H, L = 40 + r() * 140;
    ctx.strokeStyle = 'rgba(12,10,8,.55)'; ctx.lineWidth = 1 + r() * 1.4; ctx.beginPath(); ctx.moveTo(x, y);
    ctx.bezierCurveTo(x + (r() - .5) * L, y + (r() - .5) * L, x + (r() - .5) * L, y + (r() - .5) * L, x + (r() - .5) * L, y + (r() - .5) * L); ctx.stroke();
  }
  /* graffi verticali che persistono per alcuni fotogrammi */
  const block = Math.floor(f / 9), rb = rng(5000 + block * 13);
  const nS = Math.floor(rb() * 3 * amount + (opts.scratches ? 1 : 0));
  for (let i = 0; i < nS; i++) {
    const x = rb() * W + wobble(t * 6, i + block) * 6; const light = rb() < .6;
    ctx.strokeStyle = light ? 'rgba(255,248,235,.32)' : 'rgba(0,0,0,.35)'; ctx.lineWidth = .8 + rb() * 1.2;
    const y0 = rb() < .5 ? 0 : rb() * H * .5, y1 = y0 + H * (.4 + rb() * .8);
    ctx.beginPath(); ctx.moveTo(x, y0); ctx.lineTo(x + (rb() - .5) * 8, y1); ctx.stroke();
  }
  ctx.restore();
}

/* ---------- immagini ---------- */
function srcSize(s) { return s ? [s.videoWidth || s.naturalWidth || s.width, s.videoHeight || s.naturalHeight || s.height] : [1, 1]; }
/* disegna la sorgente a copertura con zoom attorno a un punto focale (fx,fy in 0..1) */
function cover(ctx, src, x, y, w, h, zoom = 1, fx = .5, fy = .5) {
  if (!src) return;
  const [sw, sh] = srcSize(src); if (!sw || !sh) return;
  const s = Math.max(w / sw, h / sh) * zoom;
  const dw = sw * s, dh = sh * s;
  let dx = x + w / 2 - fx * dw + (fx - .5) * w * (1 / zoom) * 0, dy;
  /* il punto focale resta fermo in proporzione: con zoom 1 l'immagine è centrata */
  const k = (zoom - 1) / Math.max(1e-6, zoom);
  dx = x + (w - dw) / 2 + (0.5 - fx) * dw * k;
  dy = y + (h - dh) / 2 + (0.5 - fy) * dh * k;
  dx = Math.min(x, Math.max(x + w - dw, dx)); dy = Math.min(y, Math.max(y + h - dh, dy));
  ctx.drawImage(src, dx, dy, dw, dh);
}
/* mappa: punto (u,v) della sorgente → coordinate nel riquadro con lo stesso zoom/focale */
function coverMap(src, x, y, w, h, zoom, fx, fy, u, v) {
  const [sw, sh] = srcSize(src); const s = Math.max(w / sw, h / sh) * zoom; const dw = sw * s, dh = sh * s;
  const k = (zoom - 1) / Math.max(1e-6, zoom);
  let dx = x + (w - dw) / 2 + (0.5 - fx) * dw * k, dy = y + (h - dh) / 2 + (0.5 - fy) * dh * k;
  dx = Math.min(x, Math.max(x + w - dw, dx)); dy = Math.min(y, Math.max(y + h - dh, dy));
  return [dx + u * dw, dy + v * dh];
}
/* camera "virtuale": porta il punto (u,v) dell'inquadratura piena al centro con zoom z */
function camOn(ctx, z, u, v, cx = W / 2, cy = H / 2) {
  const px = u * W, py = v * H;
  /* limita perché i bordi non entrino in campo */
  let tx = cx - px * z, ty = cy - py * z;
  tx = Math.min(0, Math.max(W - W * z, tx)); ty = Math.min(0, Math.max(H - H * z, ty));
  ctx.setTransform(ctx.getTransform().multiply(new DOMMatrix([z, 0, 0, z, tx, ty])));
  return [tx, ty];
}
const TONES = ['Originale', 'Bianco e nero', 'Seppia', 'Duotono verde', 'Duotono rosso'];
function toneFilter(tone) {
  return { 'Bianco e nero': 'grayscale(1) contrast(1.15) brightness(.96)', 'Seppia': 'grayscale(1) sepia(.55) contrast(1.1) brightness(.96)' }[tone] || 'none';
}
/* elabora (e mette in cache) una versione tonalizzata della sorgente; i video vengono tonalizzati con ctx.filter */
function toned(src, tone, key) {
  if (!src || tone === 'Originale') return src;
  const isStatic = !(src instanceof HTMLVideoElement);
  const ck = 'tone:' + key + ':' + tone;
  if (isStatic && cache.has(ck)) return cache.get(ck);
  const [sw, sh] = srcSize(src); if (!sw || !sh) return src; const sc = Math.min(1, (isStatic ? 2400 : 1280) / Math.max(sw, sh));
  const c = isStatic ? mk(Math.round(sw * sc), Math.round(sh * sc)) : (cache.get('vtone') || mk(Math.round(sw * sc), Math.round(sh * sc)));
  if (!isStatic) { if (c.width !== Math.round(sw * sc)) { c.width = Math.round(sw * sc); c.height = Math.round(sh * sc); } cache.set('vtone', c); }
  const g = c.getContext('2d');
  if (tone === 'Bianco e nero' || tone === 'Seppia') { g.filter = toneFilter(tone); g.drawImage(src, 0, 0, c.width, c.height); g.filter = 'none'; }
  else {
    g.drawImage(src, 0, 0, c.width, c.height);
    const im = g.getImageData(0, 0, c.width, c.height), d = im.data;
    const [dark, light] = tone === 'Duotono rosso' ? [[34, 12, 16], [246, 228, 214]] : [[10, 30, 24], [238, 236, 222]];
    const acc = tone === 'Duotono rosso' ? [181, 50, 60] : [70, 120, 98];
    for (let i = 0; i < d.length; i += 4) {
      let l = (d[i] * .3 + d[i + 1] * .59 + d[i + 2] * .11) / 255; l = clamp((l - .5) * 1.15 + .5);
      const m = l < .5 ? [lerp(dark[0], acc[0], l * 2), lerp(dark[1], acc[1], l * 2), lerp(dark[2], acc[2], l * 2)] : [lerp(acc[0], light[0], l * 2 - 1), lerp(acc[1], light[1], l * 2 - 1), lerp(acc[2], light[2], l * 2 - 1)];
      d[i] = m[0]; d[i + 1] = m[1]; d[i + 2] = m[2];
    }
    g.putImageData(im, 0, 0);
  }
  if (isStatic) cache.set(ck, c);
  return c;
}
/* retino tipografico (mezzatinta da giornale) */
function halftone(src, key, cell = 7, ink = '#1b1a17', paper = null) {
  const ck = 'ht:' + key + ':' + cell; if (cache.has(ck)) return cache.get(ck);
  const [sw, sh] = srcSize(src); const tw = 1100, th = Math.round(tw * sh / sw);
  const sm = mk(Math.ceil(tw / cell), Math.ceil(th / cell)); const sg = sm.getContext('2d'); sg.drawImage(src, 0, 0, sm.width, sm.height);
  const d = sg.getImageData(0, 0, sm.width, sm.height).data;
  const c = mk(tw, th), g = c.getContext('2d'); if (paper) { g.fillStyle = paper; g.fillRect(0, 0, tw, th); }
  g.fillStyle = ink; g.save(); g.translate(tw / 2, th / 2); g.rotate(Math.PI / 4); g.translate(-tw / 2, -th / 2);
  g.restore();
  for (let y = 0; y < sm.height; y++) for (let x = 0; x < sm.width; x++) {
    const i = (y * sm.width + x) * 4; const l = (d[i] * .3 + d[i + 1] * .59 + d[i + 2] * .11) / 255;
    const r = (1 - l) ** .9 * cell * .72; if (r < .35) continue;
    g.beginPath(); g.arc(x * cell + cell / 2 + (y % 2) * cell / 2, y * cell + cell / 2, r, 0, 7); g.fill();
  }
  cache.set(ck, c); return c;
}

/* foto d'archivio di esempio, generata: campo, tribuna, giocatori in controluce */
function samplePhoto() {
  if (cache.has('sample')) return cache.get('sample');
  const w = 1800, h = 1200, c = mk(w, h), g = c.getContext('2d'); const r = rng(1934);
  const sky = g.createLinearGradient(0, 0, 0, h * .32); sky.addColorStop(0, '#d9d5cc'); sky.addColorStop(1, '#b9b4a8');
  g.fillStyle = sky; g.fillRect(0, 0, w, h * .32);
  /* tribuna con tettoia */
  g.fillStyle = '#4b4842'; g.beginPath(); g.moveTo(0, h * .13); g.lineTo(w, h * .085); g.lineTo(w, h * .115); g.lineTo(0, h * .16); g.fill();
  for (let x = 30; x < w; x += 150) { g.fillStyle = '#3e3b36'; g.fillRect(x, h * .1 + x * -.000, 6, h * .14); }
  g.fillStyle = '#5d5952'; g.fillRect(0, h * .155, w, h * .2);
  for (let i = 0; i < 52000; i++) { const x = r() * w, y = h * .16 + r() * h * .19; const v = 85 + r() * 95; g.fillStyle = `rgb(${v},${v - 4},${v - 10})`; g.beginPath(); g.arc(x, y, 1 + r() * 2.2, 0, 7); g.fill(); }
  g.fillStyle = '#2e2c28'; g.fillRect(0, h * .345, w, h * .022);
  /* prato in prospettiva con strisce */
  const grass = g.createLinearGradient(0, h * .36, 0, h); grass.addColorStop(0, '#8c8a80'); grass.addColorStop(1, '#6d6b62');
  g.fillStyle = grass; g.fillRect(0, h * .365, w, h);
  for (let k = 0; k < 9; k++) { g.fillStyle = k % 2 ? 'rgba(255,255,255,.035)' : 'rgba(0,0,0,.04)'; const y0 = h * .365 + (h * .635) * ((k / 9) ** 1.6), y1 = h * .365 + (h * .635) * (((k + 1) / 9) ** 1.6); g.fillRect(0, y0, w, y1 - y0); }
  g.strokeStyle = 'rgba(240,238,230,.75)'; g.lineWidth = 5;
  g.beginPath(); g.moveTo(-100, h * .97); g.lineTo(w * .7, h * .4); g.stroke();
  g.beginPath(); g.moveTo(w * .62, h * .43); g.lineTo(w * 1.1, h * .5); g.stroke();
  g.beginPath(); g.ellipse(w * .2, h * .8, w * .2, h * .07, -.25, 0, 7); g.lineWidth = 4; g.stroke();
  /* giocatori: silhouette semplici, maglia chiara e calzoncini scuri */
  const players = [[.32, .62, 1.0, 1], [.47, .55, .82, 0], [.58, .66, 1.08, 1], [.7, .52, .74, 0], [.82, .6, .9, 1], [.22, .5, .7, 0], [.9, .47, .62, 1], [.41, .74, 1.3, 0]];
  for (const [px, py, s, team] of players) {
    const x = px * w, y = py * h, S = 120 * s; const lean = (r() - .5) * .3;
    g.save(); g.translate(x, y); g.rotate(lean);
    g.fillStyle = 'rgba(0,0,0,.25)'; g.beginPath(); g.ellipse(S * .2, S * .02, S * .45, S * .08, 0, 0, 7); g.fill();
    g.fillStyle = '#2a2724'; g.lineCap = 'round'; g.strokeStyle = '#2a2724'; g.lineWidth = S * .11;
    g.beginPath(); g.moveTo(-S * .06, -S * .5); g.lineTo(-S * .16 - (r()) * S * .12, 0); g.moveTo(S * .06, -S * .5); g.lineTo(S * .2 + r() * S * .1, -S * .02); g.stroke();
    g.fillStyle = team ? '#efece4' : '#3a3632'; rr(g, -S * .17, -S * 1.02, S * .34, S * .44, S * .06); g.fill();
    g.fillStyle = team ? '#25221f' : '#d8d4ca'; g.fillRect(-S * .16, -S * .62, S * .32, S * .16);
    g.strokeStyle = team ? '#efece4' : '#3a3632'; g.lineWidth = S * .085; g.beginPath(); g.moveTo(-S * .15, -S * .95); g.lineTo(-S * .33, -S * .62 - r() * S * .2); g.moveTo(S * .15, -S * .95); g.lineTo(S * .32, -S * .7 + r() * S * .25); g.stroke();
    g.fillStyle = '#5a4a3e'; g.beginPath(); g.arc(0, -S * 1.12, S * .1, 0, 7); g.fill(); g.fillStyle = '#1f1b18'; g.beginPath(); g.arc(0, -S * 1.16, S * .1, Math.PI, 0); g.fill();
    g.restore();
  }
  g.fillStyle = '#f4f2ea'; g.beginPath(); g.arc(w * .52, h * .73, 13, 0, 7); g.fill(); g.strokeStyle = '#333'; g.lineWidth = 2; g.stroke();
  /* invecchiamento: sfocatura, monocromia, grana, vignetta */
  const o = mk(w, h), og = o.getContext('2d'); og.filter = 'blur(1px) grayscale(1) contrast(1.02)'; og.drawImage(c, 0, 0);
  og.filter = 'none';
  const im = og.getImageData(0, 0, w, h), d = im.data;
  for (let i = 0; i < d.length; i += 4) { const n = (r() + r() - 1) * 5; d[i] += n; d[i + 1] += n; d[i + 2] += n; }
  og.putImageData(im, 0, 0);
  const vg = og.createRadialGradient(w / 2, h / 2, h * .3, w / 2, h / 2, h * .95); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,.2)'); og.fillStyle = vg; og.fillRect(0, 0, w, h);
  cache.set('sample', o); return o;
}
/* ritratto di esempio per la scheda giocatore */
function samplePortrait() {
  if (cache.has('portrait')) return cache.get('portrait');
  const w = 900, h = 1100, c = mk(w, h), g = c.getContext('2d'); const r = rng(1949);
  const bg = g.createRadialGradient(w * .5, h * .35, 50, w * .5, h * .5, h * .8); bg.addColorStop(0, '#bdb8ad'); bg.addColorStop(1, '#5d5a54'); g.fillStyle = bg; g.fillRect(0, 0, w, h);
  g.fillStyle = '#2b2925'; g.beginPath(); g.moveTo(w * .08, h); g.bezierCurveTo(w * .1, h * .72, w * .3, h * .66, w * .5, h * .66); g.bezierCurveTo(w * .7, h * .66, w * .9, h * .72, w * .92, h); g.fill();
  g.fillStyle = '#e9e6de'; g.beginPath(); g.moveTo(w * .38, h * .66); g.lineTo(w * .5, h * .8); g.lineTo(w * .62, h * .66); g.fill();
  g.fillStyle = '#8f8476'; g.fillRect(w * .43, h * .52, w * .14, h * .16);
  g.fillStyle = '#a3978a'; g.beginPath(); g.ellipse(w * .5, h * .4, w * .17, h * .17, 0, 0, 7); g.fill();
  g.fillStyle = '#1e1b18'; g.beginPath(); g.ellipse(w * .5, h * .29, w * .18, h * .09, 0, Math.PI, 0); g.fill(); g.fillRect(w * .32, h * .27, w * .36, h * .04);
  g.fillStyle = 'rgba(0,0,0,.25)'; g.beginPath(); g.ellipse(w * .44, h * .4, 14, 7, 0, 0, 7); g.ellipse(w * .56, h * .4, 14, 7, 0, 0, 7); g.fill();
  const o = mk(w, h), og = o.getContext('2d'); og.filter = 'blur(1px) grayscale(1)'; og.drawImage(c, 0, 0); og.filter = 'none';
  cache.set('portrait', o); return o;
}

/* ---------- audio: effetti sonori sintetizzati ---------- */
const SFX = (() => {
  const noiseBuf = new WeakMap();
  function noise(ctx) { if (noiseBuf.has(ctx)) return noiseBuf.get(ctx); const b = ctx.createBuffer(2, ctx.sampleRate * 3, ctx.sampleRate); for (let ch = 0; ch < 2; ch++) { const d = b.getChannelData(ch); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; } noiseBuf.set(ctx, b); return b; }
  function nsrc(ctx, t, d) { const s = ctx.createBufferSource(); s.buffer = noise(ctx); s.loop = true; s.start(t, Math.random() * 2); s.stop(t + d + .05); return s; }
  function env(ctx, t, a, h, rel, peak) { const g = ctx.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(peak, t + a); g.gain.setValueAtTime(peak, t + a + h); g.gain.exponentialRampToValueAtTime(.0001, t + a + h + rel); return g; }
  function filt(ctx, type, f, q = 1) { const b = ctx.createBiquadFilter(); b.type = type; b.frequency.value = f; b.Q.value = q; return b; }
  function osc(ctx, type, f, t, d) { const o = ctx.createOscillator(); o.type = type; o.frequency.setValueAtTime(f, t); o.start(t); o.stop(t + d + .05); return o; }
  const S = {
    whoosh(ctx, out, t, g, c) {
      const d = c.d || .7; const n = nsrc(ctx, t, d); const bp = filt(ctx, 'bandpass', 260, .9);
      bp.frequency.setValueAtTime(220, t); bp.frequency.exponentialRampToValueAtTime(2600, t + d * .6); bp.frequency.exponentialRampToValueAtTime(420, t + d);
      const e = ctx.createGain(); e.gain.setValueAtTime(0.0001, t); e.gain.exponentialRampToValueAtTime(.9 * g, t + d * .6); e.gain.exponentialRampToValueAtTime(.0001, t + d);
      const p = ctx.createStereoPanner(); p.pan.setValueAtTime(-.6, t); p.pan.linearRampToValueAtTime(.6, t + d);
      n.connect(bp).connect(e).connect(p).connect(out.dry); p.connect(out.wet);
    },
    impact(ctx, out, t, g) {
      const o = osc(ctx, 'sine', 95, t, 1.6); o.frequency.exponentialRampToValueAtTime(30, t + 1.1);
      const e = env(ctx, t, .004, .05, 1.4, 1.1 * g); o.connect(e).connect(out.dry); e.connect(out.wet);
      const n = nsrc(ctx, t, .5), lp = filt(ctx, 'lowpass', 1400, .7), e2 = env(ctx, t, .002, .01, .35, .7 * g); n.connect(lp).connect(e2).connect(out.dry); e2.connect(out.wet);
    },
    hit(ctx, out, t, g) {
      const o = osc(ctx, 'sine', 150, t, .4); o.frequency.exponentialRampToValueAtTime(55, t + .25);
      const e = env(ctx, t, .002, .02, .3, .8 * g); o.connect(e).connect(out.dry);
      const n = nsrc(ctx, t, .08), hp = filt(ctx, 'highpass', 2500), e2 = env(ctx, t, .001, .005, .05, .35 * g); n.connect(hp).connect(e2).connect(out.dry);
    },
    tick(ctx, out, t, g) { const n = nsrc(ctx, t, .03), hp = filt(ctx, 'bandpass', 4200, 2), e = env(ctx, t, .0005, .002, .02, .45 * g); n.connect(hp).connect(e).connect(out.dry); },
    key(ctx, out, t, g, c) {
      const v = c.v ?? Math.random(); const n = nsrc(ctx, t, .06), bp = filt(ctx, 'bandpass', 2200 + v * 1400, 1.8), e = env(ctx, t, .0008, .004, .045, (.5 + v * .3) * g);
      n.connect(bp).connect(e).connect(out.dry);
      const o = osc(ctx, 'triangle', 180 + v * 60, t, .06), e2 = env(ctx, t, .001, .003, .04, .35 * g); o.connect(e2).connect(out.dry);
      const n2 = nsrc(ctx, t + .028, .03), hp = filt(ctx, 'highpass', 5000), e3 = env(ctx, t + .028, .0005, .002, .02, .18 * g); n2.connect(hp).connect(e3).connect(out.dry);
    },
    bell(ctx, out, t, g) { for (const [f, a] of [[2093, .35], [3140, .18], [4186, .08]]) { const o = osc(ctx, 'sine', f, t, 1.6), e = env(ctx, t, .002, .01, 1.4, a * g); o.connect(e).connect(out.dry); e.connect(out.wet); } },
    shutter(ctx, out, t, g) { S.key(ctx, out, t, g * 1.2, { v: .2 }); S.key(ctx, out, t + .07, g, { v: .8 }); const n = nsrc(ctx, t, .1), bp = filt(ctx, 'bandpass', 1500, .8), e = env(ctx, t + .01, .005, .03, .05, .25 * g); n.connect(bp).connect(e).connect(out.dry); },
    flash(ctx, out, t, g) {
      const n = nsrc(ctx, t, .1), lp = filt(ctx, 'lowpass', 3500), e = env(ctx, t, .001, .01, .08, .8 * g); n.connect(lp).connect(e).connect(out.dry); e.connect(out.wet);
      const o = osc(ctx, 'sine', 5200, t, 1.2); o.frequency.exponentialRampToValueAtTime(3200, t + 1); const e2 = env(ctx, t + .02, .02, .05, .9, .05 * g); o.connect(e2).connect(out.dry);
    },
    riser(ctx, out, t, g, c) {
      const d = c.d || 1.5; const n = nsrc(ctx, t, d), bp = filt(ctx, 'bandpass', 300, 1.2); bp.frequency.setValueAtTime(300, t); bp.frequency.exponentialRampToValueAtTime(5000, t + d);
      const e = ctx.createGain(); e.gain.setValueAtTime(.0001, t); e.gain.exponentialRampToValueAtTime(.55 * g, t + d); e.gain.linearRampToValueAtTime(0, t + d + .04);
      n.connect(bp).connect(e).connect(out.dry); e.connect(out.wet);
      const o = osc(ctx, 'sawtooth', 110, t, d); o.frequency.exponentialRampToValueAtTime(440, t + d); const lp = filt(ctx, 'lowpass', 900), e2 = ctx.createGain(); e2.gain.setValueAtTime(.0001, t); e2.gain.exponentialRampToValueAtTime(.12 * g, t + d); e2.gain.linearRampToValueAtTime(0, t + d + .04); o.connect(lp).connect(e2).connect(out.dry);
    },
    grains(ctx, out, t, g, c, f0, q, rate, amp) {
      const d = c.d || .6; const n = nsrc(ctx, t, d), bp = filt(ctx, 'bandpass', f0, q), e = ctx.createGain(); e.gain.setValueAtTime(0, t);
      let k = t; const r = rng(Math.floor(t * 1000) + 3);
      while (k < t + d) { const a = amp * g * (.3 + r() * .7) * Math.sin(Math.PI * (k - t) / d) ** .4; e.gain.setValueAtTime(a, k); e.gain.setValueAtTime(a * .2, k + rate * .4); k += rate * (.4 + r()); }
      e.gain.setValueAtTime(0, t + d); n.connect(bp).connect(e).connect(out.dry);
    },
    rip(ctx, out, t, g, c) { S.grains(ctx, out, t, g, c, 1800, .6, .012, .9); S.whoosh(ctx, out, t, g * .35, { d: c.d || .6 }); },
    chalk(ctx, out, t, g, c) { S.grains(ctx, out, t, g, c, 3200, 2.2, .018, .4); },
    pop(ctx, out, t, g) { const o = osc(ctx, 'sine', 820, t, .15); o.frequency.exponentialRampToValueAtTime(260, t + .1); const e = env(ctx, t, .002, .01, .1, .5 * g); o.connect(e).connect(out.dry); e.connect(out.wet); },
    static(ctx, out, t, g, c) {
      const d = c.d || .5; const n = nsrc(ctx, t, d), bp = filt(ctx, 'bandpass', 1800, .4), e = env(ctx, t, .01, d - .06, .05, .35 * g); n.connect(bp).connect(e).connect(out.dry);
      const o = osc(ctx, 'square', 60, t, d), lp = filt(ctx, 'lowpass', 300), e2 = env(ctx, t, .01, d - .06, .05, .06 * g); o.connect(lp).connect(e2).connect(out.dry);
    },
    glitch(ctx, out, t, g, c) { const r = rng(Math.floor(t * 777)); const d = c.d || .4; let k = t; while (k < t + d) { const l = .015 + r() * .04; const o = osc(ctx, 'square', 200 + r() * 1800, k, l), e = env(ctx, k, .001, l * .7, .01, .12 * g); o.connect(e).connect(out.dry); k += l + r() * .03; } },
    projector(ctx, out, t, g, c) {
      const d = c.d || 3; const n = nsrc(ctx, t, d), lp = filt(ctx, 'lowpass', 1200), e = env(ctx, t, .2, d - .5, .3, .08 * g); n.connect(lp).connect(e).connect(out.dry);
      for (let k = t; k < t + d; k += 1 / 24) { const nn = nsrc(ctx, k, .02), bp = filt(ctx, 'bandpass', 900, 3), ee = env(ctx, k, .001, .003, .015, .12 * g * Math.min(1, (k - t) * 4, (t + d - k) * 4)); nn.connect(bp).connect(ee).connect(out.dry); }
    },
    sub(ctx, out, t, g) { const o = osc(ctx, 'sine', 55, t, 2.2); o.frequency.exponentialRampToValueAtTime(38, t + 2); const e = env(ctx, t, .02, .2, 1.8, .7 * g); o.connect(e).connect(out.dry); }
  };
  function reverb(ctx) {
    const len = ctx.sampleRate * 2.4, b = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let ch = 0; ch < 2; ch++) { const d = b.getChannelData(ch); for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 3.2); }
    const c = ctx.createConvolver(); c.buffer = b; return c;
  }
  async function render(cues, dur, sr = 48000) {
    if (!cues || !cues.length || typeof OfflineAudioContext === 'undefined') return null;
    const ctx = new OfflineAudioContext(2, Math.max(1, Math.ceil(dur * sr)), sr);
    const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -10; comp.ratio.value = 4; comp.attack.value = .003; comp.release.value = .2;
    const master = ctx.createGain(); master.gain.value = .9; master.connect(comp).connect(ctx.destination);
    const rv = reverb(ctx), wet = ctx.createGain(); wet.gain.value = .22; wet.connect(rv).connect(master);
    const out = { dry: master, wet };
    for (const c of cues) { if (c.t < dur && S[c.s]) { try { S[c.s](ctx, out, Math.max(0, c.t), c.g ?? 1, c); } catch (e) { console.warn(e); } } }
    return await ctx.startRendering();
  }
  function wav(buf) {
    const ch = buf.numberOfChannels, len = buf.length, sr = buf.sampleRate, out = new DataView(new ArrayBuffer(44 + len * ch * 2));
    const ws = (o, s) => { for (let i = 0; i < s.length; i++) out.setUint8(o + i, s.charCodeAt(i)); };
    ws(0, 'RIFF'); out.setUint32(4, 36 + len * ch * 2, true); ws(8, 'WAVE'); ws(12, 'fmt '); out.setUint32(16, 16, true); out.setUint16(20, 1, true); out.setUint16(22, ch, true);
    out.setUint32(24, sr, true); out.setUint32(28, sr * ch * 2, true); out.setUint16(32, ch * 2, true); out.setUint16(34, 16, true); ws(36, 'data'); out.setUint32(40, len * ch * 2, true);
    const data = []; for (let c = 0; c < ch; c++) data.push(buf.getChannelData(c));
    let o = 44; for (let i = 0; i < len; i++) for (let c = 0; c < ch; c++) { const v = clamp(data[c][i], -1, 1); out.setInt16(o, v < 0 ? v * 0x8000 : v * 0x7fff, true); o += 2; }
    return new Uint8Array(out.buffer);
  }
  return { render, wav, names: Object.keys(S) };
})();

window.MV = { W, H, PAL, SWATCHES, clamp, lerp, inv, smooth, bezier, E, ph, inOut, rng, hash, hash2, vnoise, fbm, wobble, F, loadFonts, font, track, chars, textW, wrap, fit, lines, rows,
  rr, cross, regFrame, roughRect, poly, tearLine, handLine, handEllipse, handCurve, stroke, arrowHead, mk, grain, vignette, paperTex, paperFill, filmDirt,
  srcSize, cover, coverMap, camOn, TONES, toneFilter, toned, halftone, samplePhoto, samplePortrait, SFX, cache };
})();
