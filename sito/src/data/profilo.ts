import { SHOW_ADS } from '../config';

/** Testo profilo (Chi sono). Le leve sono rese come lista con →. */
export const profilo = {
  apertura: 'Lavoro sulla Search dal 2020.',
  paragrafi: [
    'In questi anni ho lavorato su progetti per grandi brand internazionali come Durex, Liu Jo, Pandora, Unicef e altri.',
    'Oggi lavoro come freelance su SEO, AI Search e Google Ads, aiutando aziende e brand a trasformare la domanda che intercettano sui motori di ricerca in traffico qualificato, lead, prenotazioni e vendite.',
    'Il mio approccio parte da una domanda semplice: come possiamo fare in modo che il tuo brand venga trovato dalle persone giuste, nel momento in cui stanno cercando ciò che offri?',
  ],
  introLeve: 'Per farlo lavoro su tre leve:',
  leve: [
    { nome: 'SEO', testo: 'per costruire visibilità organica e intercettare domanda qualificata.' },
    {
      nome: 'AI Search',
      testo:
        "per aumentare la presenza del brand nelle risposte generate dai motori di ricerca basati sull'AI.",
    },
    {
      nome: 'Google Ads',
      testo: "per intercettare la domanda con campagne paid orientate all'acquisizione.",
    },
  ],
  chiusura: "Uso questi canali insieme, dentro un'unica strategia di Search Acquisition.",
  personale:
    'Fuori dal lavoro ho un canale YouTube, Linea di fondo, dove parlo del calcio nei posti in cui nessuno penserebbe al calcio: Corea del Nord, Afghanistan, Turkmenistan e così via.',
};

/** Versione breve per la home. */
export const profiloBreve =
  'Aiuto aziende e brand a trasformare la domanda che intercettano sui motori di ricerca in traffico qualificato, lead, prenotazioni e vendite.';

export const percorso = [
  {
    periodo: '2025 → oggi',
    ruolo: 'SEO & AI Search Specialist · Palermo',
    org: 'Freelance',
  },
  {
    periodo: '2026 → oggi',
    ruolo: 'SEO & AI Search Specialist',
    org: 'RankWit AI',
    dettaglio: 'Strategie GEO per hotel in tutta Italia.',
  },
  {
    periodo: '2025 → oggi',
    ruolo: 'SEO Specialist freelance',
    org: 'Intarget',
  },
  {
    periodo: '2026',
    ruolo: 'Docente',
    org: 'Confesercenti Sicilia',
    dettaglio: 'Due lezioni su SEO e GEO nel corso AI & Digital Marketing.',
  },
  {
    periodo: '2024 → 2025',
    ruolo: 'Marketing Specialist',
    org: 'Ruralis.com',
    dettaglio: 'Affitti brevi.',
  },
  {
    periodo: '2022 → 2024',
    ruolo: 'SEO Consultant',
    org: 'dentsu, Milano',
    dettaglio:
      'E-commerce (Liu Jo, Pandora, Arper), pharma (Durex, Benagol, Gaviscon, Nurofen, Swisse), Amazon SEO, link building internazionale.',
  },
  {
    periodo: '2022',
    ruolo: 'SEO & Content Marketing Specialist',
    org: 'Minicar Store',
  },
  {
    periodo: '2020 → 2022',
    ruolo: 'Content Marketing Specialist',
    org: 'Sicilì Food',
  },
];

export const formazione = [
  { titolo: 'Economia e Management', org: 'Università di Parma' },
  { titolo: 'Master in Digital Marketing', org: 'start2impact' },
];

export const strumenti = [
  'Screaming Frog',
  'Google Search Console',
  'GA4',
  'Python / pandas',
  'Dati strutturati',
  'hreflang',
];

export const brand = ['Durex', 'Liu Jo', 'Pandora', 'Arper', 'Nurofen', 'Gaviscon', 'Unicef'];

export const docenza = {
  org: 'Confesercenti Sicilia',
  anno: '2026',
  testo: 'Due lezioni su SEO e GEO nel corso AI & Digital Marketing.',
};

/** Colonne di "Cosa faccio". Google Ads compare solo con SHOW_ADS = true. */
const servizi = [
  {
    titolo: 'SEO tecnica',
    testo: 'Per costruire visibilità organica e intercettare domanda qualificata.',
    punti: [
      'Audit con Screaming Frog e Search Console',
      'Dati strutturati',
      'hreflang e SEO internazionale',
      'Ottimizzazioni sulle pagine esistenti',
    ],
  },
  {
    titolo: 'AI Search / GEO',
    testo:
      "Per aumentare la presenza del brand nelle risposte generate dai motori di ricerca basati sull'AI.",
    punti: [
      'Strategie GEO',
      'Impression nelle funzionalità AI di Google',
      'ChatGPT, Perplexity, Gemini, AI Overviews',
    ],
    protagonista: true,
  },
  {
    titolo: 'Contenuti',
    testo: 'Produzione editoriale, aggiornamento dei contenuti esistenti e internal linking.',
    punti: [
      'Ottimizzazione delle pagine commerciali',
      'Nuovi contenuti di supporto',
      'Individuazione di nuovi topic',
    ],
  },
  {
    titolo: 'Google Ads',
    testo: "Per intercettare la domanda con campagne paid orientate all'acquisizione.",
    punti: [],
    ads: true,
  },
];

export const serviziVisibili = servizi.filter((s) => SHOW_ADS || !s.ads);

/** knowsAbout del JSON-LD Person. */
export const competenze = [
  'SEO',
  'Generative Engine Optimization',
  'AI Search',
  'SEO tecnica',
  'SEO internazionale',
  'Google Ads',
];
