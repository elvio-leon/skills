# elvioleonardi.netlify.app

Sito personale di Elvio Leonardi, SEO & AI Search Specialist.
Astro 7, output statico, zero JavaScript lato client, design system Leonardi Editorial.
Costo: 0 €. Tutte le dipendenze sono open source e i font (Geist, Geist Mono) hanno licenza SIL OFL 1.1.

## Comandi

Serve Node 22.12 o superiore (`.nvmrc`).

```bash
npm install        # installa le dipendenze
npm run dev        # sviluppo su http://localhost:4321 (i casi in bozza sono visibili)
npm run build      # build in dist/ + elenco dei segnaposto [DA SCRIVERE] rimasti
npm run preview    # serve dist/ in locale
```

## Struttura

```
src/
├── config.ts             SITE_URL, SHOW_ADS, contatti, P. IVA, analytics
├── content.config.ts     schema Zod dei casi studio
├── content/casi/         un file .md (o .mdx) per caso; il nome del file è lo slug
├── data/profilo.ts       testi di profilo, percorso, strumenti, brand, servizi
├── styles/               token (Paper/Ink, scala, spazi) e CSS globale
├── layouts/Base.astro    <head> SEO, JSON-LD, header, footer con firma
├── components/           Rail, Section, Firma, FrameworkColumns, Process, DataCard,
│                         BarChart, Comparison, Quote, Timeline, CaseRow, Contatto…
├── lib/                  formattazione numeri it-IT, casi, JSON-LD, immagini OG
└── pages/                home, casi-studio, chi-sono, 404, og/*.png, robots.txt, llms.txt
public/
├── fonts/                woff2 self-hosted (subset latino)
├── casi/                 PDF dei casi (opzionali)
└── favicon.svg / .ico, apple-touch-icon.png
scripts/
├── placeholder-report.mjs  elenca i [DA SCRIVERE] a fine build
└── genera-icone.mjs        rigenera .ico e apple-touch-icon da favicon.svg
```

## Aggiungere un caso studio

1. Copia `src/content/casi/caso-2.md` in un nuovo file, per esempio `src/content/casi/ecommerce-moda-hreflang.md`.
   Il nome del file diventa l'URL: `/casi-studio/ecommerce-moda-hreflang/`.
   Mai il nome del cliente nel nome del file, nel testo, negli alt o nei metadati.
2. Compila il frontmatter. Lo schema in `src/content.config.ts` blocca il build se manca qualcosa di obbligatorio:
   - `ruolo` (descrizione, team, durata): senza, il caso non compila.
   - `fonte`, `periodo_prima`, `periodo_dopo`: obbligatori, compaiono come caption sotto ogni dato.
   - `meta_title` max 60 caratteri, `meta_description` fra 140 e 155, `sintesi` di 2-3 frasi.
   - Ogni grafico ha esattamente una barra con `protagonista: true` e valori ≥ 0.
   - Se un KPI ha `confronto: { prima, dopo }`, il `valore` deve tornare con i dati (es. 397920 → 471468 = +18,5).
   - I numeri si scrivono grezzi (`471468`, `18.5`): la formattazione italiana (471.468 · 18,5%) è automatica.
   - `==parola==` in `obiettivo` e `insight` diventa il marker giallo (1-4 parole).
3. Scrivi il **Contesto** nel corpo del file (Markdown sotto il frontmatter).
4. Lascia `draft: true` finché non è pronto: il caso è visibile solo con `npm run dev`.
   Toglilo per pubblicarlo: pagina, indice, home, sitemap, immagine OG e `llms.txt` si aggiornano da soli.
5. PDF opzionale: metti il file in `public/casi/nome-file.pdf` e aggiungi `pdf: /casi/nome-file.pdf`.
6. `npm run build`: se lo schema non è rispettato il build si ferma e dice quale campo correggere;
   a fine build trovi l'elenco dei `[DA SCRIVERE]` ancora presenti.

## Pubblicare il codice su GitHub

Il sito è stato sviluppato nella cartella `sito/` del repository `elvio-leon/skills`
(branch `claude/nifty-edison-66c4t4`). Per spostarlo in un repository privato dedicato, con la sua storia:

1. Su GitHub crea un repository **privato e vuoto** (senza README, .gitignore o licenza),
   per esempio `elvio-leon/elvioleonardi-sito`. In alternativa, con la GitHub CLI:
   `gh repo create elvio-leon/elvioleonardi-sito --private`
2. Dal tuo computer:

```bash
git clone https://github.com/elvio-leon/skills.git
cd skills
git checkout claude/nifty-edison-66c4t4
git subtree split --prefix=sito -b sito-main
git push https://github.com/elvio-leon/elvioleonardi-sito.git sito-main:main
```

3. Da qui in poi lavora nel nuovo repository:

```bash
cd ..
git clone https://github.com/elvio-leon/elvioleonardi-sito.git
cd elvioleonardi-sito
npm install
npm run dev
```

## Deploy su Netlify (piano gratuito)

Il file `netlify.toml` contiene già comando di build (`npm run build`), cartella di output (`dist`),
Node 22, header di sicurezza e di cache e la regola per la 404.

1. Accedi a [app.netlify.com](https://app.netlify.com) (piano Free, nessuna carta richiesta).
2. **Add new project → Import an existing project → GitHub**. Autorizza Netlify e concedi l'accesso
   solo al repository `elvioleonardi-sito`.
3. Scegli il repository. Branch di produzione: `main`. Lascia vuoti i campi di build:
   Netlify legge tutto da `netlify.toml`. Clicca **Deploy**.
   (Se invece colleghi direttamente `elvio-leon/skills`, imposta **Base directory** = `sito`.)
4. **Project configuration → Change project name** → `elvioleonardi`.
   Il sito risponde su `https://elvioleonardi.netlify.app`, cioè il valore di `SITE_URL`.
5. Deploy continuo: ogni push su `main` pubblica il sito.
   Deploy preview: in **Project configuration → Build & deploy → Continuous deployment → Deploy Previews**
   verifica che sia attivo "Any pull request against your production branch"
   (è l'impostazione predefinita). Ogni pull request riceve un URL di anteprima.
6. Non attivare Netlify Analytics (è a pagamento) né i form di Netlify.

Dopo il primo deploy: aggiungi la proprietà in Google Search Console e invia
`https://elvioleonardi.netlify.app/sitemap-index.xml`.

## Passare a un dominio proprio

Netlify non costa nulla anche con un dominio proprio; il dominio si acquista dal registrar che preferisci.

1. In `src/config.ts` cambia una riga: `export const SITE_URL = 'https://www.tuodominio.it';`
   Canonical, sitemap, robots.txt, llms.txt, JSON-LD e Open Graph si aggiornano al prossimo build.
2. Commit e push su `main`.
3. Su Netlify: **Domain management → Add a domain** → inserisci il dominio.
4. DNS: usa Netlify DNS (cambia i nameserver dal registrar con quelli indicati) oppure,
   con DNS esterno, un record `CNAME` per `www` verso `elvioleonardi.netlify.app`
   e il record `A` per il dominio nudo verso l'IP del load balancer indicato da Netlify.
5. HTTPS: Netlify emette il certificato Let's Encrypt (gratuito) in automatico.
   Imposta il dominio come **primary domain**: il sottodominio `netlify.app` reindirizza lì.
6. In Search Console aggiungi la nuova proprietà e invia di nuovo la sitemap.

## Analytics (opzionale, gratuito, senza cookie)

Oggi il sito non ha analytics e quindi niente cookie banner. Per attivare GoatCounter:

1. Crea un account gratuito su goatcounter.com con un codice, per esempio `elvioleonardi`.
2. In `src/config.ts` imposta `GOATCOUNTER_CODE = 'elvioleonardi'`.
   Lo script viene inserito da `src/components/Analytics.astro`, punto unico nel layout.
3. In `netlify.toml` aggiorna la `Content-Security-Policy`: aggiungi `https://gc.zgo.at` a `script-src`
   e `https://elvioleonardi.goatcounter.com` a `connect-src` e `img-src`.

## Altre impostazioni in `src/config.ts`

- `SHOW_ADS`: `true` aggiunge Google Ads come quarta colonna in "Cosa faccio".
- `PERSONA.youtube`: URL del canale "Linea di fondo". Se valorizzato compare in Chi sono, nel footer e in `sameAs` del JSON-LD.
- `PARTITA_IVA`: se valorizzata compare nel footer.

## Font e icone

I woff2 in `public/fonts/` e i TTF in `src/assets/og-fonts/` (usati per le immagini OG) sono subset latini
dei file ufficiali del pacchetto npm `geist`, generati con `pyftsubset` (fonttools).
Peso totale dei tre woff2: circa 50 KB. Licenza in `public/fonts/OFL.txt`.

## Verifiche fatte

- HTML valido: W3C Nu validator (vnu) e html-validate, zero errori.
- Nessun link interno rotto e nessun redirect interno (tutti gli URL con slash finale).
- Lighthouse mobile: 100 su Performance, Accessibilità, Best Practices e SEO su tutte le pagine.
- Nessuno scroll orizzontale a 360 px.
- `astro check`: zero errori.
