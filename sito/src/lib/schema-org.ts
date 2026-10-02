import { PERSONA, SITE_URL, abs } from '../config';
import { competenze, formazione } from '../data/profilo';
import { senzaMarker } from './format';
import { ogCaso, urlCaso, type Caso } from './casi';

export const PERSON_ID = abs('/#person');
export const WEBSITE_ID = abs('/#website');

export function person(): Record<string, unknown> {
  return {
    '@type': 'Person',
    '@id': PERSON_ID,
    name: PERSONA.nome,
    jobTitle: PERSONA.ruolo,
    url: abs('/'),
    email: `mailto:${PERSONA.email}`,
    image: abs('/og/home.png'),
    sameAs: [PERSONA.linkedin, PERSONA.youtube].filter(Boolean),
    knowsAbout: competenze,
    address: {
      '@type': 'PostalAddress',
      addressLocality: PERSONA.citta,
      addressCountry: 'IT',
    },
    alumniOf: formazione.map((f) => ({ '@type': 'EducationalOrganization', name: f.org })),
  };
}

export function website(): Record<string, unknown> {
  return {
    '@type': 'WebSite',
    '@id': WEBSITE_ID,
    url: abs('/'),
    name: PERSONA.nome,
    description: `${PERSONA.ruolo}. Casi studio di SEO e AI Search.`,
    inLanguage: 'it-IT',
    publisher: { '@id': PERSON_ID },
  };
}

export function graph(...nodes: Record<string, unknown>[]): Record<string, unknown> {
  return { '@context': 'https://schema.org', '@graph': nodes };
}

export function breadcrumb(items: { name: string; path: string }[]): Record<string, unknown> {
  return {
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      item: abs(it.path),
    })),
  };
}

export function profilePage(path: string, title: string, description: string) {
  return {
    '@type': 'ProfilePage',
    '@id': abs(`${path}#profilepage`),
    url: abs(path),
    name: title,
    description,
    inLanguage: 'it-IT',
    isPartOf: { '@id': WEBSITE_ID },
    mainEntity: { '@id': PERSON_ID },
  };
}

export function article(caso: Caso): Record<string, unknown> {
  const d = caso.data;
  const url = abs(urlCaso(caso));
  return {
    '@type': 'Article',
    '@id': `${url}#article`,
    headline: d.titolo,
    description: d.meta_description,
    abstract: senzaMarker(d.sintesi),
    url,
    mainEntityOfPage: url,
    image: abs(ogCaso(caso)),
    inLanguage: 'it-IT',
    datePublished: d.data_pubblicazione.toISOString(),
    dateModified: (d.data_modifica ?? d.data_pubblicazione).toISOString(),
    author: { '@id': PERSON_ID },
    publisher: { '@id': PERSON_ID },
    isPartOf: { '@id': WEBSITE_ID },
    articleSection: 'Casi studio',
    about: [
      ...[d.tipo, ...d.ambiti].map((t) => ({
        '@type': 'Thing',
        name: t === 'AI Search' ? 'AI Search (Generative Engine Optimization)' : t,
      })),
      { '@type': 'Thing', name: d.settore },
    ],
  };
}

export { SITE_URL };
