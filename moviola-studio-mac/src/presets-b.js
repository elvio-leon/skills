/* Moviola — preset: tattica, mappa, transizioni, texture, camera */
(function () {
'use strict';
const M = window.MV, X = window.MVX, { W, H, PAL, E, ph, clamp, lerp, inv, smooth, F } = M;
const { rgba, ground, T, AT, mask, alpha, drift, shake, accentP, grainP, bgP, finish } = X;
const P = window.PRESETS;

/* =============================================================== TATTICA */
const FORMS = {
  'Sistema WM 3-2-2-3': [[.04, .5], [.18, .2], [.16, .5], [.18, .8], [.33, .35], [.33, .65], [.5, .38], [.5, .62], [.7, .12], [.74, .5], [.7, .88]],
  'Metodo 2-3-2-3': [[.04, .5], [.2, .3], [.2, .7], [.36, .18], [.33, .5], [.36, .82], [.5, .36], [.5, .64], [.68, .14], [.72, .5], [.68, .86]],
  'Catenaccio 1-3-3-3': [[.04, .5], [.1, .5], [.2, .2], [.2, .5], [.2, .8], [.38, .25], [.36, .5], [.38, .75], [.56, .2], [.6, .5], [.56, .8]],
  '4-4-2': [[.04, .5], [.2, .14], [.18, .38], [.18, .62], [.2, .86], [.4, .14], [.38, .4], [.38, .6], [.4, .86], [.58, .38], [.58, .62]],
  '4-3-3': [[.04, .5], [.2, .14], [.18, .38], [.18, .62], [.2, .86], [.38, .28], [.35, .5], [.38, .72], [.6, .14], [.63, .5], [.6, .86]],
  '4-2-3-1': [[.04, .5], [.2, .14], [.18, .38], [.18, .62], [.2, .86], [.33, .38], [.33, .62], [.5, .16], [.5, .5], [.5, .84], [.65, .5]],
  '3-5-2': [[.04, .5], [.18, .27], [.16, .5], [.18, .73], [.38, .08], [.35, .32], [.32, .5], [.35, .68], [.38, .92], [.58, .4], [.58, .6]],
  '5-3-2': [[.04, .5], [.24, .08], [.18, .3], [.16, .5], [.18, .7], [.24, .92], [.38, .28], [.36, .5], [.38, .72], [.56, .4], [.56, .6]]
};
function pitchLines() {
  const L = [], arc = (cx, cy, r, a0, a1, n = 40) => { const pts = []; for (let i = 0; i <= n; i++) { const a = a0 + (a1 - a0) * i / n; pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return pts; };
  L.push([[0, 0], [105, 0], [105, 68], [0, 68], [0, 0]]); L.push([[52.5, 0], [52.5, 68]]); L.push(arc(52.5, 34, 9.15, 0, Math.PI * 2, 60));
  for (const s of [0, 1]) {
    const x = s ? 105 : 0, d = s ? -1 : 1;
    L.push([[x, 13.84], [x + d * 16.5, 13.84], [x + d * 16.5, 54.16], [x, 54.16]]);
    L.push([[x, 24.84], [x + d * 5.5, 24.84], [x + d * 5.5, 43.16], [x, 43.16]]);
    const a = Math.acos(5.5 / 9.15); L.push(s ? arc(105 - 11, 34, 9.15, Math.PI - a, Math.PI + a) : arc(11, 34, 9.15, -a, a));
    L.push([[x, 30.34], [x - d * 1.8, 30.34], [x - d * 1.8, 37.66], [x, 37.66]]);
  }
  for (const [cx, cy, a0] of [[0, 0, 0], [105, 0, Math.PI / 2], [105, 68, Math.PI], [0, 68, -Math.PI / 2]]) L.push(arc(cx, cy, 1, a0, a0 + Math.PI / 2, 8));
  return L;
}
const PITCH = pitchLines();
function boardBg(ctx, style) {
  if (style === 'Carta') { ground(ctx, 'Carta'); return; }
  if (style === 'Progetto') { ground(ctx, 'Inchiostro'); return; }
  const key = 'board'; let c = M.cache.get(key);
  if (!c) { c = M.mk(960, 540); const g = c.getContext('2d'); const im = g.createImageData(960, 540); for (let y = 0; y < 540; y++) for (let x = 0; x < 960; x++) { const i = (y * 960 + x) * 4; const n = M.fbm(x / 90, y / 60, 4), s = M.fbm(x / 14 + 9, y / 140, 2); const v = 30 + n * 22 + (s > .62 ? (s - .62) * 60 : 0); im.data[i] = v * .78; im.data[i + 1] = v * 1.02; im.data[i + 2] = v * .88; im.data[i + 3] = 255; } g.putImageData(im, 0, 0); M.cache.set(key, c); }
  ctx.drawImage(c, 0, 0, W, H); M.vignette(ctx, .5);
}
P.push({
  id: 'lavagna', cat: 'Tattica', name: 'Lavagna tattica', dur: 11, thumbT: 6.5,
  desc: 'Campo che si disegna, giocatori che entrano reparto per reparto con nome e numero, poi corse e passaggi animati in sequenza. Moduli storici inclusi: Metodo, Sistema WM, Catenaccio.',
  tip: 'Spiega un\'idea di gioco alla volta. Scrivi i movimenti come "10>78,40" (il 10 corre in quel punto, in % del campo) o "10>9" (passaggio dal 10 al 9).',
  params: [
    { k: 'squadra', label: 'Titolo', type: 'text', def: 'GRANDE TORINO' },
    { k: 'modulo', label: 'Modulo', type: 'select', opts: Object.keys(FORMS), def: 'Sistema WM 3-2-2-3' },
    { k: 'nomi', label: 'Giocatori (Nome|numero), dall\'alto in basso per reparto', type: 'textarea', def: 'Bacigalupo|1\nMaroso|3\nRigamonti|5\nBallarin|2\nCastigliano|6\nGrezar|4\nMazzola|10\nLoik|8\nOssola|11\nGabetto|9\nMenti|7' },
    { k: 'mosse', label: 'Movimenti in sequenza', type: 'textarea', def: '6>10\n10>66,30\n6>10\n10>9\n9>90,48' },
    { k: 'stile', label: 'Stile', type: 'select', opts: ['Lavagna', 'Progetto', 'Carta'], def: 'Lavagna' },
    { k: 'colore', label: 'Colore giocatori', type: 'color', def: PAL.rosso },
    grainP(.3)
  ],
  sched(p) { const ms = M.lines(p.mosse); return ms.map((m, i) => ({ m, t0: 4.0 + i * 1.15 })); },
  sfx(p) { const c = [{ s: 'chalk', t: .1, d: 1.6, g: .4 }]; for (let i = 0; i < 11; i++) c.push({ s: 'pop', t: 1.7 + i * .12, g: .35 }); this.sched(p).forEach(s => c.push({ s: /,/.test(s.m) ? 'chalk' : 'whoosh', t: s.t0, d: .7, g: .4 })); return c; },
  draw(ctx, t, D, p) {
    const st = p.stile; boardBg(ctx, st);
    const ink = st === 'Carta' ? PAL.inchiostro : PAL.carta;
    const ex = ph(t, D - .6, .5, E.swift);
    const px0 = 265, py0 = 150, pw = 1390, phh = 900, mx = v => px0 + v / 105 * pw, my = v => py0 + v / 68 * phh;
    ctx.save(); ctx.globalAlpha = 1 - ex;
    /* titolo */
    mask(ctx, px0 - 10, 30, 1400, 110, () => T(ctx, p.squadra.toUpperCase(), px0, 118 + (1 - ph(t, .2, .8, E.film)) * 100, { size: 76, fam: st === 'Lavagna' ? F.marker : F.display, color: ink }));
    alpha(ctx, ph(t, .6, .6), () => T(ctx, p.modulo.toUpperCase(), px0 + pw, 112, { size: 30, weight: 600, tr: .2, color: st === 'Carta' ? p.colore : rgba(ink, .8), align: 'right' }));
    /* linee del campo */
    const lp = ph(t, .2, 1.6, E.io3);
    PITCH.forEach((pl, i) => {
      const pts = pl.map(q => [mx(q[0]), my(q[1])]);
      if (st === 'Lavagna') { M.stroke(ctx, pts, lp, 4, rgba(PAL.carta, .78)); M.stroke(ctx, pts.map(q => [q[0] + 1.5, q[1] + 1]), lp, 2, rgba(PAL.carta, .25)); }
      else M.stroke(ctx, pts, lp, st === 'Progetto' ? 1.6 : 3, rgba(ink, st === 'Progetto' ? .7 : .85));
    });
    if (st === 'Progetto') {
      ctx.strokeStyle = rgba(PAL.carta, .7 * lp); for (const [x, y] of [[0, 0], [105, 0], [0, 68], [105, 68]]) M.cross(ctx, mx(x), my(y), 14, 1.5);
      alpha(ctx, lp, () => { T(ctx, '105 m', mx(52.5), py0 + phh + 44, { size: 20, fam: F.mono, color: rgba(PAL.carta, .7), align: 'center' }); ctx.save(); ctx.translate(px0 - 30, my(34)); ctx.rotate(-Math.PI / 2); T(ctx, '68 m', 0, 0, { size: 20, fam: F.mono, color: rgba(PAL.carta, .7), align: 'center' }); ctx.restore(); });
    }
    if (st === 'Lavagna') M.grain(ctx, t, .5, true, 1);
    /* giocatori */
    const form = FORMS[p.modulo] || FORMS['Sistema WM 3-2-2-3'];
    const names = M.rows(p.nomi); const pos = form.map((q, i) => ({ x: q[0] * 105, y: q[1] * 68, n: names[i] ? names[i][1] || String(i + 1) : String(i + 1), name: names[i] ? names[i][0] : '' }));
    /* applica i movimenti fino al tempo t */
    const sch = this.sched(p); const ball = { at: null, x: 0, y: 0, vis: false };
    const byNum = n => pos.find(q => q.n === n);
    const drawLater = [];
    sch.forEach(({ m, t0 }, si) => {
      const mm = m.match(/^\s*(\w+)\s*>\s*(?:(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)|(\w+))\s*$/); if (!mm) return;
      const a = byNum(mm[1]); if (!a) return; const k = E.io3(inv(t0, t0 + .95, t)); if (t < t0) return;
      if (mm[4]) {
        const b = byNum(mm[4]); if (!b) return;
        const x0 = a.x, y0 = a.y, x1 = b.x, y1 = b.y;
        drawLater.push(() => { const pts = [[mx(x0), my(y0)], [mx(x1), my(y1)]]; const dl = Math.hypot(pts[1][0] - pts[0][0], pts[1][1] - pts[0][1]); ctx.save(); ctx.setLineDash([14, 12]); ctx.globalAlpha *= 1 - .6 * inv(t0 + 1.2, t0 + 2.4, t); const r = M.stroke(ctx, M.handLine(pts[0][0], pts[0][1], pts[1][0], pts[1][1], si, 2, 24), k, 4, st === 'Carta' ? PAL.inchiostro : PAL.carta); ctx.restore(); if (r && k > .1) M.arrowHead(ctx, r.tip[0], r.tip[1], r.ang, 20, st === 'Carta' ? PAL.inchiostro : PAL.carta, 4, inv(.85, 1, k) || (k >= 1 ? 1 : 0)); });
        ball.vis = true; ball.x = lerp(x0, x1, k); ball.y = lerp(y0, y1, k);
      } else {
        const tx = +mm[2] / 100 * 105, ty = +mm[3] / 100 * 68; const x0 = a.x, y0 = a.y;
        drawLater.push(() => { ctx.save(); ctx.globalAlpha *= 1 - .6 * inv(t0 + 1.2, t0 + 2.4, t); const pts = M.handCurve(mx(x0), my(y0), mx(tx), my(ty), .18, si + 2, 40); const r = M.stroke(ctx, pts, k, 5, p.colore, { taper: true }); if (r) M.arrowHead(ctx, r.tip[0], r.tip[1], r.ang, 22, p.colore, 5, k >= .98 ? 1 : 0); ctx.restore(); });
        const bez = M.handCurve(x0, y0, tx, ty, .18, si + 2, 40); const kk = Math.min(bez.length - 1, Math.floor(k * (bez.length - 1)));
        a.x = bez[kk][0]; a.y = bez[kk][1]; if (k >= 1) { a.x = tx; a.y = ty; }
        if (ball.vis) { ball.x = a.x + .8; ball.y = a.y + .8; }
      }
    });
    drawLater.forEach(f => f());
    const labels = [];
    pos.forEach((q, i) => {
      const rowT = 1.7 + i * .12; const k = ph(t, rowT, .5, E.lin); if (k <= 0) return; const s = E.outBack(k);
      const x = mx(q.x), y = my(q.y);
      ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
      if (st === 'Lavagna') { ctx.strokeStyle = PAL.carta; ctx.lineWidth = 4; M.stroke(ctx, M.handEllipse(0, 0, 30, 30, i + 1, 1.05, 40), 1, 4, PAL.carta); ctx.fillStyle = rgba(p.colore, .85); ctx.beginPath(); ctx.arc(0, 0, 25, 0, 7); ctx.fill(); T(ctx, q.n, 0, 14, { size: 38, fam: F.marker, color: PAL.carta, align: 'center' }); }
      else { ctx.fillStyle = p.colore; ctx.beginPath(); ctx.arc(0, 0, 30, 0, 7); ctx.fill(); ctx.strokeStyle = st === 'Carta' ? PAL.inchiostro : PAL.carta; ctx.lineWidth = 2.5; ctx.stroke(); T(ctx, q.n, 0, 13, { size: 34, fam: F.display, color: PAL.carta, align: 'center' }); }
      ctx.restore();
      const lsz = st === 'Lavagna' ? 23 : 19; M.font(ctx, lsz, st === 'Lavagna' ? F.marker : F.body, 600); const lw = M.textW(ctx, q.name.toUpperCase(), st === 'Lavagna' ? 0 : lsz * .08);
      let ly = y + 58; const hit = yy => labels.some(o => Math.abs(o[0] - x) < (o[2] + lw) / 2 + 8 && Math.abs(o[1] - yy) < 30);
      if (hit(ly)) ly = y - 44; if (hit(ly)) ly = y + 86; labels.push([x, ly, lw]);
      if (q.name) alpha(ctx, ph(t, rowT + .2, .4), () => { ctx.save(); if (st !== 'Carta') { ctx.shadowColor = 'rgba(0,0,0,.7)'; ctx.shadowBlur = 6; } T(ctx, q.name.toUpperCase(), x, ly, { size: lsz, fam: st === 'Lavagna' ? F.marker : F.body, weight: 600, tr: st === 'Lavagna' ? 0 : .08, color: ink, align: 'center' }); ctx.restore(); });
    });
    if (ball.vis) { ctx.fillStyle = '#fff'; ctx.strokeStyle = '#111'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(mx(ball.x), my(ball.y), 11, 0, 7); ctx.fill(); ctx.stroke(); }
    ctx.restore();
    M.grain(ctx, t, p.grana * .35, false);
  }
});

/* =============================================================== MAPPA */
const CITIES = { torino: [45.07, 7.69], milano: [45.46, 9.19], genova: [44.41, 8.93], bologna: [44.49, 11.34], firenze: [43.77, 11.25], roma: [41.9, 12.5], napoli: [40.85, 14.27], bari: [41.12, 16.87], palermo: [38.12, 13.36], cagliari: [39.22, 9.12], verona: [45.44, 10.99], bergamo: [45.7, 9.67], udine: [46.06, 13.24], venezia: [45.44, 12.33], trieste: [45.65, 13.78], lecce: [40.35, 18.17], catania: [37.5, 15.09], parma: [44.8, 10.33], superga: [45.08, 7.77], vercelli: [45.32, 8.42], 'reggio calabria': [38.11, 15.65], salerno: [40.68, 14.77], empoli: [43.72, 10.95], pisa: [43.72, 10.4], livorno: [43.55, 10.31], novara: [45.45, 8.62], brescia: [45.54, 10.21], como: [45.81, 9.08], lisbona: [38.72, -9.14], madrid: [40.42, -3.7], barcellona: [41.39, 2.17], siviglia: [37.39, -5.98], valencia: [39.47, -.38], londra: [51.51, -.13], manchester: [53.48, -2.24], liverpool: [53.41, -2.98], glasgow: [55.86, -4.25], dublino: [53.35, -6.26], parigi: [48.86, 2.35], marsiglia: [43.3, 5.37], lione: [45.76, 4.84], monaco: [48.14, 11.58], 'monaco di baviera': [48.14, 11.58], berlino: [52.52, 13.4], dortmund: [51.51, 7.47], amburgo: [53.55, 9.99], amsterdam: [52.37, 4.9], rotterdam: [51.92, 4.48], bruxelles: [50.85, 4.35], vienna: [48.21, 16.37], budapest: [47.5, 19.04], belgrado: [44.79, 20.45], praga: [50.08, 14.44], zurigo: [47.38, 8.54], berna: [46.95, 7.45], ginevra: [46.2, 6.14], atene: [37.98, 23.73], istanbul: [41.01, 28.98], bucarest: [44.43, 26.1], varsavia: [52.23, 21.01], stoccolma: [59.33, 18.07], copenaghen: [55.68, 12.57], oslo: [59.91, 10.75], mosca: [55.76, 37.62], kiev: [50.45, 30.52], zagabria: [45.81, 15.98], spalato: [43.51, 16.44], 'montecarlo': [43.74, 7.42], salonicco: [40.64, 22.94], porto: [41.15, -8.61], wembley: [51.56, -.28], tirana: [41.33, 19.82] };
const merc = lat => Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) * 180 / Math.PI;
function cityOf(line) { const a = line.split('|').map(s => s.trim()); if (a.length >= 3 && !isNaN(+a[1])) return { name: a[0], lat: +a[1], lon: +a[2] }; const c = CITIES[a[0].toLowerCase()]; return c ? { name: a[0], lat: c[0], lon: c[1] } : null; }
P.push({
  id: 'mappa', cat: 'Tattica', name: 'Mappa e percorso', dur: 8, thumbT: 5,
  desc: 'Mappa d\'Europa che si avvicina sul percorso: puntine che cadono sulle città, rotta che si traccia ad arco con il segnalino in viaggio. Tre stili, Italia in evidenza.',
  tip: 'Scrivi una città per riga (ce ne sono 80 in archivio) oppure "Nome|lat|lon". Ideale per trasferte europee, tournée e mercato.',
  params: [
    { k: 'percorso', label: 'Tappe (una per riga)', type: 'textarea', def: 'Lisbona\nBarcellona\nSuperga' },
    { k: 'titolo', label: 'Titolo', type: 'text', def: 'L\'ULTIMO VOLO · 4 MAGGIO 1949' },
    { k: 'stile', label: 'Stile', type: 'select', opts: ['Carta d\'epoca', 'Verde campo', 'Notte'], def: 'Carta d\'epoca' },
    { k: 'italia', label: 'Italia in evidenza', type: 'bool', def: true },
    accentP(), grainP(.3)
  ],
  sfx(p, D) { const n = M.lines(p.percorso).length; const c = [{ s: 'whoosh', t: .2, d: 1.2, g: .4 }]; for (let i = 0; i < n; i++) c.push({ s: 'pop', t: 1.6 + i * ((D - 3.2) / Math.max(1, n - 1)) * (i ? 1 : 0), g: .5 }); for (let i = 1; i < n; i++) c.push({ s: 'whoosh', t: 1.8 + (i - 1) * ((D - 3.2) / Math.max(1, n - 1)), d: (D - 3.2) / Math.max(1, n - 1), g: .25 }); return c; },
  draw(ctx, t, D, p) {
    const st = p.stile; const G = window.GEO; if (!G) return;
    const cs = M.lines(p.percorso).map(cityOf).filter(Boolean);
    const sea = { 'Carta d\'epoca': '#e6dcc6', 'Verde campo': PAL.verdeScuro, 'Notte': '#07100d' }[st] || '#e6dcc6';
    const land = { 'Carta d\'epoca': '#d3c4a3', 'Verde campo': '#21483a', 'Notte': '#13211c' }[st];
    const coast = { 'Carta d\'epoca': 'rgba(60,45,25,.7)', 'Verde campo': rgba(PAL.carta, .5), 'Notte': rgba(PAL.fosforo, .35) }[st];
    const ink = st === 'Carta d\'epoca' ? PAL.inchiostro : PAL.carta;
    ctx.fillStyle = sea; ctx.fillRect(0, 0, W, H);
    if (st === 'Carta d\'epoca') { ctx.beginPath(); ctx.rect(0, 0, W, H); M.paperFill(ctx, '#e8d9b8', 2); }
    /* camera: dall'Europa al riquadro del percorso */
    const lons = cs.map(c => c.lon), lats = cs.map(c => merc(c.lat));
    const tb = cs.length ? [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)] : [7, 12, 40, 46];
    const fitBox = (b, pad) => { const cx = (b[0] + b[1]) / 2, cy = (b[2] + b[3]) / 2; const sx = (W - pad * 2) / Math.max(1, b[1] - b[0]), sy = (H - pad * 2) / Math.max(1, b[3] - b[2]); return { cx, cy, s: Math.min(sx, sy, 160) }; };
    const A = fitBox([-11, 32, merc(35), merc(60)], 40), B = fitBox(tb, 260);
    const k = E.io5(inv(.2, 2.2, t)); const s = Math.exp(lerp(Math.log(A.s), Math.log(B.s), k)) * (1 + .04 * inv(2.2, D, t));
    const cx = lerp(A.cx, B.cx, k), cy = lerp(A.cy, B.cy, k);
    const pr = (lon, lat) => [W / 2 + (lon - cx) * s, H / 2 - (merc(lat) - cy) * s];
    const prm = (lon, my) => [W / 2 + (lon - cx) * s, H / 2 - (my - cy) * s];
    /* reticolo */
    ctx.strokeStyle = rgba(ink, .08); ctx.lineWidth = 1;
    for (let lo = -30; lo <= 50; lo += 5) { const a = prm(lo, merc(70)), b = prm(lo, merc(20)); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }
    for (let la = 25; la <= 70; la += 5) { const a = pr(-40, la), b = pr(60, la); ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]); ctx.stroke(); }
    const drawPolys = (arr, fill, str, lw) => { ctx.beginPath(); for (const fl of arr) { for (let i = 0; i < fl.length; i += 2) { const q = pr(fl[i] / 100, fl[i + 1] / 100); i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); } ctx.closePath(); } if (fill) { ctx.fillStyle = fill; ctx.fill('evenodd'); } if (str) { ctx.strokeStyle = str; ctx.lineWidth = lw; ctx.lineJoin = 'round'; ctx.stroke(); } };
    ctx.save(); if (st !== 'Notte') { ctx.shadowColor = 'rgba(0,0,0,.25)'; ctx.shadowBlur = 12; ctx.shadowOffsetY = 4; }
    drawPolys(G.land, land, null); drawPolys(G.ita, p.italia ? (st === 'Carta d\'epoca' ? '#c9ae86' : st === 'Notte' ? '#1d3029' : '#2c5a49') : land, null); ctx.restore();
    drawPolys(G.land, null, coast, 1.2); drawPolys(G.ita, null, p.italia ? rgba(p.accento, .9) : coast, p.italia ? 2.2 : 1.2);
    if (st === 'Carta d\'epoca') { ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.save(); ctx.globalCompositeOperation = 'multiply'; ctx.globalAlpha = .55; M.paperFill(ctx, null, 2); ctx.restore(); }
    /* percorso */
    const n = cs.length; const seg = (D - 3.2) / Math.max(1, n - 1);
    const pts = cs.map(c => pr(c.lon, c.lat));
    for (let i = 1; i < n; i++) {
      const a = pts[i - 1], b = pts[i]; const kk = E.io3(inv(1.8 + (i - 1) * seg, 1.8 + (i - 1) * seg + seg * .85, t)); if (kk <= 0) continue;
      const d = Math.hypot(b[0] - a[0], b[1] - a[1]); const bend = d > 60 ? .22 : 0;
      const mxp = (a[0] + b[0]) / 2 + (a[1] - b[1]) * bend, myp = (a[1] + b[1]) / 2 + (b[0] - a[0]) * bend - d * .05;
      const curve = []; for (let j = 0; j <= 60; j++) { const u = j / 60, v = 1 - u; curve.push([v * v * a[0] + 2 * v * u * mxp + u * u * b[0], v * v * a[1] + 2 * v * u * myp + u * u * b[1]]); }
      ctx.save(); ctx.setLineDash([16, 10]); const r = M.stroke(ctx, curve, kk, 5, p.accento); ctx.restore();
      if (r && kk < 1) { ctx.save(); ctx.translate(r.tip[0], r.tip[1]); ctx.rotate(r.ang); ctx.fillStyle = p.accento; ctx.beginPath(); ctx.moveTo(14, 0); ctx.lineTo(-10, -10); ctx.lineTo(-5, 0); ctx.lineTo(-10, 10); ctx.closePath(); ctx.fill(); ctx.restore(); }
    }
    const placed = [];
    pts.forEach((q, i) => {
      const t0 = i === 0 ? 1.6 : 1.8 + (i - 1) * seg + seg * .85; const kk = ph(t, t0, .5, E.lin); if (kk <= 0) return;
      const drop = (1 - E.outBack(kk)) * -40;
      ctx.save(); ctx.globalAlpha *= clamp(kk * 3);
      if (st === 'Notte') { const g = ctx.createRadialGradient(q[0], q[1], 0, q[0], q[1], 60); g.addColorStop(0, rgba(PAL.fosforo, .35)); g.addColorStop(1, rgba(PAL.fosforo, 0)); ctx.fillStyle = g; ctx.fillRect(q[0] - 60, q[1] - 60, 120, 120); }
      ctx.strokeStyle = rgba(p.accento, .6 * (1 - inv(t0, t0 + 1.2, t))); ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(q[0], q[1], 10 + 40 * inv(t0, t0 + 1.2, t), 0, 7); ctx.stroke();
      ctx.fillStyle = p.accento; ctx.beginPath(); ctx.arc(q[0], q[1] + drop, 11, 0, 7); ctx.fill(); ctx.strokeStyle = PAL.carta; ctx.lineWidth = 3; ctx.stroke();
      const left = q[0] > W - 400; const lx = q[0] + (left ? -26 : 26);
      ctx.shadowColor = st === 'Carta d\'epoca' ? 'transparent' : 'rgba(0,0,0,.7)'; ctx.shadowBlur = 8;
      let ly = q[1] - 14; if (placed.some(o => Math.abs(o[0] - q[0]) < 220 && Math.abs(o[1] - ly) < 56)) ly = q[1] + 52; placed.push([q[0], ly]);
      T(ctx, cs[i].name.toUpperCase(), lx, ly, { size: 44, fam: F.display, tr: .02, color: ink, align: left ? 'right' : 'left' });
      ctx.restore();
    });
    /* titolo */
    alpha(ctx, ph(t, .4, .8), () => { ctx.fillStyle = st === 'Carta d\'epoca' ? rgba(PAL.carta, .85) : 'rgba(8,20,16,.75)'; M.font(ctx, 30, F.body, 600); const tw = M.textW(ctx, p.titolo, 30 * .22) + 70; ctx.fillRect(80, H - 150, tw * ph(t, .4, .7, E.film), 70); ctx.fillStyle = p.accento; ctx.fillRect(80, H - 150, 8, 70); mask(ctx, 80, H - 150, tw * ph(t, .4, .7, E.film), 70, () => T(ctx, p.titolo, 116, H - 104, { size: 30, weight: 600, tr: .22, color: ink })); });
    M.vignette(ctx, st === 'Carta d\'epoca' ? .3 : .5, st === 'Carta d\'epoca' ? '70,45,20' : '0,0,0');
    M.grain(ctx, t, p.grana * .4, false);
  }
});

/* =============================================================== TRANSIZIONI */
function field(key, w, h, sc, oct = 3) {
  const ck = 'field:' + key; if (M.cache.has(ck)) return M.cache.get(ck);
  const a = new Float32Array(w * h); for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) a[y * w + x] = M.fbm(x / sc + key * 7.3, y / sc + key * 3.1, oct); M.cache.set(ck, a); return a;
}
function lowres(w, h) { const ck = 'lr' + w + 'x' + h; let c = M.cache.get(ck); if (!c) { c = M.mk(w, h); M.cache.set(ck, c); } return c; }
const cutP = { k: 'nota', label: '', type: 'info' };

P.push({
  id: 't-pellicola', cat: 'Transizioni', name: 'Bruciatura pellicola', dur: 1.6, cut: .5, thumbT: .62, kind: 'transition',
  desc: 'La pellicola si incendia: macchie incandescenti che crescono dal bordo, nucleo bianco che copre lo stacco, alone arancio che si spegne.',
  tip: 'Metti il taglio tra le due clip esattamente sul punto rosso della barra: lì lo schermo è coperto. Per salti di decennio o cambi di capitolo.',
  params: [{ k: 'origine', label: 'Parte da', type: 'select', opts: ['Destra', 'Sinistra', 'Centro', 'Basso'], def: 'Destra' }, { k: 'calore', label: 'Colore', type: 'select', opts: ['Classico', 'Rosso profondo', 'Bianco'], def: 'Classico' }, grainP(.3)],
  sfx: (p, D) => [{ s: 'whoosh', t: 0, d: D * .55, g: .5 }, { s: 'flash', t: D * .48, g: .5 }, { s: 'static', t: D * .3, d: .5, g: .25 }],
  draw(ctx, t, D, p) {
    const w = 240, h = 135, f1 = field(11, w, h, 26, 4), f2 = field(12, w, h, 9, 2); const c = lowres(w, h), g = c.getContext('2d'); const im = g.createImageData(w, h), d = im.data;
    const cut = D * this.cut; const a = t < cut ? E.in2(t / cut) : 1 - E.out3((t - cut) / (D - cut)); const fade = t < cut ? 1 : 1 - E.in2((t - cut) / (D - cut));
    const pal = p.calore === 'Rosso profondo' ? [[255, 235, 200], [240, 90, 30], [140, 15, 10]] : p.calore === 'Bianco' ? [[255, 255, 250], [255, 230, 190], [180, 120, 80]] : [[255, 248, 225], [255, 160, 40], [190, 50, 10]];
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      const i = y * w + x; let gpos;
      const u = x / w, v = y / h;
      if (p.origine === 'Sinistra') gpos = 1 - u; else if (p.origine === 'Centro') gpos = 1 - Math.hypot(u - .5, (v - .5) * .6) * 1.6; else if (p.origine === 'Basso') gpos = v; else gpos = u;
      const n = f1[i] * .75 + f2[i] * .25 + gpos * .9 + Math.sin(t * 3 + u * 6) * .02;
      const val = n - (1.65 - a * 2.1);
      let r = 0, gg = 0, b = 0, al = 0;
      if (val > .22) { r = pal[0][0]; gg = pal[0][1]; b = pal[0][2]; al = 1; }
      else if (val > .06) { const k = (val - .06) / .16; r = lerp(pal[1][0], pal[0][0], k); gg = lerp(pal[1][1], pal[0][1], k); b = lerp(pal[1][2], pal[0][2], k); al = 1; }
      else if (val > -.08) { const k = (val + .08) / .14; r = lerp(pal[2][0], pal[1][0], k); gg = lerp(pal[2][1], pal[1][1], k); b = lerp(pal[2][2], pal[1][2], k); al = k * .95 + .05; }
      else if (val > -.2) { const k = (val + .2) / .12; r = 60; gg = 20; b = 8; al = k * .5; }
      const j = i * 4; d[j] = r; d[j + 1] = gg; d[j + 2] = b; d[j + 3] = al * 255 * fade;
    }
    g.putImageData(im, 0, 0);
    ctx.save(); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high'; ctx.filter = 'blur(5px)'; ctx.drawImage(c, -8, -8, W + 16, H + 16); ctx.filter = 'none';
    ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = .35 * fade * a; ctx.filter = 'blur(30px)'; ctx.drawImage(c, 0, 0, W, H); ctx.restore();
    M.grain(ctx, t, p.grana * .4, true);
  }
});

P.push({
  id: 't-carta', cat: 'Transizioni', name: 'Strappo di carta', dur: 1.5, cut: .45, thumbT: .75, kind: 'transition',
  desc: 'Un foglio d\'archivio entra a coprire l\'immagine e si strappa a metà: le due parti volano via con fibre bianche sul bordo dello strappo.',
  tip: 'Sul taglio il foglio è intero: è il momento per stampare sopra una data o un titolo con un altro preset.',
  params: [{ k: 'colore', label: 'Carta', type: 'select', opts: ['Avorio', 'Giornale', 'Kraft'], def: 'Avorio' }, { k: 'testo', label: 'Scritta sul foglio (facoltativa)', type: 'text', def: '' }, grainP(.25)],
  sfx: (p, D) => [{ s: 'whoosh', t: 0, d: .6, g: .5 }, { s: 'rip', t: D * .6, d: .55, g: .9 }],
  draw(ctx, t, D, p) {
    const cut = D * this.cut; const tint = { 'Avorio': null, 'Giornale': 'rgba(230,220,200,1)', 'Kraft': 'rgba(196,160,112,1)' }[p.colore];
    const enter = E.out3(inv(0, cut - .02, t)), part = E.in3(inv(cut, D, t));
    const sheet = (clipFn, dx, dy, rot, edgeFn) => {
      ctx.save(); ctx.translate(W / 2 + dx, H / 2 + dy); ctx.rotate(rot); ctx.translate(-W / 2, -H / 2);
      ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.55)'; ctx.shadowBlur = 50; clipFn(); ctx.fillStyle = '#eee'; ctx.fill(); ctx.restore();
      clipFn(); M.paperFill(ctx, tint, 1.8);
      ctx.save(); clipFn(); ctx.clip(); if (p.testo) T(ctx, p.testo.toUpperCase(), W / 2, H / 2 + 50, { size: 150, fam: F.display, color: PAL.inchiostro, align: 'center' }); M.vignette(ctx, .18, '80,50,20'); ctx.restore();
      if (edgeFn) edgeFn(); ctx.restore();
    };
    const vt = M.tearLine(-40, H + 40, 0, 26, 5).map(q => [q[1], q[0]]); /* bordo verticale strappato */
    const ht = M.tearLine(-60, W + 60, H / 2, 34, 9);
    const fib = (pts, side) => { ctx.save(); ctx.strokeStyle = 'rgba(255,255,252,.95)'; ctx.lineWidth = 7; ctx.lineJoin = 'round'; ctx.beginPath(); pts.forEach((q, i) => { const j = M.hash(i) * 4; i ? ctx.lineTo(q[0], q[1] + side * j) : ctx.moveTo(q[0], q[1]); }); ctx.stroke(); ctx.restore(); };
    if (t < cut) {
      const x0 = lerp(W + 80, -60, enter);
      sheet(() => { ctx.beginPath(); vt.forEach((q, i) => i ? ctx.lineTo(x0 + q[0], q[1]) : ctx.moveTo(x0 + q[0], q[1])); ctx.lineTo(W + 400, H + 50); ctx.lineTo(W + 400, -50); ctx.closePath(); }, 0, 0, 0, null);
    } else {
      const top = () => { ctx.beginPath(); ctx.moveTo(-200, -300); ht.forEach(q => ctx.lineTo(q[0], q[1])); ctx.lineTo(W + 200, -300); ctx.closePath(); };
      const bot = () => { ctx.beginPath(); ctx.moveTo(-200, H + 300); ht.forEach(q => ctx.lineTo(q[0], q[1])); ctx.lineTo(W + 200, H + 300); ctx.closePath(); };
      sheet(top, -part * 120, -part * (H * .75), -part * .12, () => fib(ht, -1));
      sheet(bot, part * 140, part * (H * .78), part * .1, () => fib(ht, 1));
    }
    M.grain(ctx, t, p.grana * .5, true);
  }
});

P.push({
  id: 't-inchiostro', cat: 'Transizioni', name: 'Macchia d\'inchiostro', dur: 1.8, cut: .5, thumbT: .7, kind: 'transition',
  desc: 'Gocce d\'inchiostro che si allargano e si fondono fino a coprire lo schermo, poi si ritirano con un disegno diverso. Bordi organici, schizzi.',
  tip: 'In verde campo diventa la transizione del tuo canale. In rosso funziona per i momenti drammatici (espulsioni, tragedie).',
  params: [{ k: 'colore', label: 'Inchiostro', type: 'color', def: PAL.verdeScuro }, grainP(.25)],
  sfx: (p, D) => [{ s: 'whoosh', t: 0, d: D * .5, g: .4 }, { s: 'sub', t: D * .45, g: .4 }, { s: 'whoosh', t: D * .5, d: D * .45, g: .3 }],
  draw(ctx, t, D, p) {
    const w = 320, h = 180, nf = field(21, w, h, 16, 3), nf2 = field(22, w, h, 12, 3); const c = lowres(w, h), g = c.getContext('2d'); const im = g.createImageData(w, h), d = im.data;
    const cut = D * this.cut; const first = t < cut;
    const a = first ? E.in2(t / cut) : 1 - E.out2((t - cut) / (D - cut));
    const r = M.rng(first ? 4 : 8); const blobs = []; for (let i = 0; i < 7; i++) blobs.push([r() * w, r() * h, .55 + r() * .6, r() * .35]);
    const hx = parseInt(p.colore.slice(1), 16); const cr = hx >> 16 & 255, cg = hx >> 8 & 255, cb = hx & 255;
    const nn = first ? nf : nf2;
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
      let f = -1;
      for (const [bx, by, sz, del] of blobs) { const k = clamp((a - del * (first ? 1 : 0)) / (1 - del * (first ? 1 : 0))); const R = k * sz * 260; const dd = Math.hypot(x - bx, (y - by) * 1.1); f = Math.max(f, (R - dd) / 60); }
      f += (nn[y * w + x] - .5) * .9;
      const al = smooth(-.05, .05, f); const j = (y * w + x) * 4; d[j] = cr; d[j + 1] = cg; d[j + 2] = cb; d[j + 3] = al * 255;
    }
    g.putImageData(im, 0, 0);
    ctx.save(); ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = 'high'; ctx.drawImage(c, 0, 0, W, H); ctx.restore();
    /* schizzi */
    if (first && a > .05 && a < .9) { const rs = M.rng(31); ctx.fillStyle = p.colore; for (let i = 0; i < 40; i++) { const bx = rs() * W, by = rs() * H, s = (2 + rs() * 12) * clamp(a * 3); if (rs() < a + .2) { ctx.beginPath(); ctx.arc(bx, by, s, 0, 7); ctx.fill(); } } }
    M.grain(ctx, t, p.grana * .4, true);
  }
});

P.push({
  id: 't-luce', cat: 'Transizioni', name: 'Luce calda', dur: 2.2, cut: .48, thumbT: .9, kind: 'transition',
  desc: 'Infiltrazione di luce da pellicola: fasci arancio e rossi che attraversano il quadro e sbiancano lo stacco.',
  tip: 'Esporta su nero e nel programma di montaggio metti il livello in modalità "Scherma" (Screen): il nero sparisce e resta solo la luce.',
  params: [{ k: 'tinta', label: 'Tinta', type: 'select', opts: ['Ambra', 'Rosso', 'Freddo'], def: 'Ambra' }, { k: 'intensita', label: 'Intensità', type: 'range', min: .3, max: 1.2, step: .05, def: .9 }],
  sfx: (p, D) => [{ s: 'whoosh', t: .1, d: D * .8, g: .35 }],
  draw(ctx, t, D, p) {
    const cut = D * this.cut; const a = t < cut ? E.io3(t / cut) : 1 - E.io3((t - cut) / (D - cut));
    const cols = { 'Ambra': [[255, 170, 60], [255, 90, 30], [255, 230, 170]], 'Rosso': [[255, 70, 50], [190, 30, 40], [255, 180, 140]], 'Freddo': [[120, 190, 255], [80, 120, 255], [220, 240, 255]] }[p.tinta];
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const r = M.rng(5); const sweep = t / D;
    for (let i = 0; i < 6; i++) {
      const c = cols[i % 3]; const x = lerp(-600, W + 600, sweep * (.8 + r() * .5) + r() * .2 - .1), y = H * (.2 + r() * .6) + M.wobble(t, i) * 120; const rad = 500 + r() * 700;
      const g = ctx.createRadialGradient(x, y, 0, x, y, rad); g.addColorStop(0, `rgba(${c[0]},${c[1]},${c[2]},${(.55 * a * p.intensita).toFixed(3)})`); g.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]},0)`);
      ctx.fillStyle = g; ctx.fillRect(x - rad, y - rad, rad * 2, rad * 2);
    }
    /* fascio verticale */
    const bx = lerp(-200, W + 200, E.io3(sweep)); const g2 = ctx.createLinearGradient(bx - 300, 0, bx + 300, 0); const c = cols[2];
    g2.addColorStop(0, `rgba(${c[0]},${c[1]},${c[2]},0)`); g2.addColorStop(.5, `rgba(${c[0]},${c[1]},${c[2]},${(.7 * a * p.intensita).toFixed(3)})`); g2.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]},0)`);
    ctx.fillStyle = g2; ctx.fillRect(0, 0, W, H);
    const peak = Math.max(0, 1 - Math.abs(t - cut) / .18); if (peak > 0) { ctx.fillStyle = `rgba(255,245,225,${(peak * .85 * p.intensita).toFixed(3)})`; ctx.fillRect(0, 0, W, H); }
    ctx.restore();
  }
});

P.push({
  id: 't-flash', cat: 'Transizioni', name: 'Flash fotografico', dur: 1.2, cut: .08, thumbT: .2, kind: 'transition',
  desc: 'Il lampo al magnesio dei fotografi d\'epoca: bianco pieno, alone caldo che si spegne lentamente e una nuvola di fumo.',
  tip: 'Metti il taglio sul lampo e fai entrare una foto ferma: è il modo classico per "scattare" un\'immagine d\'archivio. Suono dell\'otturatore incluso.',
  params: [{ k: 'fumo', label: 'Fumo del magnesio', type: 'bool', def: true }, { k: 'caldo', label: 'Alone caldo', type: 'bool', def: true }],
  sfx: (p, D) => [{ s: 'shutter', t: 0, g: .9 }, { s: 'flash', t: D * .08, g: .9 }],
  draw(ctx, t, D, p) {
    const k = t / D; const f = k < .08 ? E.in2(k / .08) : 1 - E.out3((k - .08) / .92);
    ctx.fillStyle = `rgba(255,255,255,${(Math.pow(f, 1.6)).toFixed(3)})`; ctx.fillRect(0, 0, W, H);
    if (p.caldo) { const g = ctx.createRadialGradient(W * .55, H * .42, 0, W * .55, H * .42, W * .7); g.addColorStop(0, `rgba(255,220,160,${(f * .5).toFixed(3)})`); g.addColorStop(1, 'rgba(255,200,140,0)'); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); }
    if (p.fumo) { const r = M.rng(3); const sk = inv(.05, 1, k); ctx.save(); ctx.filter = 'blur(40px)'; for (let i = 0; i < 9; i++) { const x = W * (.35 + r() * .4) + sk * (r() - .3) * 300, y = H * (.3 + r() * .2) - sk * 260 * r(); const rad = 120 + sk * 300 * r(); ctx.fillStyle = `rgba(235,232,225,${(.22 * (1 - sk) * clamp(sk * 6)).toFixed(3)})`; ctx.beginPath(); ctx.arc(x, y, rad, 0, 7); ctx.fill(); } ctx.restore(); }
  }
});

P.push({
  id: 't-barre', cat: 'Transizioni', name: 'Barre del canale', dur: 1.3, cut: .46, thumbT: .6, kind: 'transition',
  desc: 'Transizione grafica di marca: barre oblique nei colori del canale che attraversano il quadro, con il nome del canale sul taglio.',
  tip: 'Usala sempre uguale, solo per i cambi di sezione: diventa la firma riconoscibile del tuo canale.',
  params: [{ k: 'testo', label: 'Scritta sul taglio', type: 'text', def: 'CAPITOLO II' }, { k: 'tavolozza', label: 'Colori', type: 'select', opts: ['Canale', 'Granata', 'Azzurro', 'Bianco e nero'], def: 'Canale' }],
  sfx: (p, D) => [{ s: 'whoosh', t: 0, d: D * .55, g: .6 }, { s: 'hit', t: D * .48, g: .6 }, { s: 'whoosh', t: D * .6, d: D * .4, g: .4 }],
  draw(ctx, t, D, p) {
    const pal = { 'Canale': [PAL.carta, PAL.rosso, PAL.inchiostro, PAL.verde], 'Granata': [PAL.carta, '#b43a3a', '#5c1420', '#3b0d16'], 'Azzurro': ['#ffffff', '#3a7bd5', '#1f3f8c', '#0e1f45'], 'Bianco e nero': ['#ffffff', '#8a8a8a', '#2a2a2a', '#0b0b0b'] }[p.tavolozza];
    const cut = D * this.cut; const sk = H * .36;
    pal.forEach((c, i) => {
      const a = E.swift(inv(i * .06, cut - (3 - i) * .03, t)), b = E.swift(inv(cut + i * .05, D - (3 - i) * .02, t));
      const x0 = lerp(-sk - 40, W + sk, b) , x1 = lerp(-sk - 40, W + sk + 40, a);
      if (x1 <= x0) return;
      ctx.fillStyle = c; ctx.beginPath(); ctx.moveTo(x0 + sk, 0); ctx.lineTo(x1 + sk, 0); ctx.lineTo(x1, H); ctx.lineTo(x0, H); ctx.closePath(); ctx.fill();
    });
    const tk = 1 - Math.abs(t - cut) / .22; if (tk > 0 && p.testo) { ctx.save(); ctx.globalAlpha = clamp(tk * 2); const s = 1 + (t - cut) * .25; ctx.translate(W / 2, H / 2); ctx.scale(s, s); T(ctx, p.testo.toUpperCase(), 0, 60, { size: 170, fam: F.display, tr: .02, color: pal[0], align: 'center' }); ctx.restore(); }
  }
});

P.push({
  id: 't-vhs', cat: 'Transizioni', name: 'Disturbo VHS', dur: 1.1, cut: .45, thumbT: .5, kind: 'transition',
  desc: 'Salto di nastro: bande di tracking, sfasamento di colore e neve piena sul taglio. Perfetto per passare agli anni \'80–\'90.',
  tip: 'Abbinala alla texture "Videocassetta" sulla clip successiva per un passaggio d\'epoca credibile.',
  params: [{ k: 'play', label: 'Scritta PLAY', type: 'bool', def: true }],
  sfx: (p, D) => [{ s: 'static', t: D * .2, d: D * .6, g: .8 }, { s: 'glitch', t: D * .1, d: D * .3, g: .6 }],
  draw(ctx, t, D, p) {
    const cut = D * this.cut; const a = 1 - Math.abs(t - cut) / cut; const amt = clamp(a) ** 1.4;
    const f = Math.floor(t * 30); const r = M.rng(f * 13 + 7);
    const tiles = M.cache.get('snow') || (() => { const arr = []; for (let k = 0; k < 4; k++) { const c = M.mk(320, 180), g = c.getContext('2d'), im = g.createImageData(320, 180), rr = M.rng(k * 99 + 1); for (let i = 0; i < im.data.length; i += 4) { const v = rr() * 255; im.data[i] = im.data[i + 1] = im.data[i + 2] = v; im.data[i + 3] = 255; } g.putImageData(im, 0, 0); arr.push(c); } M.cache.set('snow', arr); return arr; })();
    const snow = tiles[f % 4];
    const full = amt > .78;
    if (full) { ctx.drawImage(snow, 0, 0, W, H); }
    const bands = Math.floor(3 + amt * 10);
    for (let i = 0; i < bands; i++) {
      const y = r() * H, h = 8 + r() * 80 * amt; const off = (r() - .5) * 140 * amt;
      ctx.save(); ctx.globalAlpha = .4 + amt * .6; ctx.drawImage(snow, 0, (y / H) * 180, 320, Math.max(1, h / 6), off, y, W, h); ctx.restore();
      ctx.fillStyle = `rgba(255,40,60,${(.25 * amt).toFixed(3)})`; ctx.fillRect(off + 8, y, W, h * .5); ctx.fillStyle = `rgba(40,220,255,${(.2 * amt).toFixed(3)})`; ctx.fillRect(off - 8, y + h * .5, W, h * .5);
    }
    const ry = ((t * 1.8) % 1) * H; ctx.fillStyle = `rgba(255,255,255,${(.12 * amt).toFixed(3)})`; ctx.fillRect(0, ry, W, 60);
    if (p.play && t > cut) { const k = (Math.floor(t * 4) % 2) ? 1 : .6; ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 4; T(ctx, 'PLAY ▶', 120, 150, { size: 72, fam: F.mono, color: `rgba(255,255,255,${k})` }); ctx.restore(); }
  }
});

P.push({
  id: 't-rullo', cat: 'Transizioni', name: 'Scorrimento pellicola', dur: 1.0, cut: .5, thumbT: .45, kind: 'transition',
  desc: 'La pellicola salta nel proiettore: la striscia con le perforazioni scorre in verticale con sfocatura di movimento e l\'interfotogramma nasconde il taglio.',
  tip: 'Funziona bene tra due filmati d\'archivio in bianco e nero, soprattutto con il suono del proiettore sotto.',
  params: [{ k: 'numeri', label: 'Numeri di bordo pellicola', type: 'bool', def: true }],
  sfx: (p, D) => [{ s: 'projector', t: 0, d: D, g: .9 }, { s: 'whoosh', t: D * .25, d: D * .5, g: .5 }],
  draw(ctx, t, D, p) {
    const cut = D * this.cut; const off = (E.ioExpo(t / D) * 2 - 1) * H * 1.15; const speed = Math.abs(E.ioExpo(Math.min(1, t / D + .01)) - E.ioExpo(t / D)) * 100;
    const blur = Math.min(24, speed * 6);
    ctx.save(); if (blur > 1) ctx.filter = `blur(${blur.toFixed(1)}px)`;
    for (let k = -2; k <= 2; k++) {
      const y = H / 2 + k * H - off;
      ctx.fillStyle = '#0a0908'; ctx.fillRect(0, y - H / 2 - 60, W, 120); /* interfotogramma */
      ctx.fillRect(0, y - H / 2, 150, H); ctx.fillRect(W - 150, y - H / 2, 150, H);
      ctx.fillStyle = '#e8e4da'; for (let s = 0; s < 6; s++) { const yy = y - H / 2 + 50 + s * (H / 6); M.rr(ctx, 45, yy, 60, 90, 10); ctx.fill(); M.rr(ctx, W - 105, yy, 60, 90, 10); ctx.fill(); }
      if (p.numeri) { ctx.save(); ctx.translate(128, y); ctx.rotate(-Math.PI / 2); T(ctx, 'KODAK SAFETY FILM  ' + (24 + k + 2) + '▸', 0, 0, { size: 26, fam: F.mono, color: 'rgba(255,190,90,.75)', align: 'center' }); ctx.restore(); }
    }
    ctx.restore();
    const fl = 1 - Math.abs(t - cut) / .1; if (fl > 0) { ctx.fillStyle = `rgba(255,250,240,${(fl * .5).toFixed(3)})`; ctx.fillRect(0, 0, W, H); }
  }
});

/* =============================================================== TEXTURE (in loop) */
P.push({
  id: 'o-pellicola', cat: 'Texture', name: 'Pellicola d\'epoca', dur: 6, thumbT: 2, kind: 'loop',
  desc: 'Tutto il carattere della pellicola 16 mm: grana viva, polvere, peli, graffi, sfarfallio di esposizione, bordi bruciati e vignetta. Si ripete senza stacchi.',
  tip: 'Mettila sopra a tutto il materiale d\'archivio. Se la esporti su grigio 50%, usa la modalità di fusione "Sovrapponi" (Overlay) nel montaggio.',
  params: [
    { k: 'grana', label: 'Grana', type: 'range', min: 0, max: 1, step: .05, def: .55 },
    { k: 'polvere', label: 'Polvere e peli', type: 'range', min: 0, max: 2, step: .1, def: 1 },
    { k: 'graffi', label: 'Graffi continui', type: 'bool', def: true },
    { k: 'sfarfallio', label: 'Sfarfallio', type: 'range', min: 0, max: 1, step: .05, def: .35 },
    { k: 'vignetta', label: 'Vignetta', type: 'range', min: 0, max: 1, step: .05, def: .55 },
    { k: 'bruciato', label: 'Bordi bruciati', type: 'bool', def: true },
    { k: 'base', label: 'Base', type: 'select', opts: ['Trasparente', 'Grigio 50%'], def: 'Trasparente' }
  ],
  sfx: (p, D) => [{ s: 'projector', t: 0, d: D, g: .7 }],
  draw(ctx, t, D, p) {
    if (p.base === 'Grigio 50%') { ctx.fillStyle = '#808080'; ctx.fillRect(0, 0, W, H); }
    const f = Math.floor(t * 24); const fl = (M.hash(f * 1.3) - .5) * p.sfarfallio;
    ctx.fillStyle = fl > 0 ? `rgba(255,248,235,${(fl * .22).toFixed(3)})` : `rgba(0,0,0,${(-fl * .3).toFixed(3)})`; ctx.fillRect(0, 0, W, H);
    M.grain(ctx, t, p.grana * .6, false);
    M.filmDirt(ctx, t, p.polvere, { scratches: p.graffi });
    if (p.bruciato) {
      const k = .75 + M.wobble(t, 3, 2) * .2;
      for (const [x0, x1] of [[0, 260], [W, W - 260]]) { const g = ctx.createLinearGradient(x0, 0, x1, 0); g.addColorStop(0, `rgba(70,30,10,${(.55 * k).toFixed(3)})`); g.addColorStop(.35, `rgba(140,70,20,${(.18 * k).toFixed(3)})`); g.addColorStop(1, 'rgba(140,70,20,0)'); ctx.fillStyle = g; ctx.fillRect(Math.min(x0, x1), 0, 260, H); }
    }
    M.vignette(ctx, p.vignetta * .75, '10,6,2', .38);
    /* pelo nel corridoio del proiettore */
    if (Math.floor(t * 24 / 36) % 3 === 1) { const r = M.rng(Math.floor(t * 24 / 36)); ctx.strokeStyle = 'rgba(10,8,6,.6)'; ctx.lineWidth = 2; ctx.beginPath(); const x = W * (.1 + r() * .8); ctx.moveTo(x, H); ctx.bezierCurveTo(x + 40, H - 120, x - 30 + M.wobble(t * 8, 2) * 6, H - 200, x + 20, H - 260); ctx.stroke(); }
  }
});

P.push({
  id: 'o-vhs', cat: 'Texture', name: 'Videocassetta', dur: 6, thumbT: 1.5, kind: 'loop',
  desc: 'Registrazione su nastro: linee di scansione, banda di disturbo che scorre, rumore di cambio testina in basso, scritte a schermo con data e ora che avanzano.',
  tip: 'Per le partite anni \'80–\'90 registrate dalla TV. Imposta la data reale della partita: è il dettaglio che fa credere al pubblico che sia un nastro vero.',
  params: [
    { k: 'osd', label: 'Scritta in alto', type: 'text', def: 'PLAY ▶' },
    { k: 'data', label: 'Data', type: 'text', def: 'MAG. 25 1994' },
    { k: 'ora', label: 'Ora di partenza', type: 'text', def: '20:31:07' },
    { k: 'intensita', label: 'Intensità', type: 'range', min: 0, max: 1, step: .05, def: .6 },
    { k: 'sfondo', label: 'Sfondo', type: 'select', opts: ['Trasparente', 'Nero'], def: 'Trasparente' }
  ],
  sfx: (p, D) => [{ s: 'static', t: 0, d: .3, g: .4 }],
  draw(ctx, t, D, p) {
    if (p.sfondo === 'Nero') { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); }
    const I = p.intensita;
    ctx.fillStyle = `rgba(0,0,0,${(.18 * I).toFixed(3)})`; for (let y = 0; y < H; y += 4) ctx.fillRect(0, y, W, 2);
    const ry = ((t * .12) % 1) * (H + 200) - 100; const g = ctx.createLinearGradient(0, ry - 60, 0, ry + 60); g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(.5, `rgba(255,255,255,${(.09 * I).toFixed(3)})`); g.addColorStop(1, 'rgba(255,255,255,0)'); ctx.fillStyle = g; ctx.fillRect(0, ry - 60, W, 120);
    const f = Math.floor(t * 30), r = M.rng(f);
    ctx.fillStyle = `rgba(230,230,230,${(.35 * I).toFixed(3)})`; for (let i = 0; i < 30; i++) ctx.fillRect(r() * W, H - 34 + r() * 30, 20 + r() * 160, 2);
    ctx.fillStyle = `rgba(0,0,0,${(.35 * I).toFixed(3)})`; ctx.fillRect(0, H - 34, W, 34);
    if (r() < .12 * I) { const y = r() * H; for (let i = 0; i < 5; i++) { ctx.fillStyle = `rgba(255,255,255,${(.3 * r()).toFixed(3)})`; ctx.fillRect(0, y + i * 3, W, 1); } }
    M.grain(ctx, t, .25 * I, false, 30);
    const osd = (s, x, y, al = 'left') => { T(ctx, s, x + 3, y + 3, { size: 64, fam: F.mono, color: 'rgba(0,0,0,.55)', align: al }); T(ctx, s, x - 2, y, { size: 64, fam: F.mono, color: 'rgba(255,60,80,.45)', align: al }); T(ctx, s, x + 2, y, { size: 64, fam: F.mono, color: 'rgba(60,220,255,.45)', align: al }); T(ctx, s, x, y, { size: 64, fam: F.mono, color: '#f4f4f0', align: al }); };
    if (t > 2.5 || Math.floor(t * 2) % 2 === 0) osd(p.osd, 120, 150);
    const m = String(p.ora).match(/(\d+):(\d+):(\d+)/); let tt = m ? (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) + Math.floor(t) : Math.floor(t);
    const hh = Math.floor(tt / 3600) % 24, mm = Math.floor(tt / 60) % 60, ss = tt % 60; const pm = hh >= 12 ? 'PM' : 'AM';
    osd(`${pm} ${String((hh % 12) || 12).padStart(2, ' ')}:${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`, W - 120, H - 110, 'right');
    osd(p.data, 120, H - 110);
  }
});

P.push({
  id: 'o-mirino', cat: 'Texture', name: 'Mirino REC', dur: 6, thumbT: 1.2, kind: 'loop',
  desc: 'Interfaccia di telecamera: angoli del mirino, punto REC che lampeggia, timecode che scorre, batteria, parametri di ripresa e messa a fuoco che si aggancia.',
  tip: 'Per le interviste girate da te o per far sembrare "girato sul posto" un tuo sopralluogo allo stadio.',
  params: [
    { k: 'info', label: 'Parametri', type: 'text', def: 'ISO 800   1/50   F2.8   4K 25P' },
    { k: 'tc', label: 'Timecode iniziale', type: 'text', def: '00:14:32:00' },
    accentP()
  ],
  sfx: () => [{ s: 'tick', t: .4, g: .7 }, { s: 'tick', t: .5, g: .7 }],
  draw(ctx, t, D, p, env) {
    const c = PAL.carta; ctx.strokeStyle = c; ctx.lineWidth = 4; const m = 90, L = 90;
    ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 6;
    for (const [x, y, sx, sy] of [[m, m, 1, 1], [W - m, m, -1, 1], [m, H - m, 1, -1], [W - m, H - m, -1, -1]]) { ctx.beginPath(); ctx.moveTo(x, y + sy * L); ctx.lineTo(x, y); ctx.lineTo(x + sx * L, y); ctx.stroke(); }
    if (Math.floor(t * 1.6) % 2 === 0) { ctx.fillStyle = p.accento; ctx.beginPath(); ctx.arc(m + 70, m + 74, 15, 0, 7); ctx.fill(); }
    T(ctx, 'REC', m + 100, m + 88, { size: 42, weight: 600, color: c });
    const m2 = String(p.tc).match(/(\d+):(\d+):(\d+):(\d+)/); const fps = env.fps || 25; let fr = m2 ? (((+m2[1]) * 60 + (+m2[2])) * 60 + (+m2[3])) * fps + (+m2[4]) : 0; fr += Math.floor(t * fps);
    const ff = fr % fps, s = Math.floor(fr / fps) % 60, mi = Math.floor(fr / fps / 60) % 60, hh = Math.floor(fr / fps / 3600);
    T(ctx, `TC ${[hh, mi, s, ff].map(v => String(v).padStart(2, '0')).join(':')}`, W - m - 30, m + 88, { size: 40, fam: F.mono, color: c, align: 'right' });
    T(ctx, p.info, W / 2, H - m - 40, { size: 30, weight: 500, tr: .1, color: c, align: 'center' });
    /* batteria */
    ctx.lineWidth = 3; ctx.strokeRect(m + 30, H - m - 76, 70, 32); ctx.fillStyle = c; ctx.fillRect(m + 100, H - m - 66, 6, 12); ctx.fillRect(m + 36, H - m - 70, 44, 20);
    /* messa a fuoco */
    const fk = E.outBack(inv(.2, .9, t)); const sz = lerp(260, 160, fk) + (t < .9 ? Math.sin(t * 30) * 8 * (1 - fk) : 0);
    ctx.strokeStyle = t > .9 ? c : rgba(c, .7); ctx.lineWidth = 3; const cx = W / 2, cy = H / 2, q = 26;
    for (const [sx, sy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) { ctx.beginPath(); ctx.moveTo(cx + sx * sz / 2, cy + sy * (sz / 2 - q)); ctx.lineTo(cx + sx * sz / 2, cy + sy * sz / 2); ctx.lineTo(cx + sx * (sz / 2 - q), cy + sy * sz / 2); ctx.stroke(); }
    ctx.lineWidth = 2; M.cross(ctx, cx, cy, 12, 2);
    ctx.restore();
  }
});

P.push({
  id: 'o-cornice', cat: 'Texture', name: 'Cornice d\'archivio', dur: 6, thumbT: 2, kind: 'loop',
  desc: 'La cornice di registro del tuo design system con la dicitura di materiale d\'archivio e la fonte, bande cinema opzionali e anno in sovraimpressione.',
  tip: 'Citare la fonte del materiale ti protegge e dà autorevolezza. Tienila su tutte le clip d\'archivio della stessa provenienza.',
  params: [
    { k: 'etichetta', label: 'Etichetta', type: 'text', def: 'MATERIALE D\'ARCHIVIO' },
    { k: 'fonte', label: 'Fonte', type: 'text', def: 'Fonte: Archivio Storico Luce' },
    { k: 'anno', label: 'Anno in sovraimpressione', type: 'text', def: '1949' },
    { k: 'bande', label: 'Bande cinema 2,39:1', type: 'bool', def: false },
    accentP(), grainP(.3)
  ],
  sfx: () => [],
  draw(ctx, t, D, p) {
    if (p.bande) { const bh = (H - W / 2.39) / 2 * E.film(inv(0, 1, t)); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, bh); ctx.fillRect(0, H - bh, W, bh); }
    const ip = ph(t, 0, 1.2, E.film);
    M.regFrame(ctx, 60, 60, W - 120, H - 120, ip, PAL.carta, .55);
    alpha(ctx, ph(t, .5, .6), () => {
      ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 8;
      const y0 = p.bande ? (H - W / 2.39) / 2 + 60 : 116;
      ctx.fillStyle = p.accento; ctx.fillRect(100, y0 - 22, 14, 14);
      T(ctx, p.etichetta.toUpperCase(), 128, y0 - 9, { size: 22, weight: 600, tr: .28, color: PAL.carta });
      T(ctx, p.fonte, W - 100, H - (p.bande ? (H - W / 2.39) / 2 + 40 : 96), { size: 22, weight: 500, tr: .04, color: rgba(PAL.carta, .85), align: 'right' });
      if (p.anno) T(ctx, p.anno, W - 100, y0 + 30, { size: 72, fam: F.display, color: rgba(PAL.carta, .9), align: 'right' });
      ctx.restore();
    });
    M.grain(ctx, t, p.grana * .5, true);
  }
});

/* =============================================================== CAMERA (sul tuo materiale) */
const toneP = (def = 'Bianco e nero') => ({ k: 'tono', label: 'Tono', type: 'select', opts: M.TONES, def });
function src(env, p) { return M.toned(env.media || M.samplePhoto(), p.tono || 'Originale', env.mediaKey || 'sample'); }
function look(ctx, t, p) { M.vignette(ctx, (p.vignetta ?? .4) * .8); if (p.polvere) M.filmDirt(ctx, t, .6); M.grain(ctx, t, (p.grana ?? .3) * .45, false); }
const camExtras = [{ k: 'vignetta', label: 'Vignetta', type: 'range', min: 0, max: 1, step: .05, def: .45 }, { k: 'polvere', label: 'Polvere di pellicola', type: 'bool', def: false }, grainP(.35)];

P.push({
  id: 'z-dettaglio', cat: 'Camera', name: 'Zoom sul dettaglio', dur: 7, thumbT: 4.5, media: true,
  desc: 'La camera entra nella foto fino al dettaglio, il resto si scurisce, un cerchio a pennarello circonda il soggetto e una nota scritta a mano lo indica con una freccia.',
  tip: 'Clicca sull\'anteprima per scegliere il punto. È il preset da usare per "trovare" un giocatore in una foto di squadra o un dettaglio in una tribuna.',
  params: [
    { k: 'punto', label: 'Punto (clicca sull\'anteprima)', type: 'point', def: [.58, .6] },
    { k: 'zoom', label: 'Ingrandimento', type: 'range', min: 1.2, max: 4, step: .1, def: 2.4 },
    { k: 'forma', label: 'Segno', type: 'select', opts: ['Cerchio a mano', 'Riflettore', 'Riquadro di registro', 'Nessuno'], def: 'Cerchio a mano' },
    { k: 'raggio', label: 'Dimensione del segno', type: 'range', min: 60, max: 360, step: 5, def: 170 },
    { k: 'nota', label: 'Nota scritta a mano', type: 'text', def: 'Valentino Mazzola' },
    toneP(), accentP(), ...camExtras
  ],
  sfx: () => [{ s: 'whoosh', t: .6, d: 2.2, g: .35 }, { s: 'chalk', t: 2.9, d: .7, g: .5 }, { s: 'chalk', t: 3.6, d: .6, g: .35 }],
  draw(ctx, t, D, p, env) {
    const s = src(env, p); const [u, v] = p.punto;
    const z = lerp(1, p.zoom, E.io5(inv(.5, 2.9, t))) * (1 + .03 * inv(2.9, D, t));
    ctx.save(); const [tx, ty] = M.camOn(ctx, z, u, v); M.cover(ctx, s, 0, 0, W, H); ctx.restore();
    const sx = u * W * z + tx, sy = v * H * z + ty, R = p.raggio;
    const dk = ph(t, 2.4, .9, E.io3);
    if (dk > 0 && p.forma !== 'Nessuno') {
      const strong = p.forma === 'Riflettore' ? .82 : .55;
      const g = ctx.createRadialGradient(sx, sy, R * 1.05, sx, sy, R * 3.2); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, `rgba(0,0,0,${(strong * dk).toFixed(3)})`); ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    }
    const cp = ph(t, 2.8, .75, E.io3);
    if (p.forma === 'Cerchio a mano') M.stroke(ctx, M.handEllipse(sx, sy, R * 1.12, R * 1.0, 3), cp, Math.max(6, R * .05), p.accento, { taper: true });
    else if (p.forma === 'Riquadro di registro') M.regFrame(ctx, sx - R, sy - R, R * 2, R * 2, cp, PAL.carta, .9, 2.5);
    else if (p.forma === 'Riflettore') { ctx.strokeStyle = rgba(PAL.carta, .6 * cp); ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(sx, sy, R * 1.05, 0, Math.PI * 2 * cp); ctx.stroke(); }
    if (p.nota) {
      const right = sx < W * .58; const lx = right ? sx + R * 1.5 + 60 : sx - R * 1.5 - 60, ly = Math.max(140, sy - R * 1.3);
      const np = ph(t, 3.4, .9, E.lin);
      M.font(ctx, 64, F.hand); const tw = ctx.measureText(p.nota.toUpperCase()).width;
      ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.75)'; ctx.shadowBlur = 10;
      mask(ctx, right ? lx : lx - tw * np, ly - 70, tw * np + 10, 100, () => T(ctx, p.nota.toUpperCase(), lx, ly, { size: 64, fam: F.hand, color: PAL.carta, align: right ? 'left' : 'right' }));
      const ap = ph(t, 3.5, .5, E.io3); const ax0 = right ? lx - 14 : lx + 14, ay0 = ly + 6; const ang = Math.atan2(sy - ay0, sx - ax0); const ax1 = sx - Math.cos(ang) * R * 1.2, ay1 = sy - Math.sin(ang) * R * 1.1;
      const r = M.stroke(ctx, M.handCurve(ax0, ay0, ax1, ay1, right ? -.2 : .2, 4, 30), ap, 5, PAL.carta); if (r) M.arrowHead(ctx, r.tip[0], r.tip[1], r.ang, 20, PAL.carta, 5, ap >= .98 ? 1 : 0);
      ctx.restore();
    }
    look(ctx, t, p);
  }
});

P.push({
  id: 'z-kenburns', cat: 'Camera', name: 'Ken Burns', dur: 8, thumbT: 4, media: true,
  desc: 'Il movimento lento su foto ferma, fatto bene: punto di partenza e di arrivo scelti da te, curva morbida, leggera rotazione e "respiro" di camera a mano.',
  tip: 'Movimenti lenti per i momenti emotivi, più ampi per l\'azione. Una regola: la camera deve sempre andare verso ciò di cui sta parlando la voce.',
  params: [
    { k: 'punto', label: 'Punto di partenza', type: 'point', def: [.35, .45] },
    { k: 'punto2', label: 'Punto di arrivo', type: 'point', def: [.62, .55] },
    { k: 'z0', label: 'Zoom iniziale', type: 'range', min: 1, max: 3, step: .05, def: 1.05 },
    { k: 'z1', label: 'Zoom finale', type: 'range', min: 1, max: 3, step: .05, def: 1.45 },
    { k: 'curva', label: 'Curva', type: 'select', opts: ['Morbida', 'Lineare', 'Decisa'], def: 'Morbida' },
    { k: 'ruota', label: 'Rotazione (gradi)', type: 'range', min: -5, max: 5, step: .25, def: 1 },
    { k: 'respiro', label: 'Respiro di camera a mano', type: 'bool', def: true },
    toneP('Originale'), ...camExtras
  ],
  sfx: () => [],
  draw(ctx, t, D, p, env) {
    const s = src(env, p); const ez = { 'Morbida': E.glide, 'Lineare': E.lin, 'Decisa': E.io5 }[p.curva] || E.glide; const k = ez(t / D);
    const z = lerp(p.z0, p.z1, k); const u = lerp(p.punto[0], p.punto2[0], k), v = lerp(p.punto[1], p.punto2[1], k);
    ctx.save();
    const rot = lerp(0, p.ruota, k) * Math.PI / 180; const bx = p.respiro ? M.wobble(t * .5, 1) * 6 : 0, by = p.respiro ? M.wobble(t * .45, 2) * 5 : 0;
    ctx.translate(W / 2 + bx, H / 2 + by); ctx.rotate(rot); ctx.scale(1 + Math.abs(rot) * .9, 1 + Math.abs(rot) * .9); ctx.translate(-W / 2, -H / 2);
    M.camOn(ctx, z, u, v); M.cover(ctx, s, 0, 0, W, H); ctx.restore();
    look(ctx, t, p);
  }
});

P.push({
  id: 'z-scatti', cat: 'Camera', name: 'Zoom a scatti', dur: 4, thumbT: 2.2, media: true,
  desc: 'Tre colpi di zoom secchi verso il punto, ognuno con scia di movimento, scossa di camera e lampo. Per rivelazioni e momenti di tensione.',
  tip: 'Metti ogni scatto su un colpo di musica o su una parola chiave della voce. Funziona anche su un fermo immagine del gol.',
  params: [
    { k: 'punto', label: 'Punto (clicca sull\'anteprima)', type: 'point', def: [.42, .58] },
    { k: 'scatti', label: 'Scatti', type: 'range', min: 1, max: 5, step: 1, def: 3 },
    { k: 'zoom', label: 'Zoom finale', type: 'range', min: 1.4, max: 5, step: .1, def: 3 },
    { k: 'lampo', label: 'Lampo su ogni scatto', type: 'bool', def: true },
    toneP(), ...camExtras
  ],
  times(p, D) { const n = Math.round(p.scatti); return Array.from({ length: n }, (_, i) => .4 + i * Math.min(1, (D - 1.2) / n)); },
  sfx(p, D) { return this.times(p, D).flatMap(t => [{ s: 'hit', t, g: .9 }, { s: 'whoosh', t: t - .12, d: .2, g: .4 }]); },
  draw(ctx, t, D, p, env) {
    const s = src(env, p); const ts = this.times(p, D); const n = ts.length; const [u, v] = p.punto;
    const zAt = tt => { let z = 1; ts.forEach((t0, i) => { const a = Math.pow(p.zoom, i / n), b = Math.pow(p.zoom, (i + 1) / n); if (tt >= t0) z = lerp(a, b, E.outExpo((tt - t0) / .16)); }); return z * (1 + .025 * Math.max(0, tt - ts[0])); };
    const z = zAt(t); const last = ts.filter(x => t >= x).pop();
    ctx.save(); if (last != null) shake(ctx, t, last, 22, .3);
    if (last != null && t - last < .14) for (let j = 3; j >= 1; j--) { ctx.save(); ctx.globalAlpha = .28; M.camOn(ctx, zAt(t - j * .025), u, v); M.cover(ctx, s, 0, 0, W, H); ctx.restore(); }
    ctx.save(); ctx.globalAlpha = last != null && t - last < .14 ? .55 : 1; M.camOn(ctx, z, u, v); M.cover(ctx, s, 0, 0, W, H); ctx.restore();
    ctx.restore();
    if (p.lampo && last != null) { const f = 1 - clamp((t - last) / .1); if (f > 0) { ctx.fillStyle = `rgba(255,255,255,${(f * .45).toFixed(3)})`; ctx.fillRect(0, 0, W, H); } }
    look(ctx, t, p);
  }
});

P.push({
  id: 'z-lente', cat: 'Camera', name: 'Lente d\'ingrandimento', dur: 6, thumbT: 3.2, media: true,
  desc: 'Una lente da archivista scivola sulla foto e ingrandisce il dettaglio, con bordo metallico, riflesso sul vetro e ombra sul fondo.',
  tip: 'Ottima su documenti, tabellini, pagine di giornale e scritte piccole: la lente fa capire al pubblico dove guardare senza tagliare l\'inquadratura.',
  params: [
    { k: 'punto', label: 'Punto da ingrandire', type: 'point', def: [.47, .5] },
    { k: 'ingr', label: 'Ingrandimento', type: 'range', min: 1.5, max: 5, step: .1, def: 2.6 },
    { k: 'raggio', label: 'Raggio della lente', type: 'range', min: 140, max: 380, step: 5, def: 250 },
    { k: 'nota', label: 'Nota', type: 'text', def: 'Loik, numero 8' },
    toneP(), ...camExtras
  ],
  sfx: () => [{ s: 'whoosh', t: .5, d: 1.6, g: .3 }],
  draw(ctx, t, D, p, env) {
    const s = src(env, p); const [u, v] = p.punto;
    ctx.save(); M.camOn(ctx, 1 + .04 * t / D, .5, .5); M.cover(ctx, s, 0, 0, W, H); ctx.restore();
    ctx.fillStyle = `rgba(0,0,0,${(.3 * ph(t, .4, 1)).toFixed(3)})`; ctx.fillRect(0, 0, W, H);
    const k = E.io5(inv(.5, 2.4, t)); const R = p.raggio;
    const tx = u * W * (1 + .04 * t / D) - (W * .04 * t / D) * .5, ty = v * H * (1 + .04 * t / D) - (H * .04 * t / D) * .5;
    const cx = lerp(W * .18, tx, k) + M.wobble(t * .6, 4) * 4, cy = lerp(H * 1.2, ty, k) + M.wobble(t * .6, 5) * 4;
    const ap = ph(t, .3, .5);
    ctx.save(); ctx.globalAlpha = ap;
    ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 50; ctx.shadowOffsetX = 25; ctx.shadowOffsetY = 35; ctx.beginPath(); ctx.arc(cx, cy, R + 14, 0, 7); ctx.fillStyle = '#222'; ctx.fill(); ctx.restore();
    /* manico */
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(.75); const hg = ctx.createLinearGradient(0, -18, 0, 18); hg.addColorStop(0, '#3b2a1f'); hg.addColorStop(.5, '#6b4a32'); hg.addColorStop(1, '#2a1c13'); ctx.fillStyle = hg; M.rr(ctx, R + 6, -20, 260, 40, 18); ctx.fill(); ctx.restore();
    ctx.save(); ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.clip();
    ctx.translate(cx, cy); ctx.scale(p.ingr, p.ingr); ctx.translate(-cx, -cy);
    ctx.save(); M.camOn(ctx, 1 + .04 * t / D, .5, .5); M.cover(ctx, s, 0, 0, W, H); ctx.restore();
    ctx.restore();
    const gl = ctx.createRadialGradient(cx - R * .4, cy - R * .5, 0, cx - R * .4, cy - R * .5, R * 1.1); gl.addColorStop(0, 'rgba(255,255,255,.28)'); gl.addColorStop(.4, 'rgba(255,255,255,.04)'); gl.addColorStop(1, 'rgba(0,0,0,.25)');
    ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.fillStyle = gl; ctx.fill();
    const rg = ctx.createLinearGradient(cx - R, cy - R, cx + R, cy + R); rg.addColorStop(0, '#d9d4c8'); rg.addColorStop(.5, '#7d776c'); rg.addColorStop(1, '#2b2924');
    ctx.lineWidth = 16; ctx.strokeStyle = rg; ctx.beginPath(); ctx.arc(cx, cy, R + 6, 0, 7); ctx.stroke();
    ctx.lineWidth = 2; ctx.strokeStyle = 'rgba(255,255,255,.5)'; ctx.beginPath(); ctx.arc(cx, cy, R - 2, Math.PI * 1.05, Math.PI * 1.5); ctx.stroke();
    ctx.restore();
    if (p.nota) alpha(ctx, ph(t, 2.6, .8, E.out3), () => { ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.8)'; ctx.shadowBlur = 10; T(ctx, p.nota.toUpperCase(), cx, cy + R + 90 > H - 60 ? cy - R - 50 : cy + R + 90, { size: 56, fam: F.hand, color: PAL.carta, align: 'center' }); ctx.restore(); });
    look(ctx, t, p);
  }
});

P.push({
  id: 'z-foto', cat: 'Camera', name: 'Foto sul tavolo', dur: 7, thumbT: 3.5, media: true,
  desc: 'La tua foto diventa una cartolina d\'archivio che cade sul tavolo verde e si posa con l\'ombra, poi la data e il luogo si scrivono a mano. È la Cartolina Archivio, animata.',
  tip: 'Per presentare una foto come oggetto ritrovato. Alterna cartolina e stampa con bordo bianco per non ripetere sempre lo stesso gesto.',
  params: [
    { k: 'data', label: 'Data', type: 'text', def: '10 giugno 1934' },
    { k: 'soggetto', label: 'Luogo o soggetto', type: 'text', def: 'Stadio Nazionale del PNF, Roma' },
    { k: 'stile', label: 'Supporto', type: 'select', opts: ['Cartolina d\'archivio', 'Stampa con bordo bianco', 'Istantanea'], def: 'Cartolina d\'archivio' },
    { k: 'inclina', label: 'Inclinazione (gradi)', type: 'range', min: -6, max: 6, step: .5, def: -1.5 },
    { k: 'usura', label: 'Usura', type: 'range', min: 0, max: 10, step: 1, def: 5 },
    toneP('Originale'), { k: 'sfondo', label: 'Sfondo', type: 'select', opts: ['Verde campo', 'Trasparente'], def: 'Verde campo' }, grainP(.3)
  ],
  sfx: () => [{ s: 'whoosh', t: 0, d: .7, g: .45 }, { s: 'hit', t: .62, g: .5 }, { s: 'chalk', t: 1.4, d: .9, g: .4 }, { s: 'chalk', t: 2.3, d: 1.0, g: .35 }],
  draw(ctx, t, D, p, env) {
    if (p.sfondo === 'Verde campo') { ground(ctx, 'Verde campo'); ctx.strokeStyle = rgba(PAL.carta, .5); ctx.lineWidth = 2; ctx.strokeRect(60, 60, W - 120, H - 120); ctx.strokeStyle = rgba(PAL.carta, 1); for (const [x, y] of [[60, 60], [W - 60, 60], [60, H - 60], [W - 60, H - 60]]) M.cross(ctx, x, y, 16, 2); }
    const s = src(env, p); const st = p.stile; const wear = p.usura;
    const k = inv(0, .65, t); const land = E.in2(k); const settle = k >= 1 ? E.spring(t - .65, 3, 7) : 0;
    const sc = lerp(1.32, 1, land) - (k >= 1 ? (1 - settle) * -.012 : 0);
    const rot = (p.inclina + (1 - land) * -9) * Math.PI / 180;
    const push = 1 + .05 * E.glide(inv(.7, D, t));
    const CW = st === 'Istantanea' ? 760 : 1120, CH = st === 'Istantanea' ? 900 : 880;
    ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(push, push); ctx.translate(0, (1 - land) * -40); ctx.rotate(rot); ctx.scale(sc, sc); ctx.translate(-CW / 2, -CH / 2);
    ctx.globalAlpha = clamp(k * 4);
    const paperPts = st === 'Cartolina d\'archivio' ? M.roughRect(0, 0, CW, CH, 1 + wear * .35, 9, 7, false) : [[0, 0], [CW, 0], [CW, CH], [0, CH]];
    const off = lerp(90, 30, land), bl = lerp(80, 40, land);
    ctx.save(); ctx.shadowColor = `rgba(0,0,0,${lerp(.25, .45, land)})`; ctx.shadowBlur = bl; ctx.shadowOffsetY = off; M.poly(ctx, paperPts); ctx.fillStyle = PAL.carta; ctx.fill(); ctx.restore();
    M.poly(ctx, paperPts); if (st === 'Stampa con bordo bianco') { ctx.fillStyle = '#f7f5ef'; ctx.fill(); } else M.paperFill(ctx, st === 'Istantanea' ? 'rgba(250,248,240,1)' : null, 1.2);
    const ph0 = st === 'Istantanea' ? [44, 44, CW - 88, CW - 88] : st === 'Stampa con bordo bianco' ? [40, 40, CW - 80, CH - 80] : [36, 36, 1048, 640];
    const photoPts = st === 'Cartolina d\'archivio' ? M.roughRect(ph0[0], ph0[1], ph0[2], ph0[3], 1 + wear * 1.1, 12, 31, wear > 2) : [[ph0[0], ph0[1]], [ph0[0] + ph0[2], ph0[1]], [ph0[0] + ph0[2], ph0[1] + ph0[3]], [ph0[0], ph0[1] + ph0[3]]];
    ctx.save(); M.poly(ctx, photoPts); ctx.clip(); ctx.fillStyle = '#2a2a26'; ctx.fillRect(ph0[0], ph0[1], ph0[2], ph0[3]); M.cover(ctx, s, ph0[0], ph0[1], ph0[2], ph0[3]);
    const ig = ctx.createRadialGradient(ph0[0] + ph0[2] / 2, ph0[1] + ph0[3] / 2, ph0[3] * .3, ph0[0] + ph0[2] / 2, ph0[1] + ph0[3] / 2, ph0[2] * .7); ig.addColorStop(0, 'rgba(20,14,6,0)'); ig.addColorStop(1, `rgba(20,14,6,${(.3 + wear * .04).toFixed(2)})`); ctx.fillStyle = ig; ctx.fillRect(ph0[0], ph0[1], ph0[2], ph0[3]);
    if (wear > 0) { ctx.strokeStyle = 'rgba(245,239,230,.3)'; ctx.lineWidth = 1; ctx.globalAlpha *= Math.min(1, wear / 6); ctx.beginPath(); ctx.moveTo(ph0[0] + 176, ph0[1]); ctx.lineTo(ph0[0] + 162, ph0[1] + ph0[3]); ctx.moveTo(ph0[0] + 734, ph0[1] + 40); ctx.lineTo(ph0[0] + 745, ph0[1] + 410); ctx.stroke(); }
    ctx.restore();
    if (st !== 'Stampa con bordo bianco') {
      const ty = st === 'Istantanea' ? CW + 20 : 694; const tx = st === 'Istantanea' ? 60 : 64; const maxw = CW - tx * 2;
      const wp = ph(t, 1.4, .9, E.lin), wp2 = ph(t, 2.3, 1.0, E.lin);
      const fs1 = st === 'Istantanea' ? 50 : 54, fs2 = st === 'Istantanea' ? 34 : 36;
      M.font(ctx, fs1, F.hand); const w1 = M.textW(ctx, p.data.toUpperCase(), fs1 * .04) + 10;
      ctx.save(); ctx.translate(tx, ty + 70); ctx.rotate(-.6 * Math.PI / 180); mask(ctx, -6, -70, (w1 + 20) * wp, 90, () => T(ctx, p.data.toUpperCase(), 0, 0, { size: fs1, fam: F.hand, tr: .04, color: PAL.inchiostro })); ctx.restore();
      M.stroke(ctx, M.handLine(tx - 4, ty + 86, tx + Math.min(360, w1), ty + 82, 2, 2), ph(t, 2.1, .4, E.io3), 3, PAL.rosso, { alpha: .85 });
      ctx.save(); ctx.translate(tx, ty + 132); ctx.rotate(-.3 * Math.PI / 180); M.font(ctx, fs2, F.hand); const w2 = M.textW(ctx, p.soggetto.toUpperCase(), fs2 * .03) + 10; mask(ctx, -6, -50, (Math.min(maxw, w2) + 20) * wp2, 70, () => T(ctx, p.soggetto.toUpperCase(), 0, 0, { size: fs2, fam: F.hand, tr: .03, color: PAL.inchiostro })); ctx.restore();
    }
    ctx.restore();
    M.grain(ctx, t, p.grana * .4, p.sfondo === 'Trasparente');
  }
});

P.push({
  id: 'z-isola', cat: 'Camera', name: 'Isola il giocatore', dur: 6, thumbT: 3.3, media: true,
  desc: 'Analisi stile moviola: il campo si scurisce, un anello luminoso compare sotto i piedi del giocatore, un filo sale fino al cartellino con nome e ruolo.',
  tip: 'Clicca sui piedi del giocatore nell\'anteprima. Funziona su foto e fermi immagine: per un video in movimento usalo su un fotogramma congelato.',
  params: [
    { k: 'punto', label: 'Piedi del giocatore', type: 'point', def: [.47, .56] },
    { k: 'altezza', label: 'Altezza del giocatore (px)', type: 'range', min: 80, max: 700, step: 10, def: 200 },
    { k: 'nome', label: 'Nome', type: 'text', def: 'Loik' },
    { k: 'ruolo', label: 'Ruolo', type: 'text', def: '8 · Mezzala destra' },
    toneP(), accentP(), ...camExtras
  ],
  sfx: () => [{ s: 'whoosh', t: .3, d: 1, g: .3 }, { s: 'pop', t: 1.4, g: .6 }, { s: 'whoosh', t: 1.9, d: .5, g: .3 }],
  draw(ctx, t, D, p, env) {
    const s = src(env, p); const [u, v] = p.punto;
    const z = lerp(1, 1.22, E.io3(inv(.2, 2.2, t))) * (1 + .02 * t / D);
    ctx.save(); const [tx, ty] = M.camOn(ctx, z, u, v * .92); M.cover(ctx, s, 0, 0, W, H); ctx.restore();
    const fx = u * W * z + tx, fy = v * H * z + ty, hgt = p.altezza * z;
    const dk = ph(t, .9, .7, E.io3);
    const L = env.layer(); L.fillStyle = `rgba(4,10,8,${(.62 * dk).toFixed(3)})`; L.fillRect(0, 0, W, H); L.globalCompositeOperation = 'destination-out';
    const g = L.createRadialGradient(fx, fy - hgt * .5, hgt * .25, fx, fy - hgt * .5, hgt * .85); g.addColorStop(0, 'rgba(0,0,0,1)'); g.addColorStop(1, 'rgba(0,0,0,0)');
    L.save(); L.translate(fx, fy - hgt * .5); L.scale(.62, 1); L.translate(-fx, -(fy - hgt * .5)); L.fillStyle = g; L.fillRect(fx - hgt * 2, fy - hgt * 2, hgt * 4, hgt * 4); L.restore();
    env.flush(L);
    /* anello */
    const rk = ph(t, 1.3, .6, E.outBack); const rx = hgt * .42 * rk, ry = hgt * .12 * rk;
    if (rk > 0) {
      ctx.save(); ctx.shadowColor = p.accento; ctx.shadowBlur = 24; ctx.strokeStyle = p.accento; ctx.lineWidth = 5; ctx.beginPath(); ctx.ellipse(fx, fy, rx, ry, 0, 0, 7); ctx.stroke();
      ctx.lineWidth = 3; ctx.setLineDash([18, 14]); ctx.lineDashOffset = -t * 60; ctx.globalAlpha = .7; ctx.beginPath(); ctx.ellipse(fx, fy, rx * 1.35, ry * 1.35, 0, 0, 7); ctx.stroke(); ctx.restore();
      ctx.fillStyle = rgba(p.accento, .18 * rk); ctx.beginPath(); ctx.ellipse(fx, fy, rx, ry, 0, 0, 7); ctx.fill();
    }
    /* filo e cartellino */
    const lp = ph(t, 1.8, .6, E.io3); const topY = Math.max(170, fy - hgt * 1.25 - 120);
    ctx.fillStyle = PAL.carta; ctx.fillRect(fx - 1, lerp(fy - hgt * 1.05, topY, lp), 2, (fy - hgt * 1.05 - topY) * lp);
    const cp = ph(t, 2.2, .7, E.film);
    if (cp > 0) {
      M.font(ctx, 58, F.display); const nw = M.textW(ctx, p.nome.toUpperCase(), 58 * .02); M.font(ctx, 24, F.body, 600); const rw = M.textW(ctx, p.ruolo.toUpperCase(), 24 * .12);
      const bw = Math.max(nw, rw) + 56; const bx = Math.min(W - bw - 80, Math.max(80, fx - bw / 2));
      ctx.fillStyle = PAL.carta; ctx.fillRect(bx, topY - 120, bw * cp, 78); ctx.fillStyle = p.accento; ctx.fillRect(bx, topY - 42, bw * ph(t, 2.35, .7, E.film), 44);
      mask(ctx, bx, topY - 120, bw * cp, 78, () => T(ctx, p.nome.toUpperCase(), bx + 28, topY - 58, { size: 58, fam: F.display, tr: .02, color: PAL.inchiostro }));
      mask(ctx, bx, topY - 42, bw * ph(t, 2.35, .7, E.film), 44, () => T(ctx, p.ruolo.toUpperCase(), bx + 28, topY - 11, { size: 24, weight: 600, tr: .12, color: PAL.carta }));
    }
    look(ctx, t, p);
  }
});
})();
