/**
 * Configurazione unica del sito.
 * Per passare a un dominio proprio basta cambiare SITE_URL (vedi README).
 */
export const SITE_URL = 'https://elvioleonardi.netlify.app';

/** Mostra Google Ads come quarta colonna in "Cosa faccio". */
export const SHOW_ADS = false;

export const PERSONA = {
  nome: 'Elvio Leonardi',
  ruolo: 'SEO & AI Search Specialist',
  firma: 'SEO · AI Search',
  citta: 'Palermo',
  email: 'elvio@seoperstartup.it',
  linkedin: 'https://www.linkedin.com/in/elvio-leonardi/',
  /** Canale YouTube "Linea di fondo". Vuoto = non mostrato e non in sameAs. */
  youtube: '',
} as const;

/** Partita IVA mostrata nel footer. Vuota = non mostrata. */
export const PARTITA_IVA = '';

/**
 * Analytics: nessuno per ora.
 * Per attivare GoatCounter (gratuito, senza cookie) imposta il codice,
 * es. 'elvioleonardi', e aggiorna la CSP in netlify.toml (vedi README).
 */
export const GOATCOUNTER_CODE = '';

export const SITE_NAME = PERSONA.nome;
export const LOCALE = 'it-IT';

/** URL assoluto a partire da un percorso interno. */
export function abs(path: string): string {
  return new URL(path, SITE_URL).href;
}
