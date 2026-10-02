import type { APIRoute } from 'astro';
import { PERSONA } from '../../config';
import { getCasiPubblicati, protagonista, tipi } from '../../lib/casi';
import { ogPng, type OgInput } from '../../lib/og';

export async function getStaticPaths() {
  const casi = await getCasiPubblicati();
  const pagine: { path: string; og: OgInput }[] = [
    { path: 'home', og: { eyebrow: PERSONA.ruolo, titolo: PERSONA.nome } },
    {
      path: 'casi-studio',
      og: { eyebrow: 'Casi studio', titolo: 'Casi studio SEO e AI Search, con numeri veri' },
    },
    { path: 'chi-sono', og: { eyebrow: 'Chi sono', titolo: `${PERSONA.nome}, ${PERSONA.ruolo}` } },
    ...casi.map((c) => ({
      path: `casi-studio/${c.id}`,
      og: {
        eyebrow: `Caso studio · ${tipi(c).join(' · ')}`,
        numero: protagonista(c),
        titolo: c.data.titolo,
      },
    })),
  ];
  return pagine.map((p) => ({ params: { path: p.path }, props: { ...p.og } }));
}

export const GET: APIRoute = async ({ props }) => {
  const png = await ogPng(props as OgInput);
  return new Response(new Uint8Array(png), { headers: { 'Content-Type': 'image/png' } });
};
