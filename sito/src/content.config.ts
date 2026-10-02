import { defineCollection } from 'astro:content';
import { glob } from 'astro/loaders';
import { z } from 'astro/zod';
import { arrotonda, delta } from './lib/format';

/**
 * Casi studio. Ogni file in src/content/casi/ è un caso; il nome del file è lo slug.
 * Regola d'oro: il cliente è anonimo. Mai il suo nome in testo, slug, file o metadati.
 */

const Formato = z.enum(['numero', 'percentuale', 'delta-numero', 'delta-percentuale']);

const Kpi = z
  .object({
    label: z.string().min(1),
    /** Il numero mostrato. Per i delta in percentuale: 18.5 → "+18,5%". */
    valore: z.number(),
    formato: Formato,
    decimali: z.number().int().min(0).max(2).optional(),
    /** Unità mostrata dopo il numero: "clic", "milioni di impression". */
    unita: z.string().optional(),
    /** Valori di partenza e arrivo, mostrati come "397.920 → 471.468". */
    confronto: z.object({ prima: z.number(), dopo: z.number() }).optional(),
  })
  .refine(
    (k) => {
      // Se c'è il confronto, il delta dichiarato deve tornare con i dati.
      if (!k.confronto) return true;
      const { prima, dopo } = k.confronto;
      if (k.formato === 'delta-percentuale') {
        const d = k.decimali ?? 1;
        return arrotonda(delta(prima, dopo), d) === arrotonda(k.valore, d);
      }
      if (k.formato === 'delta-numero') return dopo - prima === k.valore;
      return true;
    },
    { message: 'Il valore del KPI non corrisponde al confronto prima → dopo' },
  );

/** Fonte e periodo: obbligatori a livello di caso, sovrascrivibili per blocco. */
const FonteOverride = z.object({
  fonte: z.string().min(1).optional(),
  periodo_prima: z.string().min(1).optional(),
  periodo_dopo: z.string().min(1).optional(),
  /** Periodo unico, per dati senza confronto (es. "18 mag → 28 set 2026"). */
  periodo: z.string().min(1).optional(),
});

const Grafico = z
  .object({
    titolo: z.string().min(1),
    formato: Formato,
    decimali: z.number().int().min(0).max(2).optional(),
    barre: z
      .array(
        z.object({
          label: z.string().min(1),
          // Scala da 0: niente valori negativi.
          valore: z.number().nonnegative(),
          protagonista: z.boolean().default(false),
        }),
      )
      .min(2),
  })
  .extend(FonteOverride.shape)
  .refine((g) => g.barre.filter((b) => b.protagonista).length === 1, {
    message: 'Ogni grafico ha esattamente una barra protagonista (in accento)',
  });

const Approfondimento = z
  .object({
    /** Dove compare nella pagina: dopo le leve o dopo i risultati. */
    posizione: z.enum(['leve', 'risultati']).default('risultati'),
    eyebrow: z.string().min(1),
    titolo: z.string().min(1),
    testo: z.string().optional(),
    punti: z.array(z.string().min(1)).optional(),
    kpi: Kpi.optional(),
    grafico: Grafico.optional(),
  })
  .extend(FonteOverride.shape);

const Tipo = z.enum(['SEO', 'AI Search']);

const casi = defineCollection({
  loader: glob({ pattern: '**/*.{md,mdx}', base: './src/content/casi' }),
  schema: z.object({
    draft: z.boolean().default(false),
    /** Mostrato nella home fra i casi in evidenza. */
    in_evidenza: z.boolean().default(true),
    data_pubblicazione: z.coerce.date(),
    data_modifica: z.coerce.date().optional(),

    // Header
    tipo: Tipo,
    /** Ambiti secondari trattati nel caso (es. una sezione AI Search). */
    ambiti: z.array(Tipo).default([]),
    titolo: z.string().min(1),
    settore: z.string().min(1),
    periodo: z.string().min(1),
    /** Una riga di contesto per home e indice. */
    estratto: z.string().min(1).max(120),

    // SEO
    meta_title: z.string().min(1).max(60),
    meta_description: z.string().min(140).max(155),
    /** 2-3 frasi autosufficienti: chi, cosa, risultato con numero, periodo. */
    sintesi: z.string().min(150).max(450),

    // Racconto (il Contesto è il corpo Markdown del file)
    obiettivo: z.string().min(1),
    ruolo: z.object({
      descrizione: z.string().min(1),
      team: z.string().min(1),
      durata: z.string().min(1),
    }),
    leve: z.array(z.object({ titolo: z.string().min(1), testo: z.string().min(1) })).min(1),

    // Risultati: fonte e periodi obbligatori
    fonte: z.string().min(1),
    periodo_prima: z.string().min(1),
    periodo_dopo: z.string().min(1),
    kpi_principale: Kpi,
    kpi_secondari: z.array(Kpi).default([]),
    grafici: z.array(Grafico).default([]),
    approfondimenti: z.array(Approfondimento).default([]),

    // Chiusura
    insight: z.string().min(1),
    sequenza: z.array(z.string().min(1)).optional(),
    pdf: z
      .string()
      .regex(/^\/casi\/[a-z0-9-]+\.pdf$/, 'Il PDF va in public/casi/ con nome in minuscolo')
      .optional(),
  }),
});

export const collections = { casi };
