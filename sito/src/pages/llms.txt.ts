import type { APIRoute } from 'astro';
import { PERSONA, abs } from '../config';
import { brand, profilo, serviziVisibili } from '../data/profilo';
import { getCasiPubblicati, tipi, urlCaso } from '../lib/casi';

/** llms.txt (llmstxt.org). Si rigenera a ogni build: un nuovo caso compare da solo. */
export const GET: APIRoute = async () => {
  const casi = await getCasiPubblicati();
  const testo = [
    `# ${PERSONA.nome}`,
    '',
    `> ${PERSONA.ruolo} freelance a ${PERSONA.citta}. ${profilo.apertura} ${profilo.paragrafi[1]}`,
    '',
    `Brand su cui ha lavorato: ${brand.join(', ')}.`,
    `Contatti: ${PERSONA.email} · ${PERSONA.linkedin}`,
    '',
    '## Servizi',
    '',
    ...serviziVisibili.map((s) => `- ${s.titolo}: ${s.testo}`),
    '',
    '## Casi studio',
    '',
    ...casi.map(
      (c) =>
        `- [${c.data.titolo}](${abs(urlCaso(c))}): ${tipi(c).join(', ')} · ${c.data.settore}. ${c.data.sintesi}`,
    ),
    '',
    '## Profilo',
    '',
    `- [Chi sono](${abs('/chi-sono/')}): percorso professionale, strumenti, docenza.`,
    `- [Indice dei casi studio](${abs('/casi-studio/')})`,
    '',
  ];
  return new Response(testo.join('\n'), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};
