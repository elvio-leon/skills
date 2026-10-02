import { getCollection, type CollectionEntry } from 'astro:content';
import { formatta } from './format';

export type Caso = CollectionEntry<'casi'>;

/**
 * Unico punto da cui le pagine leggono i casi.
 * I draft sono esclusi dal build (quindi da pagine, sitemap, indice, OG e llms.txt);
 * in `astro dev` restano visibili per l'anteprima.
 */
export async function getCasiPubblicati(): Promise<Caso[]> {
  const casi = await getCollection('casi', ({ data }) => import.meta.env.DEV || !data.draft);
  return casi.sort(
    (a, b) => b.data.data_pubblicazione.getTime() - a.data.data_pubblicazione.getTime(),
  );
}

export function urlCaso(caso: Caso): string {
  return `/casi-studio/${caso.id}/`;
}

export function ogCaso(caso: Caso): string {
  return `/og/casi-studio/${caso.id}.png`;
}

/** Il numero protagonista, già formattato. */
export function protagonista(caso: Caso): string {
  const k = caso.data.kpi_principale;
  return formatta(k.valore, k.formato, k.decimali);
}

export function tipi(caso: Caso): string[] {
  return [caso.data.tipo, ...caso.data.ambiti.filter((a) => a !== caso.data.tipo)];
}

export function slugTipo(tipo: string): string {
  return tipo.toLowerCase().replace(/\s+/g, '-');
}

/** Caso successivo in ordine di data, ciclico. Null se c'è un solo caso. */
export function successivo(casi: Caso[], corrente: Caso): Caso | null {
  if (casi.length < 2) return null;
  const i = casi.findIndex((c) => c.id === corrente.id);
  return casi[(i + 1) % casi.length];
}
