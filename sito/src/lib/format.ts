import { LOCALE } from '../config';

export type Formato = 'numero' | 'percentuale' | 'delta-numero' | 'delta-percentuale';

function nf(decimali: number): Intl.NumberFormat {
  return new Intl.NumberFormat(LOCALE, {
    minimumFractionDigits: decimali,
    maximumFractionDigits: decimali,
    useGrouping: 'always',
  });
}

/** 471468 → "471.468" · 18.5 → "18,5" */
export function numero(valore: number, decimali = 0): string {
  return nf(decimali).format(valore);
}

/** Segno esplicito per i delta: "+" o "−" (meno tipografico). */
function segno(valore: number): string {
  if (valore > 0) return '+';
  if (valore < 0) return '−';
  return '';
}

/** Formatta un valore secondo il formato del frontmatter. */
export function formatta(valore: number, formato: Formato, decimali?: number): string {
  switch (formato) {
    case 'numero':
      return numero(valore, decimali ?? 0);
    case 'percentuale':
      return `${numero(valore, decimali ?? 0)}%`;
    case 'delta-numero':
      return `${segno(valore)}${numero(Math.abs(valore), decimali ?? 0)}`;
    case 'delta-percentuale':
      return `${segno(valore)}${numero(Math.abs(valore), decimali ?? 1)}%`;
  }
}

/** Variazione percentuale fra due valori. */
export function delta(prima: number, dopo: number): number {
  return ((dopo - prima) / prima) * 100;
}

export function arrotonda(valore: number, decimali: number): number {
  const f = 10 ** decimali;
  return Math.round(valore * f) / f;
}

export function isDelta(formato: Formato): boolean {
  return formato.startsWith('delta');
}

/** Classe colore per i delta misurati. */
export function toneClass(valore: number, formato: Formato): string {
  if (!isDelta(formato)) return '';
  return valore > 0 ? 'positive' : valore < 0 ? 'negative' : '';
}

const MESI = ['gen', 'feb', 'mar', 'apr', 'mag', 'giu', 'lug', 'ago', 'set', 'ott', 'nov', 'dic'];

/** 2026-10-02 → "2 ott 2026" */
export function dataBreve(d: Date): string {
  return `${d.getUTCDate()} ${MESI[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** Testo con ==parola== → HTML con <mark>. L'input viene prima escapato. */
export function conMarker(testo: string): string {
  return escapeHtml(testo).replace(/==(.+?)==/g, '<mark>$1</mark>');
}

/** Rimuove la sintassi del marker per contesti testuali (meta, alt, JSON-LD). */
export function senzaMarker(testo: string): string {
  return testo.replace(/==(.+?)==/g, '$1');
}

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/** Numero per il display Mono: virgola e punto più stretti (la Mono li spazia troppo). */
export function numeroHtml(testo: string): string {
  return escapeHtml(testo).replace(/[.,]/g, '<span class="sep">$&</span>');
}
