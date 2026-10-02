import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { PERSONA, SITE_URL } from '../config';

/** Immagini Open Graph 1200x630 nello stile Leonardi Editorial (Paper). */

const dir = join(process.cwd(), 'src/assets/og-fonts');
const fonts = [
  { name: 'Geist', data: readFileSync(join(dir, 'Geist-Regular.ttf')), weight: 400 as const },
  { name: 'Geist', data: readFileSync(join(dir, 'Geist-SemiBold.ttf')), weight: 600 as const },
  { name: 'Geist Mono', data: readFileSync(join(dir, 'GeistMono-Medium.ttf')), weight: 500 as const },
];

const C = {
  bg: '#F4F4EF',
  text: '#101216',
  secondary: '#575D66',
  border: '#CACBC2',
  accent: '#1D3FCF',
};

type Node = { type: string; props: Record<string, unknown> };
function h(type: string, style: Record<string, unknown>, ...children: (Node | string | null)[]): Node {
  const kids = children.filter((c) => c !== null);
  return { type, props: { style: { display: 'flex', ...style }, children: kids.length === 1 ? kids[0] : kids } };
}

export type OgInput = {
  /** Label Mono in alto, es. "CASO STUDIO · SEO". */
  eyebrow: string;
  /** Numero protagonista (opzionale). */
  numero?: string;
  titolo: string;
};

export async function ogPng({ eyebrow, numero, titolo }: OgInput): Promise<Buffer> {
  const label = { fontFamily: 'Geist Mono', fontWeight: 500, fontSize: 22, letterSpacing: '0.08em' };
  const tree = h(
    'div',
    {
      width: 1200,
      height: 630,
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      background: C.bg,
      color: C.text,
      padding: '64px 72px 56px',
      fontFamily: 'Geist',
    },
    h(
      'div',
      {
        display: 'flex',
        justifyContent: 'space-between',
        borderTop: `2px solid ${C.border}`,
        paddingTop: 16,
        color: C.secondary,
        ...label,
      },
      h('div', {}, eyebrow.toUpperCase()),
      h('div', {}, new URL(SITE_URL).host.toUpperCase()),
    ),
    h(
      'div',
      { display: 'flex', flexDirection: 'column' },
      numero
        ? h(
            'div',
            {
              fontFamily: 'Geist Mono',
              fontWeight: 500,
              fontSize: 150,
              lineHeight: 1,
              letterSpacing: '-0.06em',
              color: C.accent,
              borderTop: `6px solid ${C.accent}`,
              paddingTop: 24,
            },
            // virgola e punto più stretti, come nel sito
            ...numero
              .split(/([.,])/)
              .filter(Boolean)
              .map((p) => (/^[.,]$/.test(p) ? h('span', { margin: '0 -26px' }, p) : h('span', {}, p))),
          )
        : null,
      h(
        'div',
        {
          fontWeight: 600,
          fontSize: numero ? 54 : 84,
          lineHeight: 1.08,
          letterSpacing: numero ? '-0.03em' : '-0.045em',
          marginTop: numero ? 24 : 0,
          maxWidth: 1000,
        },
        titolo,
      ),
    ),
    h(
      'div',
      { display: 'flex', alignItems: 'center', gap: 16 },
      h('div', { width: 18, height: 18, background: C.accent }),
      h('div', { fontWeight: 600, fontSize: 30 }, PERSONA.nome),
      h('div', { ...label, fontSize: 24, letterSpacing: '0.02em', color: C.secondary }, PERSONA.firma),
    ),
  );

  const svg = await satori(tree as unknown as Parameters<typeof satori>[0], { width: 1200, height: 630, fonts });
  return new Resvg(svg, { fitTo: { mode: 'width', value: 1200 } }).render().asPng();
}
