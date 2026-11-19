/* Moviola — preset: titoli, informazioni, dati */
(function () {
'use strict';
const M = window.MV, { W, H, PAL, E, ph, clamp, lerp, inv, smooth, F } = M;
const P = window.PRESETS = window.PRESETS || [];

/* ---------- utilità condivise (esposte anche agli altri file) ---------- */
function rgba(hex, a) { const h = hex.replace('#', ''); const n = parseInt(h.length === 3 ? h.split('').map(c => c + c).join('') : h, 16); return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`; }
function ground(ctx, kind, t = 0) {
  if (kind === 'Verde campo') {
    const g = ctx.createRadialGradient(W / 2, H * .45, 40, W / 2, H * .5, W * .62); g.addColorStop(0, '#1d4537'); g.addColorStop(.55, PAL.verde); g.addColorStop(1, PAL.verdeScuro);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H); M.vignette(ctx, .18);
  } else if (kind === 'Nero') { ctx.fillStyle = PAL.nero; ctx.fillRect(0, 0, W, H); M.vignette(ctx, .15); }
  else if (kind === 'Carta') { ctx.beginPath(); ctx.rect(0, 0, W, H); M.paperFill(ctx, null, 2); M.vignette(ctx, .1, '60,40,20'); }
  else if (kind === 'Inchiostro') { ctx.fillStyle = PAL.inchiostro; ctx.fillRect(0, 0, W, H); M.vignette(ctx, .18); }
}
const isDark = k => k !== 'Carta';
function T(ctx, s, x, y, o = {}) {
  const size = o.size || 40; M.font(ctx, size, o.fam || F.body, o.weight || 400, o.style || '');
  const tr = (o.tr || 0) * size; M.track(ctx, tr);
  ctx.textAlign = o.align || 'left'; ctx.textBaseline = o.base || 'alphabetic'; ctx.fillStyle = o.color || PAL.carta;
  const dx = (o.align === 'center') ? tr / 2 : (o.align === 'right' ? tr : 0);
  if (o.stroke) { ctx.strokeStyle = o.stroke; ctx.lineWidth = o.lw || 2; ctx.strokeText(s, x + dx, y); }
  else ctx.fillText(s, x + dx, y);
  M.track(ctx, 0); ctx.textAlign = 'left';
}
/* testo animato lettera per lettera: fn(i,n) → {a, dx, dy, s, r, blur} */
function AT(ctx, s, x, y, o, fn) {
  const size = o.size || 40; M.font(ctx, size, o.fam || F.body, o.weight || 400, o.style || '');
  const tr = (o.tr || 0) * size; const L = M.chars(ctx, s, tr);
  let x0 = x; if (o.align === 'center') x0 = x - L.width / 2; else if (o.align === 'right') x0 = x - L.width;
  ctx.textBaseline = o.base || 'alphabetic'; ctx.textAlign = 'left';
  const n = L.list.length;
  L.list.forEach((c, i) => {
    if (c.ch === ' ') return;
    const k = fn(i, n, c) || {}; const a = k.a ?? 1; if (a <= 0.003) return;
    ctx.save(); ctx.globalAlpha *= a; ctx.fillStyle = k.color || o.color || PAL.carta;
    ctx.translate(x0 + c.x + c.w / 2 + (k.dx || 0), y + (k.dy || 0)); if (k.r) ctx.rotate(k.r); if (k.s != null && k.s !== 1) ctx.scale(k.s, k.s);
    if (k.blur > .3) ctx.filter = `blur(${k.blur.toFixed(1)}px)`;
    ctx.fillText(c.ch, -c.w / 2, 0); ctx.restore();
  });
  return L.width;
}
/* ombra morbida dietro ai testi su footage chiaro */
function scrim(ctx, x, y, rx, ry, a) { if (a <= 0) return; ctx.save(); ctx.translate(x, y); ctx.scale(1, ry / rx); const g = ctx.createRadialGradient(0, 0, 0, 0, 0, rx); g.addColorStop(0, `rgba(0,0,0,${(.62 * a).toFixed(3)})`); g.addColorStop(.55, `rgba(0,0,0,${(.32 * a).toFixed(3)})`); g.addColorStop(1, 'rgba(0,0,0,0)'); ctx.fillStyle = g; ctx.fillRect(-rx, -rx, rx * 2, rx * 2); ctx.restore(); }
function mask(ctx, x, y, w, h, fn) { ctx.save(); ctx.beginPath(); ctx.rect(x, y, w, h); ctx.clip(); fn(); ctx.restore(); }
function alpha(ctx, a, fn) { if (a <= 0.003) return; ctx.save(); ctx.globalAlpha *= a; fn(); ctx.restore(); }
/* spinta lenta di camera su tutto il fotogramma */
function drift(ctx, t, D, amt = .035, cx = W / 2, cy = H / 2) { const s = 1 + amt * E.glide(t / D); ctx.translate(cx, cy); ctx.scale(s, s); ctx.translate(-cx, -cy); }
function shake(ctx, t, t0, amp = 14, dur = .35) { const k = inv(t0, t0 + dur, t); if (k <= 0 || k >= 1) return; const a = amp * (1 - k) ** 2; ctx.translate(M.wobble(t * 40, 3) * a, M.wobble(t * 40, 7) * a); }
function parseNum(s) { const neg = /^-/.test(s.trim()); const v = parseFloat(String(s).replace(/\./g, '').replace(',', '.').replace(/[^\d.]/g, '')); return isNaN(v) ? 0 : (neg ? -v : v); }
function fmtIt(v, dec = 0) { const neg = v < 0; const f = Math.abs(v).toFixed(dec); let [i, d] = f.split('.'); i = i.replace(/\B(?=(\d{3})+(?!\d))/g, '.'); return (neg ? '-' : '') + i + (d ? ',' + d : ''); }
function decOf(s) { const m = String(s).match(/,(\d+)/); return m ? m[1].length : 0; }
const BG = ['Trasparente', 'Verde campo', 'Nero', 'Carta', 'Inchiostro'];
const accentP = (def = PAL.rosso) => ({ k: 'accento', label: 'Colore accento', type: 'color', def });
/* look HD pulito: la grana è un'opzione, sempre a 0 di partenza */
const grainP = () => ({ k: 'grana', label: 'Grana pellicola (look d\'epoca)', type: 'range', min: 0, max: 1, step: .05, def: 0 });
const bgP = (def = 'Trasparente') => ({ k: 'sfondo', label: 'Sfondo', type: 'select', opts: BG, def });
function finish(ctx, t, p, atopIfTransparent = true) {
  const transparent = (p.sfondo || 'Trasparente') === 'Trasparente';
  M.grain(ctx, t, (p.grana ?? 0) * (transparent ? .55 : .32), transparent && atopIfTransparent);
}
window.MVX = { scrim, rgba, ground, isDark, T, AT, mask, alpha, drift, shake, parseNum, fmtIt, decOf, BG, accentP, grainP, bgP, finish };

/* =============================================================== TITOLI */

P.push({
  id: 'apertura', cat: 'Titoli', name: 'Apertura cinematografica', dur: 6.5, thumbT: 2.6,
  desc: 'Il titolo del documentario: righe che salgono da una maschera, filo rosso che si traccia dal centro, riflesso di luce che attraversa le lettere, cornice di registro.',
  tip: 'Mettilo dopo il cold open, sul primo colpo forte della musica: il colpo del titolo cade a 0,75 s. Lascia 2 secondi di silenzio dopo.',
  params: [
    { k: 'occhiello', label: 'Occhiello', type: 'text', def: 'UNA STORIA DEL CALCIO ITALIANO' },
    { k: 'titolo', label: 'Titolo (una riga per a capo)', type: 'textarea', def: 'IL GRANDE\nTORINO' },
    { k: 'sotto', label: 'Sottotitolo', type: 'text', def: '1943 — 1949' },
    { k: 'allinea', label: 'Allineamento', type: 'select', opts: ['Centro', 'Sinistra'], def: 'Centro' },
    bgP('Verde campo'), accentP(), { k: 'cornice', label: 'Cornice di registro', type: 'bool', def: true }, grainP()
  ],
  sfx: (p, D) => [{ s: 'whoosh', t: .35, d: .5, g: .7 }, { s: 'impact', t: .78, g: 1 }, { s: 'sub', t: .78, g: .6 }, { s: 'whoosh', t: D - .75, d: .6, g: .5 }],
  draw(ctx, t, D, p, env) {
    M.E; ground(ctx, p.sfondo, t);
    const ex = ph(t, D - .8, .75, E.swift);
    ctx.save(); drift(ctx, t, D, .04);
    const left = p.allinea === 'Sinistra'; const cx = left ? 230 : W / 2; const al = left ? 'left' : 'center';
    if (p.cornice) M.regFrame(ctx, 60, 60, W - 120, H - 120, ph(t, 0, 1.1, E.film) * (1 - ex), PAL.carta, .45);
    const ls = M.lines(p.titolo); const n = ls.length || 1;
    const size = Math.min(250, 760 / n, ...ls.map(l => M.fit(ctx, l, F.display, 250, W - 420, 400, .01)));
    const lh = size * 1.02, blockH = lh * n, top = H / 2 - blockH / 2 + size * .05;
    /* occhiello */
    const kp = ph(t, .25, 1.2, E.film);
    alpha(ctx, kp * (1 - ex), () => AT(ctx, p.occhiello, cx, top - 46, { size: 26, weight: 600, tr: lerp(.7, .38, kp), align: al, color: rgba(PAL.carta, .82) }, (i, N) => ({ a: ph(t, .25 + i * .018, .5, E.out3), blur: (1 - ph(t, .25 + i * .018, .5)) * 6 })));
    /* righe del titolo su un livello, per il riflesso */
    const L = env.layer(); L.save();
    ls.forEach((l, i) => {
      const y = top + lh * (i + 1) - size * .14;
      const a = ph(t, .55 + i * .13, 1.2, E.film), o = ph(t, D - .85 + (n - 1 - i) * .06, .6, E.swift);
      mask(L, 0, y - size * 1.0, W, size * 1.08, () => {
        M.font(L, size, F.display); const yy = y + size * (1 - a) * 1.05 - size * 1.05 * o;
        T(L, l, cx, yy, { size, fam: F.display, tr: lerp(.06, .012, a), align: al, color: PAL.carta });
      });
    });
    /* riflesso di luce che passa sulle lettere */
    const gp = ph(t, 2.0, 1.4, E.io3);
    if (gp > 0 && gp < 1) {
      L.globalCompositeOperation = 'source-atop';
      const gx = lerp(-400, W + 400, gp); const g = L.createLinearGradient(gx - 260, 0, gx + 260, 0);
      g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(.5, 'rgba(255,252,240,.85)'); g.addColorStop(1, 'rgba(255,255,255,0)');
      L.fillStyle = g; L.setTransform(L.getTransform().multiply(new DOMMatrix().skewX(-20))); L.fillRect(-W, 0, W * 3, H);
    }
    L.restore(); env.flush(L);
    /* filo rosso dal centro */
    const rp = ph(t, 1.15, 1.0, E.film) * (1 - ph(t, D - .9, .5, E.swift));
    const ry = top + blockH + 34, rw = 420 * rp;
    ctx.fillStyle = p.accento; if (left) ctx.fillRect(cx, ry, rw * 1.4, 6); else ctx.fillRect(cx - rw, ry, rw * 2, 6);
    /* sottotitolo */
    alpha(ctx, (1 - ex), () => AT(ctx, p.sotto, cx, ry + 74, { size: 38, weight: 500, tr: .32, align: al, color: PAL.carta }, i => { const k = ph(t, 1.45 + i * .03, .6, E.out3); return { a: k, dy: (1 - k) * 14 }; }));
    ctx.restore();
    finish(ctx, t, p);
  }
});

P.push({
  id: 'capitolo', cat: 'Titoli', name: 'Capitolo', dur: 6, thumbT: 2.8,
  desc: 'Cartello di capitolo: il numero si disegna a contorno e poi si riempie di colore dal basso, filo verticale, titolo in corsivo editoriale parola per parola.',
  tip: 'Dividi il documentario in 4–6 capitoli: aiuta la ritenzione su YouTube. Usa lo stesso preset per tutti, cambia solo numero e titolo.',
  params: [
    { k: 'numero', label: 'Numero', type: 'text', def: 'IV' },
    { k: 'etichetta', label: 'Etichetta', type: 'text', def: 'CAPITOLO' },
    { k: 'titolo', label: 'Titolo', type: 'text', def: 'La nebbia su Superga' },
    { k: 'data', label: 'Data o periodo', type: 'text', def: '4 maggio 1949' },
    { k: 'riempi', label: 'Riempimento del numero', type: 'bool', def: true },
    bgP('Verde campo'), accentP(), grainP()
  ],
  sfx: () => [{ s: 'whoosh', t: .2, d: .7, g: .5 }, { s: 'hit', t: 1.2, g: .8 }, { s: 'whoosh', t: 1.55, d: .5, g: .35 }],
  draw(ctx, t, D, p, env) {
    ground(ctx, p.sfondo, t);
    const ex = ph(t, D - .8, .75, E.swift);
    ctx.save(); drift(ctx, t, D, .03, 600, H / 2);
    const dark = isDark(p.sfondo) || p.sfondo === 'Trasparente'; const ink = dark ? PAL.carta : PAL.inchiostro;
    const size = Math.min(560, M.fit(ctx, p.numero, F.display, 560, 640));
    M.font(ctx, size, F.display); const nw = M.textW(ctx, p.numero);
    const nx = 560 - nw / 2 - 40, ny = H / 2 + size * .36 - ex * 60;
    /* contorno che si disegna */
    const dp = ph(t, .15, 1.6, E.io3);
    ctx.save(); ctx.globalAlpha = 1 - ex; ctx.strokeStyle = ink; ctx.lineWidth = 3; ctx.setLineDash([2400 * dp + .01, 4000]); M.font(ctx, size, F.display); ctx.textBaseline = 'alphabetic';
    ctx.strokeText(p.numero, nx, ny); ctx.restore();
    /* riempimento che sale */
    if (p.riempi) {
      const fp = ph(t, 1.0, 1.3, E.film);
      if (fp > 0) mask(ctx, 0, ny + size * .08 - (size * 1.02) * fp, W, size * 1.2, () => {
        alpha(ctx, 1 - ex, () => { M.font(ctx, size, F.display); ctx.fillStyle = p.accento; ctx.fillText(p.numero, nx, ny); });
      });
    }
    /* filo verticale */
    const lx = 1060, vp = ph(t, .5, 1.1, E.film) * (1 - ex);
    ctx.fillStyle = rgba(ink, .55); ctx.fillRect(lx, H / 2 - 230 * vp, 2, 460 * vp);
    M.cross && (ctx.strokeStyle = rgba(ink, .6 * vp)); if (vp > .1) { M.cross(ctx, lx + 1, H / 2 - 230 * vp, 12, 2); M.cross(ctx, lx + 1, H / 2 + 230 * vp, 12, 2); }
    const tx = 1130;
    alpha(ctx, 1 - ex, () => {
      const k = ph(t, .9, .8, E.out3);
      AT(ctx, (p.etichetta + ' ' + p.numero).toUpperCase(), tx, H / 2 - 120, { size: 26, weight: 600, tr: .42, color: p.accento }, i => { const a = ph(t, .9 + i * .025, .5, E.out3); return { a, dx: (1 - a) * -10 }; });
      const words = String(p.titolo).split(/\s+/); M.font(ctx, 92, F.serif, 400, 'italic');
      const ln = M.wrap(ctx, p.titolo, 700); let wi = 0;
      ln.forEach((l, li) => {
        let x = tx; const y = H / 2 - 10 + li * 104;
        l.split(' ').forEach(w => {
          const a = ph(t, 1.35 + wi * .09, .9, E.film); wi++;
          M.font(ctx, 92, F.serif, 400, 'italic'); const ww = ctx.measureText(w + ' ').width;
          alpha(ctx, a, () => { ctx.save(); if (a < 1) ctx.filter = `blur(${(1 - a) * 8}px)`; T(ctx, w, x, y + (1 - a) * 26, { size: 92, fam: F.serif, style: 'italic', color: ink }); ctx.restore(); });
          x += ww;
        });
      });
      const dy = H / 2 - 10 + ln.length * 104 + 10;
      alpha(ctx, ph(t, 2.0, .8, E.out3), () => T(ctx, p.data.toUpperCase(), tx, dy, { size: 28, weight: 500, tr: .24, color: rgba(ink, .75) }));
    });
    ctx.restore();
    finish(ctx, t, p);
  }
});

P.push({
  id: 'citazione', cat: 'Titoli', name: 'Citazione', dur: 7, thumbT: 3.6,
  desc: 'Citazione a tutto schermo: virgolette grandi, parole che passano da sfocate a nitide, parola chiave sottolineata a pennarello.',
  tip: 'Leggi la citazione in voce fuori campo mentre appare: fai coincidere la parola chiave con la sottolineatura (parte a circa 60% della durata).',
  params: [
    { k: 'testo', label: 'Citazione', type: 'textarea', def: 'Il calcio è la cosa più importante delle cose meno importanti.' },
    { k: 'autore', label: 'Autore', type: 'text', def: 'Arrigo Sacchi' },
    { k: 'chiave', label: 'Parola chiave', type: 'text', def: 'importante' },
    { k: 'stile', label: 'Carattere', type: 'select', opts: ['Corsivo editoriale', 'Scritto a mano', 'Macchina da scrivere'], def: 'Corsivo editoriale' },
    bgP('Verde campo'), accentP(), grainP()
  ],
  sfx: (p, D) => [{ s: 'whoosh', t: .1, d: .9, g: .35 }, { s: 'chalk', t: D * .58, d: .45, g: .5 }],
  draw(ctx, t, D, p, env) {
    ground(ctx, p.sfondo, t);
    const ex = ph(t, D - .9, .8, E.swift);
    ctx.save(); drift(ctx, t, D, .035);
    const ink = isDark(p.sfondo) || p.sfondo === 'Trasparente' ? PAL.carta : PAL.inchiostro;
    const st = { 'Corsivo editoriale': [F.serif, 'italic', 400, 1.18], 'Scritto a mano': [F.hand, '', 400, 1.25], 'Macchina da scrivere': [F.type, '', 400, 1.3] }[p.stile] || [F.serif, 'italic', 400, 1.18];
    const txt = String(p.testo).replace(/^["“«]|["”»]$/g, '');
    let size = 82; let ln;
    for (let i = 0; i < 12; i++) { M.font(ctx, size, st[0], st[2], st[1]); ln = M.wrap(ctx, txt, 1320); if (ln.length * size * st[3] < 520) break; size *= .92; }
    const lh = size * st[3], top = H / 2 - (ln.length * lh) / 2 + size * .2 - 40;
    /* virgolette */
    const qp = ph(t, .1, .9, E.outBack);
    alpha(ctx, ph(t, .1, .4) * (1 - ex), () => { ctx.save(); ctx.translate(W / 2, top - 70); ctx.scale(qp, qp); T(ctx, '“', 0, 150, { size: 300, fam: F.serif, weight: 900, color: p.accento, align: 'center' }); ctx.restore(); });
    const key = (p.chiave || '').toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
    let wi = 0, total = txt.split(/\s+/).length; let keyBox = null;
    const per = Math.min(.11, (D * .45) / total);
    ln.forEach((l, li) => {
      M.font(ctx, size, st[0], st[2], st[1]); const lw = ctx.measureText(l).width; let x = W / 2 - lw / 2; const y = top + lh * (li + 1);
      l.split(' ').forEach(w => {
        M.font(ctx, size, st[0], st[2], st[1]); const ww = ctx.measureText(w).width, sp = ctx.measureText(' ').width;
        const a = ph(t, .55 + wi * per, .9, E.film); wi++;
        const isKey = key && w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '') === key;
        if (isKey && !keyBox) keyBox = [x, y, ww];
        alpha(ctx, a * (1 - ex), () => { ctx.save(); if (a < 1) ctx.filter = `blur(${((1 - a) * 10).toFixed(1)}px)`; T(ctx, w, x, y + (1 - a) * 20, { size, fam: st[0], style: st[1], weight: st[2], color: ink }); ctx.restore(); });
        x += ww + sp;
      });
    });
    if (keyBox) {
      const up = ph(t, D * .58, .55, E.io3);
      const pts = M.handLine(keyBox[0] - 8, keyBox[1] + size * .2, keyBox[0] + keyBox[2] + 10, keyBox[1] + size * .14, 5, 4);
      alpha(ctx, 1 - ex, () => M.stroke(ctx, pts, up, Math.max(6, size * .09), p.accento, { taper: true }));
    }
    const ay = top + ln.length * lh + 90; const ap = ph(t, .55 + total * per + .2, .8, E.film);
    alpha(ctx, ap * (1 - ex), () => {
      ctx.fillStyle = p.accento; ctx.fillRect(W / 2 - 40 * ap, ay - 34, 80 * ap, 3);
      T(ctx, ('— ' + p.autore).toUpperCase(), W / 2, ay + 18, { size: 28, weight: 600, tr: .3, align: 'center', color: rgba(ink, .85) });
    });
    ctx.restore();
    finish(ctx, t, p);
  }
});

/* testo d'articolo per le colonne del giornale */
const ARTICOLO = 'Al termine di una gara combattuta fin dal primo minuto la squadra di casa ha superato gli avversari davanti a un pubblico delle grandi occasioni. Il gioco si è acceso a metà del primo tempo quando la mezzala ha raccolto un pallone sulla trequarti e ha trovato il compagno smarcato sulla destra. La difesa ospite ha retto a lungo ma nella ripresa il ritmo è salito e le occasioni si sono moltiplicate. I tifosi hanno seguito ogni azione con il fiato sospeso fino al fischio finale accolto da un lungo applauso. Negli spogliatoi l\'allenatore ha lodato lo spirito della squadra e la tenuta atletica dei suoi uomini. Domenica prossima la formazione sarà attesa da una trasferta difficile su un campo dove da anni nessuno riesce a vincere. ';
P.push({
  id: 'giornale', cat: 'Titoli', name: 'Prima pagina', dur: 7, thumbT: 3.5, media: true,
  desc: 'Pagina di giornale d\'epoca che scivola sul tavolo: testata gotica, titolo a nove colonne, foto in mezzatinta (la tua), evidenziatore sulla parola chiave e spinta di camera sul titolo.',
  tip: 'Perfetto per citare la cronaca dell\'epoca. Carica una foto: viene retinata come su carta da giornale. Il titolo riempie lo schermo a circa 5 s.',
  params: [
    { k: 'testata', label: 'Testata', type: 'text', def: 'Cronache del Pallone' },
    { k: 'data', label: 'Riga della data', type: 'text', def: 'TORINO · GIOVEDÌ 5 MAGGIO 1949 · ANNO IV · LIRE 15' },
    { k: 'occhiello', label: 'Occhiello', type: 'text', def: 'TRAGEDIA NEI CIELI DI TORINO' },
    { k: 'titolo', label: 'Titolo', type: 'textarea', def: 'L\'intera squadra del Torino perita sul colle di Superga' },
    { k: 'chiave', label: 'Parole da evidenziare', type: 'text', def: 'Torino' },
    { k: 'foto', label: 'Foto in pagina (usa il tuo materiale)', type: 'bool', def: true },
    { k: 'camera', label: 'Movimento', type: 'select', opts: ['Spinta sul titolo', 'Scorrimento verticale', 'Fermo'], def: 'Spinta sul titolo' },
    accentP(), grainP()
  ],
  sfx: (p, D) => [{ s: 'rip', t: .05, d: .5, g: .4 }, { s: 'whoosh', t: .0, d: .8, g: .5 }, { s: 'chalk', t: 2.1, d: .6, g: .45 }],
  page(p, env, s) {
    const key = 'page:' + JSON.stringify([p.testata, p.data, p.occhiello, p.titolo, p.foto, env.mediaKey]) + s;
    if (M.cache.has(key)) return M.cache.get(key);
    for (const k of [...M.cache.keys()]) if (k.startsWith('page:')) M.cache.delete(k);
    const PW = 1500, PH = 2000, c = M.mk(Math.round(PW * s), Math.round(PH * s)), g = c.getContext('2d'); g.scale(s, s);
    g.beginPath(); g.rect(0, 0, PW, PH); M.paperFill(g, 'rgba(236,222,190,1)', 1.6);
    const ink = '#1d1b17'; g.fillStyle = ink; g.strokeStyle = ink;
    const fs = M.fit(g, p.testata, F.black, 168, PW - 160);
    T(g, p.testata, PW / 2, 210, { size: fs, fam: F.black, color: ink, align: 'center' });
    g.fillRect(70, 250, PW - 140, 5); g.fillRect(70, 262, PW - 140, 1.5);
    T(g, p.data, PW / 2, 298, { size: 22, fam: F.serif, weight: 700, tr: .12, color: ink, align: 'center' });
    g.fillRect(70, 318, PW - 140, 1.5); g.fillRect(70, 324, PW - 140, 4);
    T(g, p.occhiello.toUpperCase(), PW / 2, 392, { size: 38, fam: F.serif, weight: 700, tr: .18, color: ink, align: 'center' });
    let hs = 150, hl; for (let i = 0; i < 20; i++) { M.font(g, hs, F.serif, 900); hl = M.wrap(g, p.titolo.toUpperCase(), PW - 150); if (hl.length * hs * 1.02 < 560) break; hs *= .94; }
    hl.forEach((l, i) => T(g, l, PW / 2, 400 + hs * (i + 1) * 1.0, { size: hs, fam: F.serif, weight: 900, color: ink, align: 'center' }));
    const hBottom = 400 + hs * hl.length * 1.0 + 40;
    g.fillRect(70, hBottom, PW - 140, 2);
    /* colonne */
    const cols = 6, gut = 26, cw = (PW - 140 - gut * (cols - 1)) / cols; let photo = null;
    if (p.foto) { const src = env.media || M.samplePhoto(); const ht = M.halftone(src, env.mediaKey || 'sample', 5, ink); photo = { x: 70 + cw + gut, y: hBottom + 30, w: cw * 4 + gut * 3, h: (cw * 4 + gut * 3) * .6, src: ht }; }
    for (let ci = 0; ci < cols; ci++) {
      const x = 70 + ci * (cw + gut); let y = hBottom + 50;
      M.font(g, 17, F.serif, 400); g.fillStyle = ink; const words = (ARTICOLO + ARTICOLO + ARTICOLO).split(' '); let wi = ci * 37 % 60, line = '';
      if (ci > 0) g.fillRect(x - gut / 2, hBottom + 20, 1, PH - hBottom - 80);
      while (y < PH - 70) {
        if (photo && x >= photo.x - 2 && x < photo.x + photo.w && y > photo.y - 10 && y < photo.y + photo.h + 46) { y += 24; continue; }
        const w = words[wi++ % words.length]; const tl = line ? line + ' ' + w : w;
        if (g.measureText(tl).width > cw) { /* giustifica */ const ws = line.split(' '); const tw = g.measureText(ws.join('')).width; const gap = ws.length > 1 ? (cw - tw) / (ws.length - 1) : 0; let xx = x; ws.forEach(s => { g.fillText(s, xx, y); xx += g.measureText(s).width + gap; }); line = w; y += 24; }
        else line = tl;
      }
    }
    if (photo) { g.fillStyle = '#e8dcc0'; g.fillRect(photo.x, photo.y, photo.w, photo.h); g.globalAlpha = .92; g.drawImage(photo.src, photo.x, photo.y, photo.w, photo.h); g.globalAlpha = 1; g.strokeStyle = ink; g.lineWidth = 2; g.strokeRect(photo.x, photo.y, photo.w, photo.h); T(g, 'La formazione in campo in una delle ultime partite della stagione', photo.x, photo.y + photo.h + 28, { size: 17, fam: F.serif, style: 'italic', color: ink }); }
    /* macchie e ingiallimento */
    const r = M.rng(9); for (let i = 0; i < 14; i++) { const x = r() * PW, y = r() * PH, rad = 40 + r() * 180; const gr = g.createRadialGradient(x, y, 0, x, y, rad); gr.addColorStop(0, 'rgba(150,110,50,.10)'); gr.addColorStop(1, 'rgba(150,110,50,0)'); g.fillStyle = gr; g.fillRect(x - rad, y - rad, rad * 2, rad * 2); }
    const eg = g.createLinearGradient(0, 0, PW, 0); eg.addColorStop(0, 'rgba(120,80,30,.18)'); eg.addColorStop(.06, 'rgba(0,0,0,0)'); eg.addColorStop(.94, 'rgba(0,0,0,0)'); eg.addColorStop(1, 'rgba(120,80,30,.2)'); g.fillStyle = eg; g.fillRect(0, 0, PW, PH);
    g.fillStyle = 'rgba(80,60,30,.08)'; g.fillRect(PW / 2 - 2, 0, 4, PH);
    const res = { c, PW, PH, hs, hl, hTop: 400, s }; M.cache.set(key, res); return res;
  },
  draw(ctx, t, D, p, env) {
    ground(ctx, 'Verde campo', t);
    const pg = this.page(p, env, Math.min(2.4, env.scale * 2.2));
    const enter = ph(t, 0, 1.1, E.film);
    const mv = p.camera;
    let z, cy;
    if (mv === 'Fermo') { z = .52; cy = 1000; }
    else if (mv === 'Scorrimento verticale') { z = .78; cy = lerp(500, 1500, E.glide(inv(.8, D, t))); }
    else { const k = E.io3(inv(1.0, D - .3, t)); z = lerp(.5, 1.18, k); cy = lerp(1000, 560 + pg.hs * pg.hl.length * .5, k); }
    const rot = lerp(-7, -2, enter) * Math.PI / 180;
    ctx.save();
    ctx.translate(W / 2 + (1 - enter) * 120, H / 2 + (1 - enter) * 900); ctx.rotate(rot); ctx.scale(z, z); ctx.translate(-pg.PW / 2, -cy);
    ctx.save(); ctx.shadowColor = 'rgba(0,0,0,.55)'; ctx.shadowBlur = 60 * z; ctx.shadowOffsetY = 26 * z; ctx.fillStyle = '#ddd'; ctx.fillRect(0, 0, pg.PW, pg.PH); ctx.restore();
    ctx.drawImage(pg.c, 0, 0, pg.PW, pg.PH);
    /* evidenziatore sulle parole chiave del titolo */
    const keys = String(p.chiave || '').toLowerCase().split(/[,\s]+/).filter(Boolean);
    if (keys.length) {
      M.font(ctx, pg.hs, F.serif, 900);
      let n = 0;
      pg.hl.forEach((l, li) => {
        const lw = ctx.measureText(l).width, x0 = pg.PW / 2 - lw / 2, y = pg.hTop + pg.hs * (li + 1);
        let pre = '';
        l.split(' ').forEach(w => {
          const clean = w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
          const x = x0 + ctx.measureText(pre).width, ww = ctx.measureText(w).width; pre += w + ' ';
          if (keys.some(k => clean === k.replace(/[^\p{L}\p{N}]/gu, ''))) {
            const hp = ph(t, 2.1 + n * .35, .55, E.io3); n++;
            if (hp > 0) { ctx.save(); ctx.globalCompositeOperation = 'multiply'; ctx.fillStyle = rgba(p.accento, .55); const r = M.rng(n + 3); ctx.beginPath(); ctx.moveTo(x - 10, y - pg.hs * .74); ctx.lineTo(x - 10 + (ww + 22) * hp, y - pg.hs * .78 + r() * 6); ctx.lineTo(x - 6 + (ww + 18) * hp, y + pg.hs * .08); ctx.lineTo(x - 12, y + pg.hs * .1); ctx.fill(); ctx.restore(); }
          }
        });
      });
    }
    ctx.restore();
    M.vignette(ctx, .15);
    M.grain(ctx, t, p.grana * .35, false);
  }
});

P.push({
  id: 'macchina', cat: 'Titoli', name: 'Macchina da scrivere', dur: 6, thumbT: 3.2,
  desc: 'Testo battuto a macchina lettera per lettera, con inchiostro irregolare, battute doppie e cursore. Su striscia di carta strappata o direttamente sul video.',
  tip: 'Il suono dei tasti è sincronizzato a ogni lettera: lascialo sotto la musica a −12 dB. Ottimo per date, luoghi e documenti ufficiali.',
  params: [
    { k: 'testo', label: 'Testo', type: 'textarea', def: 'TORINO, 4 MAGGIO 1949.\nORE 17:03. NEBBIA FITTA SULLA COLLINA.' },
    { k: 'stile', label: 'Supporto', type: 'select', opts: ['Striscia di carta', 'Sul video', 'Foglio intero'], def: 'Striscia di carta' },
    { k: 'velocita', label: 'Lettere al secondo', type: 'range', min: 6, max: 30, step: 1, def: 16 },
    { k: 'posizione', label: 'Posizione', type: 'select', opts: ['Basso', 'Centro', 'Alto'], def: 'Basso' },
    accentP(PAL.inchiostro), grainP()
  ],
  timing(p) {
    const r = M.rng(42); const tx = String(p.testo); const ts = []; let t = .45; const sp = 1 / (p.velocita || 16);
    for (const ch of tx) { ts.push(t); t += ch === '\n' ? .45 : (/[.,;:!?]/.test(ch) ? sp * 3.2 : sp * (.6 + r() * .8)); }
    return ts;
  },
  sfx(p, D) {
    const ts = this.timing(p); const tx = Array.from(String(p.testo)); const cues = [];
    ts.forEach((t, i) => { if (tx[i] === '\n') { cues.push({ s: 'bell', t: t - .2, g: .5 }, { s: 'whoosh', t: t - .1, d: .3, g: .25 }); } else if (tx[i] !== ' ') cues.push({ s: 'key', t, g: .8, v: M.hash(i) }); });
    return cues;
  },
  draw(ctx, t, D, p, env) {
    const ts = this.timing(p); const tx = Array.from(String(p.testo)); const r = M.rng(7);
    const mode = p.stile; const ex = ph(t, D - .6, .55, E.swift);
    const size = mode === 'Foglio intero' ? 64 : 52; const lh = size * 1.35;
    M.font(ctx, size, F.type); const linesArr = String(p.testo).split('\n');
    const maxW = Math.max(...linesArr.map(l => ctx.measureText(l).width));
    const blockH = linesArr.length * lh;
    let x0 = 170, y0 = p.posizione === 'Alto' ? 150 : p.posizione === 'Centro' ? H / 2 - blockH / 2 : H - 150 - blockH;
    if (mode === 'Foglio intero') { ground(ctx, 'Carta', t); x0 = W / 2 - maxW / 2; y0 = H / 2 - blockH / 2; }
    const ink = mode === 'Sul video' ? PAL.carta : p.accento;
    ctx.save(); ctx.globalAlpha = 1 - ex;
    if (mode === 'Striscia di carta') {
      const sp = ph(t, 0, .45, E.film); const pw = maxW + 120, phh = blockH + 70;
      ctx.save(); ctx.translate(x0 - 60 + (1 - sp) * -80, y0 - 50); ctx.rotate(-.006);
      const pts = M.roughRect(0, 0, pw, phh, 5, 8, 11, true); ctx.shadowColor = 'rgba(0,0,0,.45)'; ctx.shadowBlur = 24; ctx.shadowOffsetY = 10; ctx.globalAlpha *= sp; M.poly(ctx, pts); ctx.fillStyle = PAL.carta; ctx.fill(); ctx.shadowColor = 'transparent'; M.poly(ctx, pts); M.paperFill(ctx, null, 1.2);
      ctx.restore();
    }
    let li = 0, x = x0, last = null;
    tx.forEach((ch, i) => {
      if (ch === '\n') { li++; x = x0; return; }
      M.font(ctx, size, F.type); const w = ctx.measureText(ch).width;
      const tt = ts[i]; const k = t - tt;
      if (k >= 0) {
        const dens = .78 + M.hash(i * 3.1) * .22; const jy = (M.hash(i * 1.7) - .5) * 3, rot = (M.hash(i * 5.3) - .5) * .035;
        const strike = k < .05 ? 1.6 : 1; ctx.save(); ctx.globalAlpha *= dens; ctx.fillStyle = ink;
        if (mode === 'Sul video') { ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 10; }
        ctx.translate(x + w / 2, y0 + lh * (li + 1) - lh * .28 + jy); ctx.rotate(rot); ctx.scale(strike, strike > 1 ? 1.04 : 1);
        ctx.fillText(ch, -w / 2, 0); if (M.hash(i * 9.9) > .82) { ctx.globalAlpha *= .45; ctx.fillText(ch, -w / 2 + .9, .4); }
        ctx.restore(); last = [x + w, y0 + lh * (li + 1) - lh * .28];
      }
      x += w;
    });
    /* cursore */
    const done = t > ts[ts.length - 1] + .1; const cur = last || [x0, y0 + lh * .72];
    if (!done || Math.floor(t * 2.2) % 2 === 0) { ctx.fillStyle = ink; ctx.globalAlpha *= .85; ctx.fillRect(cur[0] + 4, cur[1] - size * .72, size * .5, size * .85); }
    ctx.restore();
    M.grain(ctx, t, p.grana * .5, mode !== 'Foglio intero');
  }
});

P.push({
  id: 'impatto', cat: 'Titoli', name: 'Impatto da trailer', dur: 5, thumbT: 1.05,
  desc: 'Parole che sbattono a schermo a ritmo, con sfocatura di movimento, lampo e scossa di camera. Il gancio dei primi 15 secondi.',
  tip: 'Monta le parole sui colpi di cassa della musica: imposta il ritmo uguale alla distanza tra i colpi (es. 120 BPM = 0,5 s).',
  params: [
    { k: 'parole', label: 'Battute (una per riga)', type: 'textarea', def: 'UNA SQUADRA.\nUNA CITTÀ.\nUNA LEGGENDA.' },
    { k: 'ritmo', label: 'Secondi per battuta', type: 'range', min: .3, max: 2, step: .05, def: .95 },
    { k: 'ultima', label: 'Ultima battuta in colore accento', type: 'bool', def: true },
    bgP('Nero'), accentP(), grainP()
  ],
  sfx(p, D) { const ls = M.lines(p.parole); const c = [{ s: 'riser', t: 0, d: .55, g: .7 }]; ls.forEach((l, i) => c.push({ s: 'impact', t: .55 + i * p.ritmo, g: i === ls.length - 1 ? 1.1 : .85 })); c.push({ s: 'sub', t: .55 + (ls.length - 1) * p.ritmo, g: .7 }); return c; },
  draw(ctx, t, D, p, env) {
    ground(ctx, p.sfondo, t);
    const ls = M.lines(p.parole); const n = ls.length; const R = p.ritmo; const t0 = .55;
    const i = Math.min(n - 1, Math.floor((t - t0) / R)); if (t < t0) { finish(ctx, t, p); return; }
    const k = t - (t0 + i * R); const last = i === n - 1;
    const ex = last ? ph(t, D - .5, .45, E.in3) : 0;
    ctx.save(); shake(ctx, t, t0 + i * R, last ? 22 : 14, .35);
    const word = ls[i]; const size = M.fit(ctx, word, F.display, 300, W - 300, 400, .02);
    const col = (last && p.ultima) ? p.accento : PAL.carta;
    const sIn = 1 + .45 * (1 - E.outExpo(k / .2)); const creep = 1 + .05 * (k / R) + (last ? .05 * inv(t0 + i * R, D, t) : 0);
    const s = sIn * creep * (1 + ex * .25);
    /* scie: copie a scala intermedia */
    if (k < .2) for (let j = 4; j >= 1; j--) { const kk = Math.max(0, k - j * .018); const ss = (1 + .45 * (1 - E.outExpo(kk / .2))) * creep; alpha(ctx, .16, () => { ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(ss, ss); T(ctx, word, 0, size * .36, { size, fam: F.display, tr: .02, align: 'center', color: col }); ctx.restore(); }); }
    alpha(ctx, (1 - ex) * clamp(k / .03), () => { ctx.save(); ctx.translate(W / 2, H / 2); ctx.scale(s, s); T(ctx, word, 0, size * .36, { size, fam: F.display, tr: .02, align: 'center', color: col }); ctx.restore(); });
    ctx.restore();
    /* lampo */
    const fl = 1 - clamp(k / .12); if (fl > 0) { ctx.fillStyle = `rgba(255,250,240,${(fl * .35).toFixed(3)})`; ctx.fillRect(0, 0, W, H); }
    /* scintille di polvere */
    const r = M.rng(i * 17 + 3); ctx.fillStyle = rgba(PAL.carta, .7);
    for (let j = 0; j < 40; j++) { const a = r() * Math.PI * 2, sp = 200 + r() * 900; const d = sp * E.out3(k * 1.3); const x = W / 2 + Math.cos(a) * (180 + d), y = H / 2 + Math.sin(a) * (80 + d * .5); const al = (1 - clamp(k * 1.6)) * (.3 + r() * .7); if (al > 0) { ctx.globalAlpha = al; ctx.fillRect(x, y, 2 + r() * 3, 2 + r() * 3); } }
    ctx.globalAlpha = 1;
    finish(ctx, t, p);
  }
});

/* =============================================================== INFORMAZIONI */

P.push({
  id: 'sottopancia', cat: 'Informazioni', name: 'Sottopancia', dur: 5.5, thumbT: 2.2,
  desc: 'Nome e ruolo di chi parla o di chi è in foto. Quattro stili: Cinema, Archivio (cartellino scritto a mano), Minimale, Televisivo.',
  tip: 'Tienilo a schermo almeno il tempo di leggerlo due volte (4–6 s). Usa lo stesso stile per tutto il video: la coerenza è ciò che fa sembrare professionale.',
  params: [
    { k: 'nome', label: 'Nome', type: 'text', def: 'Valentino Mazzola' },
    { k: 'ruolo', label: 'Ruolo', type: 'text', def: 'Capitano del Grande Torino · 1942–1949' },
    { k: 'variante', label: 'Stile', type: 'select', opts: ['Cinema', 'Archivio', 'Minimale', 'Televisivo'], def: 'Cinema' },
    { k: 'lato', label: 'Lato', type: 'select', opts: ['Sinistra', 'Destra'], def: 'Sinistra' },
    { k: 'fondino', label: 'Ombra di leggibilità', type: 'bool', def: true },
    accentP(), grainP()
  ],
  sfx: (p, D) => p.variante === 'Archivio' ? [{ s: 'whoosh', t: .05, d: .5, g: .35 }, { s: 'chalk', t: .55, d: .7, g: .35 }] : [{ s: 'whoosh', t: .05, d: .45, g: .35 }, { s: 'whoosh', t: D - .55, d: .45, g: .25 }],
  draw(ctx, t, D, p) {
    const right = p.lato === 'Destra'; const ex = ph(t, D - .7, .6, E.swift); const v = p.variante;
    const X = right ? W - 150 : 150, Y = 860;
    if (p.fondino && v !== 'Archivio') scrim(ctx, right ? W - 380 : 380, Y - 20, 760, 260, ph(t, 0, .6, E.out3) * (1 - ph(t, D - .5, .5)));
    ctx.save();
    if (right) { ctx.translate(W, 0); ctx.scale(-1, 1); }
    const flipText = (fn) => { ctx.save(); if (right) { ctx.translate(W, 0); ctx.scale(-1, 1); } fn(); ctx.restore(); };
    const bx = 150;
    if (v === 'Cinema') {
      const bh = 150, bp = ph(t, 0, .45, E.film) * (1 - ph(t, D - .35, .3, E.swift));
      ctx.fillStyle = p.accento; ctx.fillRect(bx, Y - 110, 8, bh * bp);
      M.font(ctx, 76, F.display); const nw = M.textW(ctx, p.nome.toUpperCase(), 76 * .02);
      M.font(ctx, 28, F.body, 500); const rw = M.textW(ctx, p.ruolo.toUpperCase(), 28 * .12);
      const np = ph(t, .2, .8, E.film) * (1 - ex), rp = ph(t, .38, .8, E.film) * (1 - ph(t, D - .75, .55, E.swift));
      flipText(() => {
        const nx = right ? W - bx - 30 - nw : bx + 30, rx = right ? W - bx - 30 - rw : bx + 30;
        mask(ctx, right ? 0 : bx + 10, Y - 120, right ? W - bx - 10 : W, 104, () => T(ctx, p.nome.toUpperCase(), nx + (right ? 1 : -1) * (1 - np) * (nw + 40), Y - 30, { size: 76, fam: F.display, tr: .02, color: PAL.carta }));
        mask(ctx, right ? 0 : bx + 10, Y - 10, right ? W - bx - 10 : W, 50, () => T(ctx, p.ruolo.toUpperCase(), rx + (right ? 1 : -1) * (1 - rp) * (rw + 40), Y + 26, { size: 28, weight: 500, tr: .12, color: rgba(PAL.carta, .85) }));
      });
    } else if (v === 'Archivio') {
      const sp = ph(t, 0, .6, E.film), o = ex;
      M.font(ctx, 70, F.hand); const nw = Math.max(ctx.measureText(p.nome.toUpperCase()).width, (M.font(ctx, 36, F.hand), ctx.measureText(p.ruolo.toUpperCase()).width)) + 100;
      ctx.save(); ctx.translate(bx + (1 - sp) * -60 - o * 80, Y - 150 + (1 - sp) * 30); ctx.rotate((-2 + (1 - sp) * -4) * Math.PI / 180); ctx.globalAlpha = sp * (1 - o);
      const pts = M.roughRect(0, 0, nw, 190, 3, 9, 21, false); ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 22; ctx.shadowOffsetY = 10; M.poly(ctx, pts); ctx.fillStyle = PAL.carta; ctx.fill(); ctx.shadowColor = 'transparent'; M.poly(ctx, pts); M.paperFill(ctx, null, 1);
      ctx.fillStyle = 'rgba(240,232,210,.6)'; ctx.save(); ctx.translate(nw * .45, -12); ctx.rotate(-.06); ctx.fillRect(0, 0, 130, 34); ctx.restore();
      flipText(() => { }); ctx.restore();
      /* testo a mano scritto progressivamente */
      ctx.save(); ctx.translate(bx + (1 - sp) * -60 - o * 80, Y - 150 + (1 - sp) * 30); ctx.rotate((-2 + (1 - sp) * -4) * Math.PI / 180); ctx.globalAlpha = sp * (1 - o);
      if (right) { ctx.translate(nw, 0); ctx.scale(-1, 1); ctx.translate(-0, 0); }
      const wp = ph(t, .5, 1.0, E.lin), rp2 = ph(t, 1.3, .9, E.lin);
      mask(ctx, 0, 0, 50 + (nw - 50) * wp, 110, () => T(ctx, p.nome.toUpperCase(), 48, 92, { size: 70, fam: F.hand, color: PAL.inchiostro }));
      M.stroke(ctx, M.handLine(44, 108, 44 + Math.min(nw - 80, 360), 104, 3, 2), ph(t, 1.1, .4, E.io3), 4, p.accento, { alpha: .9 });
      mask(ctx, 0, 110, 50 + (nw - 50) * rp2, 80, () => T(ctx, p.ruolo.toUpperCase(), 48, 158, { size: 36, fam: F.hand, color: PAL.inchiostro }));
      ctx.restore();
    } else if (v === 'Minimale') {
      const lp = ph(t, .1, .9, E.film) * (1 - ex);
      ctx.fillStyle = rgba(PAL.carta, .7); ctx.fillRect(bx, Y - 4, 480 * lp, 1.5); ctx.strokeStyle = rgba(PAL.carta, .9 * lp); if (lp > .02) M.cross(ctx, bx, Y - 3, 10, 1.5);
      flipText(() => {
        const ax = right ? W - bx : bx, al = right ? 'right' : 'left';
        alpha(ctx, 1 - ex, () => AT(ctx, p.nome, ax, Y - 26, { size: 48, weight: 600, tr: .01, align: al, color: PAL.carta }, i => { const a = ph(t, .2 + i * .02, .6, E.out3); return { a, dy: (1 - a) * 12 }; }));
        alpha(ctx, (1 - ex) * ph(t, .6, .8, E.out3), () => T(ctx, p.ruolo, ax, Y + 40, { size: 26, weight: 400, tr: .02, align: al, color: rgba(PAL.carta, .7) }));
      });
    } else {
      M.font(ctx, 62, F.display); const nw = M.textW(ctx, p.nome.toUpperCase(), 62 * .02) + 70;
      M.font(ctx, 26, F.body, 600); const rw = M.textW(ctx, p.ruolo.toUpperCase(), 26 * .1) + 50;
      const a1 = ph(t, 0, .55, E.film) * (1 - ph(t, D - .5, .45, E.swift)), a2 = ph(t, .15, .55, E.film) * (1 - ph(t, D - .62, .45, E.swift));
      ctx.save(); ctx.transform(1, 0, -.18, 1, 0, 0);
      ctx.fillStyle = PAL.carta; ctx.fillRect(bx + 160, Y - 118, nw * a1, 92);
      ctx.fillStyle = p.accento; ctx.fillRect(bx + 160 + 18, Y - 26, rw * a2, 50);
      ctx.restore();
      flipText(() => {
        const nx = right ? W - bx - 30 - nw + 40 : bx + 30, rx = right ? W - bx - 30 - rw + 30 : bx + 30;
        mask(ctx, right ? W - bx - 30 - nw * a1 + 20 : bx, Y - 118, nw * a1, 92, () => T(ctx, p.nome.toUpperCase(), nx + 4, Y - 44, { size: 62, fam: F.display, tr: .02, color: PAL.inchiostro }));
        mask(ctx, right ? W - bx - 30 - rw * a2 + 10 : bx, Y - 26, rw * a2 + 20, 50, () => T(ctx, p.ruolo.toUpperCase(), rx + 8, Y + 9, { size: 26, weight: 600, tr: .1, color: PAL.carta }));
      });
    }
    ctx.restore();
    M.grain(ctx, t, p.grana * .6, true);
  }
});

const SCRAMBLE = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#/·';
function decode(str, t, t0, per = .035, spin = .35) {
  return Array.from(str).map((ch, i) => { const st = t0 + i * per; if (ch === ' ' || t >= st + spin) return ch; if (t < st) return ' '; return SCRAMBLE[Math.floor(M.hash(i * 3.3 + Math.floor(t * 30)) * SCRAMBLE.length)]; }).join('');
}
P.push({
  id: 'luogo', cat: 'Informazioni', name: 'Luogo e data', dur: 6, thumbT: 2.6,
  desc: 'Indicazione di luogo stile reportage: le lettere si decifrano una alla volta, le coordinate scorrono come su un rilevatore, mirino che si disegna.',
  tip: 'Usalo in apertura di ogni scena che cambia città o anno. Il ticchettio audio va tenuto basso: è un dettaglio, non un effetto.',
  params: [
    { k: 'luogo', label: 'Luogo', type: 'text', def: 'SUPERGA, TORINO' },
    { k: 'dettaglio', label: 'Dettaglio', type: 'text', def: 'Basilica di Superga · 669 m s.l.m.' },
    { k: 'data', label: 'Data e ora', type: 'text', def: '4 MAGGIO 1949 — ORE 17:03' },
    { k: 'coord', label: 'Coordinate', type: 'text', def: '45.0803° N   7.7672° E' },
    { k: 'posizione', label: 'Posizione', type: 'select', opts: ['Basso sinistra', 'Alto sinistra', 'Centro'], def: 'Basso sinistra' },
    { k: 'fondino', label: 'Ombra di leggibilità', type: 'bool', def: true },
    accentP(), grainP()
  ],
  sfx: (p) => { const c = []; for (let i = 0; i < 18; i++) c.push({ s: 'tick', t: .3 + i * .045, g: .5 }); for (let i = 0; i < 10; i++) c.push({ s: 'tick', t: 1.2 + i * .06, g: .35 }); return c; },
  draw(ctx, t, D, p) {
    const pos = p.posizione; const center = pos === 'Centro';
    const X = center ? W / 2 : 150, Y = pos === 'Alto sinistra' ? 200 : center ? H / 2 - 40 : H - 250; const al = center ? 'center' : 'left';
    const ex = ph(t, D - .6, .5, E.swift);
    if (p.fondino) scrim(ctx, center ? W / 2 : X + 360, Y + 60, center ? 900 : 780, 300, ph(t, 0, .6, E.out3) * (1 - ex));
    ctx.save(); ctx.globalAlpha = 1 - ex;
    /* mirino */
    if (!center) {
      const rp = ph(t, 0, .9, E.film); ctx.strokeStyle = p.accento; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(X + 26, Y - 26, 22, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * rp); ctx.stroke();
      ctx.globalAlpha *= rp; M.cross(ctx, X + 26, Y - 26, 32 * rp, 2); ctx.fillStyle = p.accento; ctx.beginPath(); ctx.arc(X + 26, Y - 26, 5 * (.6 + .4 * Math.sin(t * 6)), 0, 7); ctx.fill(); ctx.globalAlpha = 1 - ex;
    }
    const tx = center ? X : X + 80;
    const lu = decode(p.luogo.toUpperCase(), t, .25, .04, .3);
    T(ctx, lu, tx, Y, { size: 84, fam: F.display, tr: .03, align: al, color: PAL.carta });
    const lp = ph(t, .5, .8, E.film);
    ctx.fillStyle = p.accento; if (center) ctx.fillRect(X - 200 * lp, Y + 26, 400 * lp, 4); else ctx.fillRect(tx, Y + 26, 300 * lp, 4);
    alpha(ctx, ph(t, .9, .6, E.out3), () => T(ctx, p.dettaglio, tx, Y + 76, { size: 30, weight: 500, align: al, color: rgba(PAL.carta, .85) }));
    T(ctx, decode(p.data.toUpperCase(), t, 1.15, .03, .25), tx, Y + 124, { size: 26, weight: 600, tr: .22, align: al, color: PAL.carta });
    /* coordinate che scorrono */
    const cp = ph(t, 1.4, 1.4, E.out5);
    const cs = p.coord.replace(/\d+\.\d+/g, m => { const v = parseFloat(m); const dec = (m.split('.')[1] || '').length; return (v * cp + (1 - cp) * (v * .2)).toFixed(dec); });
    alpha(ctx, ph(t, 1.4, .3), () => T(ctx, cs, tx, Y + 166, { size: 34, fam: F.mono, tr: .06, align: al, color: rgba(PAL.carta, .7) }));
    ctx.restore();
    M.grain(ctx, t, p.grana * .6, true);
  }
});

P.push({
  id: 'scheda', cat: 'Informazioni', name: 'Scheda giocatore', dur: 7, thumbT: 3.4, media: true,
  desc: 'Presentazione del protagonista: foto in duotono incorniciata a registro, numero di maglia gigante sullo sfondo, nome, ruolo e statistiche che contano fino al valore.',
  tip: 'Carica un ritratto (anche ritagliato male: viene incorniciato). Ideale quando un giocatore entra nella storia per la prima volta.',
  params: [
    { k: 'nome', label: 'Nome', type: 'text', def: 'Valentino' },
    { k: 'cognome', label: 'Cognome', type: 'text', def: 'Mazzola' },
    { k: 'numero', label: 'Numero di maglia', type: 'text', def: '10' },
    { k: 'ruolo', label: 'Ruolo', type: 'text', def: 'Mezzala · Capitano' },
    { k: 'nato', label: 'Nascita', type: 'text', def: 'Cassano d\'Adda, 26 gennaio 1919' },
    { k: 'stat', label: 'Statistiche (Nome|valore per riga)', type: 'textarea', def: 'Presenze|195\nGol|118\nScudetti|5' },
    { k: 'tono', label: 'Tono foto', type: 'select', opts: M.TONES, def: 'Duotono verde' },
    bgP('Verde campo'), accentP(), grainP()
  ],
  sfx: (p) => { const c = [{ s: 'whoosh', t: .1, d: .7, g: .5 }, { s: 'hit', t: .9, g: .6 }]; for (let i = 0; i < 14; i++) c.push({ s: 'tick', t: 2.2 + i * .07 * (1 + i * .08), g: .45 }); c.push({ s: 'hit', t: 3.7, g: .5 }); return c; },
  draw(ctx, t, D, p, env) {
    ground(ctx, p.sfondo, t);
    const ex = ph(t, D - .8, .7, E.swift);
    ctx.save(); drift(ctx, t, D, .025);
    /* numero gigante */
    alpha(ctx, ph(t, .3, 1.6, E.out3) * (1 - ex), () => { ctx.save(); ctx.translate(-60 * E.glide(t / D), 0); ctx.globalAlpha *= .9; T(ctx, p.numero, W + 40, H + 40, { size: 1100, fam: F.display, align: 'right', stroke: rgba(PAL.carta, .16), lw: 3 }); ctx.restore(); });
    /* foto */
    const fx = 190, fy = 150, fw = 600, fh = 780;
    const rv = ph(t, .2, 1.1, E.film);
    const src = M.toned(env.media || M.samplePortrait(), p.tono, env.mediaKey || 'portrait');
    alpha(ctx, 1 - ex, () => {
      mask(ctx, fx, fy + fh * (1 - rv), fw, fh * rv, () => M.cover(ctx, src, fx, fy, fw, fh, 1.12 - .1 * E.out3(inv(.2, 3, t)) + .03 * (t / D), .5, .4));
      ctx.save(); ctx.strokeStyle = rgba(PAL.carta, .45); ctx.lineWidth = 1.5; ctx.strokeRect(fx, fy, fw, fh * rv); ctx.restore();
      M.regFrame(ctx, fx - 24, fy - 24, fw + 48, fh + 48, ph(t, 0, 1.2, E.film), PAL.carta, .55, 1.5);
    });
    const tx = 900;
    alpha(ctx, 1 - ex, () => {
      ctx.fillStyle = p.accento; ctx.fillRect(tx, 238, 22 * ph(t, .6, .4, E.out3), 22);
      AT(ctx, 'N. ' + p.numero + '  ·  ' + p.ruolo.toUpperCase(), tx + 40, 258, { size: 26, weight: 600, tr: .24, color: rgba(PAL.carta, .85) }, i => ({ a: ph(t, .7 + i * .015, .4, E.out3) }));
      mask(ctx, tx - 10, 270, 1000, 90, () => T(ctx, p.nome.toUpperCase(), tx, 340 + (1 - ph(t, .8, .8, E.film)) * 90, { size: 66, weight: 500, tr: .2, color: PAL.carta }));
      const cs = M.fit(ctx, p.cognome.toUpperCase(), F.display, 220, 900);
      mask(ctx, tx - 10, 350, 1000, cs * 1.05, () => T(ctx, p.cognome.toUpperCase(), tx, 350 + cs * .98 + (1 - ph(t, .95, .9, E.film)) * cs, { size: cs, fam: F.display, tr: .01, color: PAL.carta }));
      const ly = 350 + cs + 40; ctx.fillStyle = rgba(PAL.carta, .35); ctx.fillRect(tx, ly, 820 * ph(t, 1.3, 1, E.film), 1.5);
      alpha(ctx, ph(t, 1.5, .8, E.out3), () => T(ctx, p.nato, tx, ly + 52, { size: 28, weight: 400, color: rgba(PAL.carta, .75) }));
      const st = M.rows(p.stat).slice(0, 4); const cw = 820 / Math.max(1, st.length);
      st.forEach(([lab, val], i) => {
        const x = tx + i * cw, y = ly + 220; const k = ph(t, 2.1 + i * .25, 1.5, E.out5); const tv = parseNum(val), dec = decOf(val);
        alpha(ctx, ph(t, 2.0 + i * .25, .4), () => {
          T(ctx, fmtIt(tv * k, dec), x, y, { size: 120, fam: F.display, color: i === 0 ? p.accento : PAL.carta });
          T(ctx, lab.toUpperCase(), x + 2, y + 44, { size: 22, weight: 600, tr: .24, color: rgba(PAL.carta, .7) });
        });
      });
    });
    ctx.restore();
    finish(ctx, t, p);
  }
});

/* =============================================================== DATI */

P.push({
  id: 'contatore', cat: 'Dati', name: 'Numero gigante', dur: 6, thumbT: 3.2,
  desc: 'Un numero che fa notizia: le cifre girano come un contachilometri meccanico (con sfocatura di movimento) e si fermano sul valore, con etichetta e nota.',
  tip: 'Un solo numero per schermata. Fai dire il numero alla voce fuori campo un istante dopo che si ferma (a circa 2,6 s).',
  params: [
    { k: 'numero', label: 'Numero', type: 'text', def: '1.257' },
    { k: 'prefisso', label: 'Prefisso', type: 'text', def: '' },
    { k: 'suffisso', label: 'Suffisso', type: 'text', def: '' },
    { k: 'etichetta', label: 'Etichetta', type: 'text', def: 'GIORNI SENZA SCONFITTE IN CASA' },
    { k: 'nota', label: 'Nota', type: 'text', def: 'Stadio Filadelfia, 17 gennaio 1943 – 30 aprile 1949' },
    { k: 'stile', label: 'Animazione', type: 'select', opts: ['Contachilometri', 'Conteggio'], def: 'Contachilometri' },
    bgP('Verde campo'), accentP(), grainP()
  ],
  sfx: () => { const c = []; let tt = .3; for (let i = 0; i < 22; i++) { c.push({ s: 'tick', t: tt, g: .4 }); tt += .04 + i * .006; } c.push({ s: 'impact', t: 2.45, g: .8 }); return c; },
  draw(ctx, t, D, p) {
    ground(ctx, p.sfondo, t);
    const ex = ph(t, D - .7, .6, E.swift);
    ctx.save(); drift(ctx, t, D, .03);
    const ink = isDark(p.sfondo) || p.sfondo === 'Trasparente' ? PAL.carta : PAL.inchiostro;
    const raw = String(p.numero).trim(); const target = parseNum(raw); const dec = decOf(raw);
    const k = E.out5(inv(.3, 2.4, t));
    const size = 380; M.font(ctx, size, F.display);
    const str = fmtIt(target, dec); const digitW = ctx.measureText('0').width;
    const parts = Array.from(p.prefisso + str + p.suffisso);
    const widths = parts.map(ch => /\d/.test(ch) ? digitW : ctx.measureText(ch).width);
    const total = widths.reduce((a, b) => a + b, 0); let x = W / 2 - total / 2; const y = H / 2 + size * .2 - 40;
    const intDigits = str.replace(/\D/g, '').length; let di = 0;
    alpha(ctx, ph(t, .1, .4) * (1 - ex), () => parts.forEach((ch, i) => {
      if (/\d/.test(ch) && !(i < p.prefisso.length) && i < p.prefisso.length + str.length) {
        const place = intDigits - 1 - di; di++;
        const v = target * Math.pow(10, dec) * (p.stile === 'Conteggio' ? 1 : k);
        if (p.stile === 'Conteggio') { const cur = Math.floor(target * Math.pow(10, dec) * k); const s = String(cur).padStart(intDigits, '0'); T(ctx, s[di - 1], x + widths[i] / 2, y, { size, fam: F.display, color: ink, align: 'center' }); }
        else {
          const pos = v / Math.pow(10, place); const d = Math.floor(pos) % 10; let fr = pos - Math.floor(pos);
          const roll = place === 0 ? fr : smooth(.85, 1, fr);
          const speed = (target * Math.pow(10, dec) / Math.pow(10, place)) * (E.out5(inv(.3, 2.4, t + .01)) - k) * 100;
          mask(ctx, x - 10, y - size * .8, widths[i] + 20, size * .86, () => {
            for (let j = -1; j <= 1; j++) {
              const dd = (d + j + 10) % 10;
              const off = (j - roll) * size * .98;
              const blur = Math.min(10, Math.abs(speed) * .6);
              ctx.save(); if (blur > .5 && k < .99) ctx.filter = `blur(${blur.toFixed(1)}px)`;
              T(ctx, String(dd), x + widths[i] / 2, y + off, { size, fam: F.display, color: ink, align: 'center' }); ctx.restore();
            }
          });
        }
      } else T(ctx, ch, x, y, { size, fam: F.display, color: ink });
      x += widths[i];
    }));
    /* etichetta */
    const lp = ph(t, 2.3, .9, E.film);
    ctx.fillStyle = p.accento; ctx.fillRect(W / 2 - 160 * lp, y + 56, 320 * lp, 6);
    alpha(ctx, (1 - ex), () => AT(ctx, p.etichetta.toUpperCase(), W / 2, y + 130, { size: 44, weight: 600, tr: .14, align: 'center', color: ink }, i => { const a = ph(t, 2.4 + i * .015, .5, E.out3); return { a, dy: (1 - a) * 12 }; }));
    alpha(ctx, ph(t, 3.0, .8, E.out3) * (1 - ex), () => T(ctx, p.nota, W / 2, y + 184, { size: 28, weight: 400, align: 'center', color: rgba(ink, .7) }));
    ctx.restore();
    finish(ctx, t, p);
  }
});

P.push({
  id: 'risultato', cat: 'Dati', name: 'Tabellino', dur: 8, thumbT: 5.2,
  desc: 'Risultato della partita con i marcatori che entrano uno alla volta: ad ogni gol il punteggio scatta. Stile tabellone o cartoncino d\'archivio.',
  tip: 'Sincronizza ogni marcatore con l\'immagine del gol nel montaggio: i gol arrivano ogni "Passo gol" secondi a partire da 1,8 s.',
  params: [
    { k: 'casa', label: 'Squadra di casa', type: 'text', def: 'Torino' },
    { k: 'ospiti', label: 'Squadra ospite', type: 'text', def: 'Roma' },
    { k: 'colCasa', label: 'Colore casa', type: 'color', def: '#7a1f2b' },
    { k: 'colOspiti', label: 'Colore ospiti', type: 'color', def: '#c8792b' },
    { k: 'marcatori', label: 'Marcatori (Nome minuto|1 o 2)', type: 'textarea', def: 'Gabetto 3\'|1\nMazzola 15\'|1\nOssola 32\'|1\nAmadei 40\'|2\nLoik 51\'|1\nMazzola 63\'|1\nGabetto 70\'|1' },
    { k: 'info', label: 'Competizione e luogo', type: 'text', def: 'Serie A 1945/46 · Stadio Filadelfia' },
    { k: 'passo', label: 'Passo gol (s)', type: 'range', min: .3, max: 2, step: .05, def: .6 },
    { k: 'stile', label: 'Stile', type: 'select', opts: ['Tabellone', 'Cartoncino d\'archivio'], def: 'Tabellone' },
    grainP()
  ],
  sfx(p) { const c = [{ s: 'whoosh', t: .1, d: .6, g: .5 }]; M.rows(p.marcatori).forEach((r, i) => c.push({ s: 'hit', t: 1.8 + i * p.passo, g: .7 })); return c; },
  draw(ctx, t, D, p) {
    const rowsM = M.rows(p.marcatori); const ex = ph(t, D - .7, .6, E.swift);
    let s1 = 0, s2 = 0; const shown = [];
    rowsM.forEach((r, i) => { const tg = 1.8 + i * p.passo; if (t >= tg) { if (r[1] === '2') s2++; else s1++; shown.push({ r, i, tg }); } });
    const paper = p.stile !== 'Tabellone';
    const en = ph(t, 0, .8, E.film);
    const PWd = 1500, Y0 = 250, PHt = 600;
    ctx.save(); ctx.globalAlpha = 1 - ex; ctx.translate(0, (1 - en) * 80 + ex * -40);
    const x0 = W / 2 - PWd / 2;
    if (paper) {
      ctx.save(); ctx.translate(W / 2, Y0 + PHt / 2); ctx.rotate(-.012); ctx.translate(-W / 2, -(Y0 + PHt / 2));
      const pts = M.roughRect(x0, Y0, PWd, PHt, 3, 9, 4, false); ctx.shadowColor = 'rgba(0,0,0,.5)'; ctx.shadowBlur = 40; ctx.shadowOffsetY = 18; ctx.globalAlpha *= en; M.poly(ctx, pts); ctx.fillStyle = PAL.carta; ctx.fill(); ctx.shadowColor = 'transparent'; M.poly(ctx, pts); M.paperFill(ctx);
    } else {
      ctx.save(); ctx.fillStyle = 'rgba(12,31,25,.9)'; ctx.globalAlpha *= en; ctx.fillRect(x0, Y0, PWd * E.film(inv(0, .7, t)), PHt); ctx.fillStyle = PAL.rosso; ctx.fillRect(x0, Y0, PWd * E.film(inv(.1, .8, t)), 6);
    }
    const ink = paper ? PAL.inchiostro : PAL.carta; const fam = paper ? F.type : F.body;
    alpha(ctx, ph(t, .4, .6), () => T(ctx, p.info.toUpperCase(), W / 2, Y0 + 64, { size: 24, fam, weight: 600, tr: .24, align: 'center', color: rgba(ink, .75) }));
    /* stemmi semplificati */
    const crest = (cx, col, name, k) => { const s = E.outBack(k); if (s <= 0) return; ctx.save(); ctx.translate(cx, Y0 + 210); ctx.scale(s, s); ctx.fillStyle = col; ctx.beginPath(); ctx.moveTo(-46, -54); ctx.lineTo(46, -54); ctx.lineTo(46, 10); ctx.quadraticCurveTo(46, 50, 0, 64); ctx.quadraticCurveTo(-46, 50, -46, 10); ctx.closePath(); ctx.fill(); ctx.strokeStyle = rgba(ink, .5); ctx.lineWidth = 2; ctx.stroke(); T(ctx, name.slice(0, 1).toUpperCase(), 0, 22, { size: 64, fam: F.display, color: PAL.carta, align: 'center' }); ctx.restore(); };
    crest(x0 + 150, p.colCasa, p.casa, ph(t, .5, .6, E.lin)); crest(x0 + PWd - 150, p.colOspiti, p.ospiti, ph(t, .6, .6, E.lin));
    const ns = M.fit(ctx, p.casa.toUpperCase(), F.display, 92, 440);
    alpha(ctx, ph(t, .6, .6), () => { T(ctx, p.casa.toUpperCase(), x0 + 240, Y0 + 245, { size: Math.min(ns, M.fit(ctx, p.ospiti.toUpperCase(), F.display, 92, 440)), fam: F.display, color: ink }); T(ctx, p.ospiti.toUpperCase(), x0 + PWd - 240, Y0 + 245, { size: Math.min(ns, M.fit(ctx, p.ospiti.toUpperCase(), F.display, 92, 440)), fam: F.display, color: ink, align: 'right' }); });
    /* punteggio con scatto */
    const lastG = shown.length ? shown[shown.length - 1] : null; const bump = lastG ? 1 + .25 * (1 - E.out3(inv(lastG.tg, lastG.tg + .35, t))) : 1;
    alpha(ctx, ph(t, .8, .5), () => {
      ctx.save(); ctx.translate(W / 2, Y0 + 260); ctx.scale(bump, bump);
      T(ctx, s1 + ' – ' + s2, 0, 0, { size: 190, fam: F.display, color: paper ? PAL.inchiostro : PAL.carta, align: 'center' }); ctx.restore();
    });
    ctx.fillStyle = rgba(ink, .25); ctx.fillRect(x0 + 80, Y0 + 320, PWd - 160, 1.5);
    /* marcatori */
    const col1 = shown.filter(s => s.r[1] !== '2'), col2 = shown.filter(s => s.r[1] === '2');
    const drawList = (list, x, al) => list.forEach((s, j) => { const k = E.film(inv(s.tg, s.tg + .45, t)); alpha(ctx, k, () => T(ctx, s.r[0], x + (al === 'left' ? -1 : 1) * (1 - k) * 30, Y0 + 380 + j * 44, { size: paper ? 34 : 32, fam: paper ? F.hand : F.body, weight: 500, color: ink, align: al })); });
    const per = Math.max(col1.length, col2.length); ctx.save(); if (per > 5) { const sc = 5 / per; ctx.translate(0, Y0 + 350); ctx.scale(1, sc); ctx.translate(0, -(Y0 + 350)); }
    drawList(col1, x0 + 240, 'left'); drawList(col2, x0 + PWd - 240, 'right'); ctx.restore();
    ctx.restore(); ctx.restore();
    M.grain(ctx, t, p.grana * .5, true);
  }
});

P.push({
  id: 'confronto', cat: 'Dati', name: 'Testa a testa', dur: 7, thumbT: 4,
  desc: 'Confronto tra due giocatori o squadre: barre che crescono dal centro verso i lati, valori che contano, il migliore di ogni riga illuminato.',
  tip: 'Massimo 4–5 righe. Ordina dalla statistica più forte alla più sorprendente: l\'ultima riga è quella che il pubblico ricorda.',
  params: [
    { k: 'nome1', label: 'Lato sinistro', type: 'text', def: 'Valentino Mazzola' },
    { k: 'sotto1', label: 'Sottotitolo sinistro', type: 'text', def: 'Torino 1942–49' },
    { k: 'nome2', label: 'Lato destro', type: 'text', def: 'Giuseppe Meazza' },
    { k: 'sotto2', label: 'Sottotitolo destro', type: 'text', def: 'Inter 1927–40' },
    { k: 'righe', label: 'Righe (Statistica|sinistra|destra)', type: 'textarea', def: 'Presenze in A|195|239\nGol in A|118|197\nScudetti|5|3\nMedia gol|0,61|0,82' },
    bgP('Verde campo'), accentP(), grainP()
  ],
  sfx(p) { const c = [{ s: 'whoosh', t: .1, d: .6, g: .5 }]; M.rows(p.righe, 3).forEach((r, i) => c.push({ s: 'whoosh', t: 1.2 + i * .35, d: .4, g: .25 })); return c; },
  draw(ctx, t, D, p) {
    ground(ctx, p.sfondo, t);
    const ex = ph(t, D - .7, .6, E.swift); const ink = isDark(p.sfondo) || p.sfondo === 'Trasparente' ? PAL.carta : PAL.inchiostro;
    const rs = M.rows(p.righe, 3).slice(0, 6);
    ctx.save(); ctx.globalAlpha = 1 - ex; drift(ctx, t, D, .02);
    const hk = ph(t, .2, .9, E.film);
    const n1 = M.fit(ctx, p.nome1.toUpperCase(), F.display, 92, 760), n2 = M.fit(ctx, p.nome2.toUpperCase(), F.display, 92, 760), ns = Math.min(n1, n2);
    mask(ctx, 0, 110, W / 2 - 40, 140, () => T(ctx, p.nome1.toUpperCase(), W / 2 - 80 + (1 - hk) * -200, 220, { size: ns, fam: F.display, color: p.accento, align: 'right' }));
    mask(ctx, W / 2 + 40, 110, W, 140, () => T(ctx, p.nome2.toUpperCase(), W / 2 + 80 + (1 - hk) * 200, 220, { size: ns, fam: F.display, color: ink }));
    alpha(ctx, ph(t, .6, .6), () => { T(ctx, p.sotto1, W / 2 - 80, 266, { size: 26, color: rgba(ink, .7), align: 'right' }); T(ctx, p.sotto2, W / 2 + 80, 266, { size: 26, color: rgba(ink, .7) }); T(ctx, 'VS', W / 2, 212, { size: 40, fam: F.display, color: rgba(ink, .5), align: 'center' }); });
    const top = 360, rh = Math.min(150, 620 / Math.max(1, rs.length)), maxL = 720;
    rs.forEach(([lab, a, b], i) => {
      const y = top + i * rh; const va = parseNum(a), vb = parseNum(b), mx = Math.max(va, vb) || 1;
      const k = ph(t, 1.2 + i * .35, 1.2, E.film);
      alpha(ctx, ph(t, 1.1 + i * .35, .4), () => T(ctx, lab.toUpperCase(), W / 2, y, { size: 24, weight: 600, tr: .2, align: 'center', color: rgba(ink, .75) }));
      const bh = 26, by = y + 22;
      const winA = va >= vb, winB = vb >= va;
      ctx.fillStyle = rgba(ink, .08); ctx.fillRect(W / 2 - 10 - maxL, by, maxL, bh); ctx.fillRect(W / 2 + 10, by, maxL, bh);
      ctx.fillStyle = winA ? p.accento : rgba(ink, .45); ctx.fillRect(W / 2 - 10 - maxL * (va / mx) * k, by, maxL * (va / mx) * k, bh);
      ctx.fillStyle = winB ? ink : rgba(ink, .35); ctx.fillRect(W / 2 + 10, by, maxL * (vb / mx) * k, bh);
      const da = decOf(a), db = decOf(b);
      alpha(ctx, ph(t, 1.2 + i * .35, .3), () => {
        T(ctx, fmtIt(va * k, da), W / 2 - 24 - maxL * (va / mx) * k, by + bh - 2, { size: 52, fam: F.display, align: 'right', color: winA ? p.accento : rgba(ink, .6) });
        T(ctx, fmtIt(vb * k, db), W / 2 + 24 + maxL * (vb / mx) * k, by + bh - 2, { size: 52, fam: F.display, color: winB ? ink : rgba(ink, .6) });
      });
    });
    ctx.restore();
    finish(ctx, t, p);
  }
});

P.push({
  id: 'classifica', cat: 'Dati', name: 'Classifica', dur: 7, thumbT: 3.6,
  desc: 'Classifica a righe che entrano in sequenza; la squadra protagonista si accende con una barra di colore e le altre si abbassano.',
  tip: 'Mostra solo le prime 5–8 posizioni. Se racconti un sorpasso, duplica il preset e cambia l\'ordine: lo stacco tra i due dà l\'idea del ribaltone.',
  params: [
    { k: 'titolo', label: 'Titolo', type: 'text', def: 'SERIE A 1947/48' },
    { k: 'nota', label: 'Nota', type: 'text', def: 'Classifica finale · 2 punti a vittoria' },
    { k: 'righe', label: 'Righe (Squadra|punti)', type: 'textarea', def: 'Torino|65\nMilan|49\nJuventus|49\nTriestina|49\nAtalanta|48\nModena|48' },
    { k: 'evidenzia', label: 'Riga in evidenza (numero)', type: 'range', min: 0, max: 10, step: 1, def: 1 },
    bgP('Verde campo'), accentP(), grainP()
  ],
  sfx(p) { const c = [{ s: 'whoosh', t: .1, d: .6, g: .4 }]; M.rows(p.righe).forEach((r, i) => c.push({ s: 'tick', t: .7 + i * .12, g: .6 })); c.push({ s: 'hit', t: 2.2, g: .6 }); return c; },
  draw(ctx, t, D, p) {
    ground(ctx, p.sfondo, t);
    const ex = ph(t, D - .7, .6, E.swift); const ink = isDark(p.sfondo) || p.sfondo === 'Trasparente' ? PAL.carta : PAL.inchiostro;
    const rs = M.rows(p.righe).slice(0, 10);
    ctx.save(); ctx.globalAlpha = 1 - ex; drift(ctx, t, D, .025, W / 2, 300);
    const X = 420, Wd = 1080; const rh = Math.min(92, 620 / Math.max(1, rs.length)); const top = 330;
    mask(ctx, X - 10, 130, Wd, 110, () => T(ctx, p.titolo.toUpperCase(), X, 220 + (1 - ph(t, .1, .8, E.film)) * 100, { size: 92, fam: F.display, color: ink }));
    alpha(ctx, ph(t, .4, .6), () => T(ctx, p.nota, X + Wd, 220, { size: 26, color: rgba(ink, .7), align: 'right' }));
    ctx.fillStyle = p.accento; ctx.fillRect(X, 250, Wd * ph(t, .3, .9, E.film), 4);
    const hl = Math.round(p.evidenzia) - 1; const hk = ph(t, 2.2, .7, E.film);
    rs.forEach(([team, pts], i) => {
      const y = top + i * rh; const k = ph(t, .7 + i * .12, .8, E.film); const isH = i === hl;
      const dim = hl >= 0 && !isH ? 1 - .45 * hk : 1;
      ctx.save(); ctx.translate((1 - k) * 260, 0); ctx.globalAlpha *= k * dim;
      if (isH) { ctx.fillStyle = p.accento; ctx.fillRect(X - 20, y + 4, (Wd + 40) * hk, rh - 10); }
      else { ctx.fillStyle = rgba(ink, .14); ctx.fillRect(X, y + rh - 4, Wd, 1); }
      T(ctx, String(i + 1).padStart(2, '0'), X + 10, y + rh * .7, { size: rh * .5, fam: F.display, color: isH && hk > .5 ? PAL.carta : rgba(ink, .55) });
      T(ctx, team.toUpperCase(), X + 120, y + rh * .66, { size: rh * .38, weight: 600, tr: .06, color: isH && hk > .5 ? PAL.carta : ink });
      T(ctx, pts, X + Wd - 10, y + rh * .7, { size: rh * .5, fam: F.display, color: isH && hk > .5 ? PAL.carta : ink, align: 'right' });
      ctx.restore();
    });
    ctx.restore();
    finish(ctx, t, p);
  }
});

P.push({
  id: 'timeline', cat: 'Dati', name: 'Linea del tempo', dur: 10, thumbT: 3.3,
  desc: 'Linea del tempo orizzontale che la camera percorre: la linea si traccia, gli anni salgono da una maschera, l\'evento attivo è a fuoco e gli altri si attenuano.',
  tip: 'Ogni evento resta fermo circa (durata ÷ numero eventi) secondi: regola la durata sulla voce. Anni grandi e frasi brevi, massimo 6 parole.',
  params: [
    { k: 'eventi', label: 'Eventi (Anno|testo)', type: 'textarea', def: '1906|Nasce il Foot-Ball Club Torino\n1928|Il primo scudetto\n1943|Inizia il ciclo del Grande Torino\n1949|La tragedia di Superga\n1976|Lo scudetto di Radice' },
    bgP('Verde campo'), accentP(), grainP()
  ],
  sfx(p, D) { const ev = M.rows(p.eventi); const seg = (D - 1.2) / ev.length; return ev.map((e, i) => ({ s: 'whoosh', t: .3 + i * seg, d: .7, g: .35 })).concat(ev.map((e, i) => ({ s: 'pop', t: .85 + i * seg, g: .5 }))); },
  draw(ctx, t, D, p) {
    ground(ctx, p.sfondo, t);
    const ink = isDark(p.sfondo) || p.sfondo === 'Trasparente' ? PAL.carta : PAL.inchiostro;
    const ev = M.rows(p.eventi); const n = ev.length || 1; const gap = 640; const seg = (D - 1.2) / n;
    const ex = ph(t, D - .6, .5, E.swift);
    /* posizione della camera: viaggio + sosta per ogni evento */
    let cam = 0; for (let i = 0; i < n; i++) { const k = E.swift(inv(.3 + i * seg, .3 + i * seg + Math.min(.9, seg * .45), t)); cam = i === 0 ? k * 0 : cam + (k) * gap * (i > 0 ? 1 : 0); }
    cam = 0; for (let i = 1; i < n; i++) cam += gap * E.swift(inv(.3 + i * seg, .3 + i * seg + Math.min(.9, seg * .45), t));
    const active = Math.max(0, Math.min(n - 1, Math.floor((t - .3) / seg)));
    const baseX = W / 2 - cam, y = H / 2 + 40;
    ctx.save(); ctx.globalAlpha = 1 - ex;
    /* anni giganti in parallasse */
    ev.forEach((e, i) => { const k1 = ph(t, .3 + i * seg, .7, E.out3), k2 = i < n - 1 ? ph(t, .3 + (i + 1) * seg, .5, E.in2) : 0; const a = k1 * (1 - k2); if (a > 0) alpha(ctx, .06 * a, () => T(ctx, e[0], W / 2 + (1 - k1) * 120 - k2 * 120, H / 2 + 250, { size: 560, fam: F.display, align: 'center', color: ink })); });
    /* linea */
    const lineTo = baseX + (n - 1) * gap * Math.min(1, ph(t, .1, D - 1.4, E.lin) * 1.05) + 200;
    ctx.fillStyle = rgba(ink, .5); ctx.fillRect(baseX - 400, y, Math.max(0, lineTo - (baseX - 400)), 2);
    ev.forEach(([yr, txt], i) => {
      const x = baseX + i * gap; if (x < -400 || x > W + 400) return;
      const ap = ph(t, .5 + i * seg, .8, E.film); const isA = i === active; const dim = isA ? 1 : .38;
      ctx.save(); ctx.globalAlpha *= dim;
      const s = E.outBack(ph(t, .55 + i * seg, .5, E.lin)); ctx.fillStyle = isA ? p.accento : ink; ctx.beginPath(); ctx.arc(x, y + 1, 12 * s, 0, 7); ctx.fill();
      if (isA) { ctx.strokeStyle = p.accento; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(x, y + 1, 12 + 14 * s + 4 * Math.sin(t * 4), 0, 7); ctx.globalAlpha *= .6; ctx.stroke(); ctx.globalAlpha /= .6; }
      ctx.fillStyle = rgba(ink, .5); ctx.fillRect(x - 1, y - 60 * ap, 2, 46 * ap);
      mask(ctx, x - 400, y - 250, 800, 180, () => T(ctx, yr, x, y - 80 + (1 - ap) * 170, { size: 150, fam: F.display, align: 'center', color: ink }));
      M.font(ctx, 36, F.body, 500); const ls = M.wrap(ctx, txt, 520);
      ls.forEach((l, li) => alpha(ctx, ph(t, .75 + i * seg + li * .1, .6, E.out3), () => T(ctx, l, x, y + 80 + li * 46, { size: 36, weight: 500, align: 'center', color: ink })));
      ctx.restore();
    });
    ctx.restore();
    finish(ctx, t, p);
  }
});

P.push({
  id: 'grafico', cat: 'Dati', name: 'Grafico andamento', dur: 7, thumbT: 4.6,
  desc: 'Grafico a linea che si traccia nel tempo con area sfumata, valori sui punti e il massimo cerchiato a pennarello. In scala reale, da zero.',
  tip: 'Racconta un picco o un crollo: scrivi nel campo "nota" cosa è successo nel punto più alto, apparirà vicino al cerchio.',
  params: [
    { k: 'titolo', label: 'Titolo', type: 'text', def: 'GOL SEGNATI DAL TORINO' },
    { k: 'serie', label: 'Dati (Etichetta|valore)', type: 'textarea', def: '42/43|68\n45/46|104\n46/47|104\n47/48|125\n48/49|78' },
    { k: 'nota', label: 'Nota sul massimo', type: 'text', def: 'Record della Serie A a girone unico' },
    { k: 'stile', label: 'Stile', type: 'select', opts: ['Pulito', 'Gesso'], def: 'Pulito' },
    bgP('Verde campo'), accentP(), grainP()
  ],
  sfx(p, D) { const s = M.rows(p.serie); const c = [{ s: p.stile === 'Gesso' ? 'chalk' : 'whoosh', t: .9, d: 2.2, g: .35 }]; s.forEach((r, i) => c.push({ s: 'pop', t: .9 + 2.2 * i / Math.max(1, s.length - 1), g: .4 })); c.push({ s: 'chalk', t: 3.4, d: .6, g: .5 }); return c; },
  draw(ctx, t, D, p) {
    ground(ctx, p.sfondo, t);
    const ink = isDark(p.sfondo) || p.sfondo === 'Trasparente' ? PAL.carta : PAL.inchiostro; const chalk = p.stile === 'Gesso';
    const s = M.rows(p.serie).map(r => [r[0], parseNum(r[1]), r[1]]); if (s.length < 2) return;
    const ex = ph(t, D - .7, .6, E.swift);
    const X0 = 260, X1 = W - 260, Y0 = 860, Y1 = 330;
    const max = Math.max(...s.map(r => r[1])); const mag = Math.pow(10, Math.floor(Math.log10(max || 1))); const step = [.1, .2, .25, .5, 1, 2].map(k => k * mag).find(k => max / k <= 5) || mag * 2; const top = Math.ceil(max * 1.08 / step) * step || 1;
    const sx = i => X0 + (X1 - X0) * i / (s.length - 1), sy = v => Y0 - (Y0 - Y1) * v / top;
    ctx.save(); ctx.globalAlpha = 1 - ex;
    mask(ctx, X0 - 10, 150, W, 110, () => T(ctx, p.titolo.toUpperCase(), X0, 240 + (1 - ph(t, .1, .8, E.film)) * 100, { size: 72, fam: F.display, color: ink }));
    /* griglia */
    const gp = ph(t, .3, 1, E.film);
    for (let v = 0; v <= top + 1e-9; v += step) { const y = sy(v); ctx.fillStyle = rgba(ink, v === 0 ? .55 : .12); ctx.fillRect(X0, y, (X1 - X0) * gp, v === 0 ? 2 : 1); alpha(ctx, gp, () => T(ctx, fmtIt(v), X0 - 24, y + 8, { size: 22, color: rgba(ink, .6), align: 'right' })); }
    s.forEach((r, i) => alpha(ctx, ph(t, .4 + i * .05, .5), () => T(ctx, r[0], sx(i), Y0 + 46, { size: 24, weight: 500, color: rgba(ink, .75), align: 'center' })));
    /* linea e area */
    const lp = ph(t, .9, 2.2, E.io3); const pts = s.map((r, i) => [sx(i), sy(r[1])]);
    const upto = lp * (s.length - 1);
    const path = []; for (let i = 0; i < s.length; i++) { if (i <= upto) path.push(pts[i]); else { const k = upto - (i - 1); if (k > 0) path.push([lerp(pts[i - 1][0], pts[i][0], k), lerp(pts[i - 1][1], pts[i][1], k)]); break; } }
    if (path.length > 1) {
      const g = ctx.createLinearGradient(0, Y1, 0, Y0); g.addColorStop(0, rgba(p.accento, .38)); g.addColorStop(1, rgba(p.accento, 0));
      ctx.beginPath(); ctx.moveTo(path[0][0], Y0); path.forEach(q => ctx.lineTo(q[0], q[1])); ctx.lineTo(path[path.length - 1][0], Y0); ctx.closePath(); ctx.fillStyle = g; ctx.fill();
      if (chalk) { M.stroke(ctx, path.flatMap((q, i) => i ? M.handLine(path[i - 1][0], path[i - 1][1], q[0], q[1], i, 3, 12) : []), 1, 7, ink, { taper: true, alpha: .9 }); }
      else { ctx.strokeStyle = ink; ctx.lineWidth = 5; ctx.lineJoin = 'round'; ctx.beginPath(); path.forEach((q, i) => i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1])); ctx.stroke(); }
    }
    const mi = s.findIndex(r => r[1] === max);
    pts.forEach((q, i) => { const k = ph(t, .9 + 2.2 * i / (s.length - 1), .4, E.lin); if (k <= 0) return; const sc = E.outBack(k); ctx.fillStyle = i === mi ? p.accento : ink; ctx.beginPath(); ctx.arc(q[0], q[1], 9 * sc, 0, 7); ctx.fill(); alpha(ctx, k, () => T(ctx, s[i][2], q[0], q[1] - 26, { size: 38, fam: F.display, color: i === mi ? p.accento : ink, align: 'center' })); });
    /* massimo cerchiato */
    const cp = ph(t, 3.4, .7, E.io3); const q = pts[mi];
    M.stroke(ctx, M.handEllipse(q[0], q[1] - 14, 84, 62, 7), cp, 6, p.accento, { taper: true });
    alpha(ctx, ph(t, 3.9, .6, E.out3), () => {
      M.font(ctx, 40, F.hand); const tw = ctx.measureText(p.nota).width;
      if (q[0] + 110 + tw < W - 80) T(ctx, p.nota, q[0] + 110, q[1] - 70, { size: 40, fam: F.hand, color: ink });
      else if (q[0] - 110 - tw > 80) T(ctx, p.nota, q[0] - 110, q[1] - 70, { size: 40, fam: F.hand, color: ink, align: 'right' });
      else T(ctx, p.nota, Math.min(W - 80 - tw / 2, Math.max(80 + tw / 2, q[0])), q[1] - 110, { size: 40, fam: F.hand, color: ink, align: 'center' });
    });
    ctx.restore();
    if (chalk && p.grana > 0) M.grain(ctx, t, .35, true);
    finish(ctx, t, p);
  }
});
})();
