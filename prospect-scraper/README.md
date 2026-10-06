# Prospect Scraper

Tool locale per trovare aziende appartenenti a un ICP e raccogliere le informazioni
pubbliche dai loro siti web: email, telefoni, social, indirizzo, città, P.IVA.
Risultati in tabella (ordinabile, filtrabile, con selezione righe) ed export CSV/XLSX.

Niente AI, scoring, audit SEO, CRM o automazioni: è un MVP volutamente semplice.

## Installazione su Mac (consigliata)

1. Scarica **ProspectScraper.dmg** dalla pagina
   [Release "prospect-scraper-latest"](https://github.com/elvio-leon/skills/releases/tag/prospect-scraper-latest).
2. Apri il file `.dmg` e trascina **Prospect Scraper** nella cartella **Applicazioni**.
3. Apri Prospect Scraper da Applicazioni o dal Launchpad. Non serve installare Python o altro.
4. Solo la prima volta macOS lo blocca, perché l'app non è firmata da uno sviluppatore Apple
   registrato: vai in **Impostazioni di Sistema → Privacy e sicurezza**, scorri in basso e
   premi **Apri comunque**.

L'app si apre in una sua finestra. **Chiudendo la finestra si chiude tutto.** Gli export
(CSV/Excel) vengono salvati direttamente nella cartella **Download**; la prima volta macOS
chiede il permesso di accedervi. Dati e ricerche restano in
`~/Library/Application Support/Prospect Scraper`, quindi sopravvivono agli aggiornamenti dell'app.

Per aggiornare: scarica il nuovo `.dmg` e sostituisci l'app in Applicazioni.

L'app è per Mac con processore Apple (M1 o successivi).

## Windows e Linux (da sorgente, senza terminale)

**Serve Python 3.11 o superiore**, da [python.org/downloads](https://www.python.org/downloads/).
Su Windows spunta **"Add python.exe to PATH"** durante l'installazione. Poi doppio clic su:

| Sistema | File |
|---|---|
| Windows | `Avvia Prospect Scraper (Windows).bat` |
| Linux | `avvia-prospect-scraper-linux.sh` |

- **Il primo avvio** prepara l'app da solo (1-3 minuti, serve Internet). Quelli successivi
  durano pochi secondi.
- L'app si apre in una **finestra dedicata** (Edge o Chrome in "modalità app"); se nessuno
  dei due è installato, si apre nel browser predefinito.
- Per spegnerla: pulsante **Chiudi app** in fondo alla barra laterale.
- I file esportati finiscono nella cartella **Download**.

Suggerimento: crea un collegamento sul desktop (Windows: tasto destro sul file → *Invia a →
Desktop (crea collegamento)*).

Facoltativo e avanzato, per leggere i siti che mostrano i contenuti solo via JavaScript
(da terminale, una sola volta):
`.venv/bin/python -m pip install playwright && .venv/bin/python -m playwright install chromium`
(Windows: `.venv\Scripts\python -m ...`).

<details><summary>Avvio da terminale (alternativa)</summary>

```bash
cd prospect-scraper
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```
</details>

Da sorgente il database è in `data/prospects.db` (tutte le ricerche restano salvate tra una
sessione e l'altra), i log in `logs/`.

## Come si usa

1. **Tipo di ricerca**: Hospitality, Editoriale, Digital / Startup o Custom (determina le fonti predefinite).
2. **Keyword**: es. `hotel 4 stelle Palermo`, `boutique hotel`, `magazine tecnologia`, `ecommerce arredamento`.
3. **Località**: es. `Sicilia`, `Milano`, `Italia` (default: Italia). Se la keyword contiene
   una città ("hotel Palermo") viene usata quella, perché è più specifica.
4. **Numero risultati** e **Modalità**:
   - *Search*: solo ricerca;
   - *Website enrichment*: arricchisce gli URL incollati (uno per riga) oppure, se il campo
     è vuoto, i prospect già nel database non ancora arricchiti;
   - *Search + enrichment* (default).
5. **CERCA PROSPECT**. Nella tabella puoi cercare, filtrare, ordinare (clic sull'intestazione)
   e selezionare righe.

### Export

Sopra la tabella ci sono **DOWNLOAD CSV** e **DOWNLOAD XLSX**: esportano le righe selezionate
oppure, se non ne selezioni, tutte quelle visibili con i filtri applicati. Il file include
tutte le colonne (anche P.IVA, tutte le email, tutti i telefoni, indirizzo, URL della fonte...)
e prende il nome dalla ricerca, es. `hotel-4-stelle-palermo-20260929-1305.xlsx`.

Tre viste, scelte con i pulsanti sopra la tabella:

- **Ultima ricerca**: i risultati dell'ultima ricerca (anche dopo aver riaperto l'app);
- **Ricerche salvate**: scegli una qualsiasi ricerca fatta in passato e la esporti. Con
  **Prepara export di tutte le ricerche** ottieni un unico Excel con **un foglio per ricerca**;
- **Tutto il database**: tutti i prospect trovati finora, senza duplicati.

## Fonti di ricerca

Nessuno scraping di Google o LinkedIn. Solo fonti con accesso consentito e gratuito:

| Fonte | Quando | Note |
|---|---|---|
| **OpenStreetMap** (Nominatim + Overpass) | Hospitality, attività locali, negozi, uffici | Dati strutturati: sito, telefono, email, indirizzo. La keyword viene tradotta in tag OSM (`hotel` → `tourism=hotel`, `4 stelle` → `stars=4`, `arredamento` → `shop=furniture`, `software` → `office=it`...). |
| **Wikidata** (API MediaWiki) | Editoriale, software house, aziende note | Solo elementi con sito ufficiale e non cessati. |
| **SearXNG** (opzionale) | Ricerca web generica ("SaaS Italia") | Serve una tua istanza SearXNG locale. |

Per attivare SearXNG:

```bash
docker run -d -p 8888:8080 searxng/searxng
# nel file settings.yml dell'istanza abilita il formato JSON:
#   search:
#     formats: [html, json]
export PS_SEARXNG_URL=http://localhost:8888
streamlit run app.py
```

Nuove fonti: crea una sottoclasse di `SearchProvider` in `scrapers/search/` e registrala
in `PROVIDERS` (`scrapers/search/__init__.py`). Interfaccia:

```python
from scrapers.search import search
search("hotel 4 stelle", 20, location="Palermo", category="Hospitality")
# -> [{"title": ..., "url": ..., "snippet": ..., "source": ..., "extra": {...}}, ...]
```

## Web Search (aziende digitali)

La ricerca locale (OpenStreetMap + Wikidata) trova attività con una sede fisica. Per **startup,
SaaS, e-commerce e publisher** online serve la **Web Search**: nella barra laterale scegli
**Fonte → Web Search**. È un modo di ricerca indipendente: la ricerca locale resta com'è.

Flusso: **ricerca web (API) → domini aziendali → deduplicazione per dominio → enrichment dei siti → CSV/XLSX**.
Portali, directory, social, siti di recensioni e marketplace vengono scartati; più risultati dello
stesso sito (`www.`, sottodomini, pagine diverse) diventano un solo prospect.

**Configurazione (una volta sola, nell'app):**

1. crea un account gratuito su https://app.tavily.com (1000 ricerche al mese, senza carta di credito);
2. nella barra laterale apri **Impostazioni Web Search**, incolla la chiave API e premi **Salva**.

La chiave è salvata solo sul tuo computer (`user_settings.json` nella cartella dei dati, permessi
`0600`) e non compare mai in log, messaggi o export. In alternativa: variabili d'ambiente
`PS_TAVILY_API_KEY`, `PS_BRAVE_API_KEY`, `PS_SEARXNG_URL`, `PS_WEB_PROVIDER`.

| Provider | Costo | Note |
|---|---|---|
| **Tavily** (predefinito) | 1000 ricerche/mese gratis, **nessuna carta** | Fino a 20 risultati per chiamata, senza paginazione (altri risultati con varianti della query). |
| **Brave Search** | 5$/mese di credito (≈1000 ricerche), **carta richiesta** | https://api-dashboard.search.brave.com. Fino a 20 risultati per chiamata, con paginazione. |
| **SearXNG** | Gratuito, ma serve Docker e un'istanza propria | Interroga a sua volta motori come Google/Bing. Per utenti tecnici. |

**Costo di una ricerca:** ogni chiamata API costa 1 credito. Una ricerca da 20 risultati usa in
genere 1-3 chiamate; il massimo è `WEB_MAX_API_CALLS` (5, `PS_WEB_MAX_API_CALLS`). L'app mostra
quante ricerche API sono state fatte ("N ricerche API").

**Limiti:** tra i risultati possono esserci blog, articoli e classifiche ("i 10 migliori SaaS") che
non sono il sito di un'azienda; nessuna qualificazione dei prospect (settore, dimensione, fit) per ora.
Città, paese, email e telefono arrivano solo dall'enrichment del sito (se attivo).

Nuovi provider: vedi la docstring di `scrapers/web_search/__init__.py`.

## Agenzie (qualifica con AI)

Pensata per trovare **agenzie italiane di marketing e web** a cui proporre servizi SEO / AI search in
white label, e dare a ciascuna un **punteggio da 0 a 100** (più alto = più adatta). Nella barra laterale
scegli **Fonte → Agenzie**. Le altre due fonti (Local e Web Search) non cambiano.

Flusso: **ricerca web → blacklist → contatti dal sito → pagine servizi / chi siamo / portfolio → AI → score**.

1. la Web Search trova i siti (serve la chiave Tavily/Brave, vedi sopra);
2. la **blacklist** scarta directory, classifiche e portali ("le migliori agenzie…", clutch.co, ecc.)
   *prima* di contare i risultati: la ricerca continua fino a raggiungere il numero richiesto;
3. l'enrichment legge home e pagine di contatto (email, telefono, social);
4. per ogni sito si leggono la home e al più **una pagina per gruppo** (servizi, chi siamo, portfolio),
   riusando i testi già scaricati; lo stato del **blog** si ricava in modo deterministico (feed RSS o
   pagina del blog: una sola richiesta, attivo se l'ultimo articolo ha meno di ~6 mesi);
5. l'AI compila una scheda (è un'agenzia? servizi, livello SEO, servizi ricorrenti, dimensione del team,
   verticali, una nota con un aggancio per il primo messaggio) con una citazione come prova;
6. lo **score** si calcola con pesi modificabili.

Rispetta `robots.txt` e le pause per host come il resto dell'app; **LinkedIn non viene mai visitato**.

**Modelli AI** (scegli in *Impostazioni Agenzie*; costi indicativi per agenzia, ~8000 token in ingresso):

| Modello | Costo per agenzia | Note |
|---|---|---|
| **Claude Haiku 4.5** (predefinito) | ≈ 0,01 $ | economico, ottimo per schede strutturate |
| **Claude Sonnet 5.5** | ≈ 0,03 $ | più accurato (conta anche il ragionamento: ~2000 token in uscita) |
| OpenAI GPT-5.4 mini | ≈ 0,01 $ | chiamate HTTP dirette |
| Google Gemini 2.5 Flash | ≈ 0,005 $ | chiamate HTTP dirette |

Le chiavi si ottengono su https://platform.claude.com/settings/keys, https://platform.openai.com/api-keys,
https://aistudio.google.com/apikey. Si inseriscono in **Impostazioni Agenzie → Chiave API → Salva**
(file `user_settings.json`, permessi `0600`, mai in log o export) oppure con le variabili
`PS_ANTHROPIC_API_KEY` / `ANTHROPIC_API_KEY`, `PS_OPENAI_API_KEY` / `OPENAI_API_KEY`,
`PS_GEMINI_API_KEY` / `GEMINI_API_KEY`, `PS_LLM_PROVIDER`, `PS_CLAUDE_MODEL`.
**I testi delle pagine del sito (max ~20.000 caratteri per agenzia) vengono inviati al provider scelto.**
Senza chiave la ricerca funziona comunque (solo scoperta e contatti) e l'app avvisa che la qualifica è saltata.

**Blacklist e pesi** si modificano in *Impostazioni Agenzie* (Blacklist, Pesi dello score) oppure direttamente
nei file della cartella dei dati: `agency_blacklist.txt` (sezioni `[domini]` e `[frasi]`; le frasi valgono per
titolo e percorso dell'URL) e `agency_scoring.toml` (tomllib). Alla prima volta vengono copiati dai valori
predefiniti in `config/`. Un file dei pesi non valido non viene salvato dall'app; se lo rompi a mano si usano
i pesi predefiniti e l'app lo segnala.

**Score** (somma, limitata tra 0 e 100; valori predefiniti):

| Segnale | Punti |
|---|---|
| SEO: assente / accennata / strutturata | 40 / 25 / 0 |
| Servizi ricorrenti (social, ADV, manutenzione, canoni): sì / no | 25 / 0 |
| Team: 1 / 2-5 / 6-20 / 20+ / non determinabile | 5 / 15 / 25 / 5 / 0 |
| Blog: assente / fermo / attivo / non determinabile | 10 / 10 / 0 / 0 |
| Agenzia: sì / dubbio (−20) / **no = esclusa**, senza score | 0 / −20 / – |

La tabella è ordinata per score decrescente; ci sono il filtro **Score minimo** e l'opzione **Mostra escluse**.
Le qualifiche fallite (sito non raggiungibile, errore dell'AI…) compaiono come "⚠️ failed" con il motivo in
*Error* ("qualifica: …"). L'export CSV/XLSX contiene tutte le colonne della scheda, le prove, i modelli e il costo.

**Limiti:** l'AI legge solo poche pagine e può sbagliare (controlla sempre la citazione di prova); i siti che
richiedono JavaScript hanno poco testo e danno più "dubbio"; la dimensione del team è spesso "non determinabile";
il blog si rileva solo se è linkato dalla home.

### Contatti dei decisori («Trova contatti»)

Nei risultati di una ricerca Agenzie (anche vecchia, da *Ricerche salvate*: nessuna nuova ricerca) il riquadro
**👤 Trova contatti dei decisori** lavora sulle righe spuntate (✓) oppure su tutte quelle con **score ≥ 50**,
solo per le agenzie con *Agenzia = si*. Quelle già cercate vengono saltate (spunta *Ricalcola* per rifarle).
Per ogni agenzia:

1. **Decisore** — riscarica home (footer compreso), chi siamo, team e contatti (robots.txt e pausa per sito
   come sempre) e l'AI scelta in *Impostazioni Agenzie* estrae titolare / founder / CEO / managing director
   (poi soci e partner). Se ce n'è più di uno vince il ruolo più alto. Il nome viene accettato **solo se nome e
   cognome compaiono davvero nel testo del sito**; altrimenti "non trovato" (niente nomi inventati).
2. **LinkedIn** — una ricerca Web Search (Tavily, 1 credito): `"Nome Cognome" "Agenzia" site:linkedin.com/in`.
   Si usano **solo URL e titolo dei risultati**: le pagine linkedin.com non vengono mai aperte (il client HTTP
   le rifiuta). Si prende il primo profilo `/in/` il cui titolo contiene il cognome; confidenza **alta** se il
   titolo contiene anche il nome dell'agenzia o il ruolo, altrimenti **media**.
3. **Email** — prima l'email nominativa trovata sul sito (es. `mario.rossi@`, `m.rossi@`, `mario@` sul dominio
   dell'agenzia) → *sito (verificata)*; altrimenti l'ipotesi `nome@dominio` → *ipotesi – da verificare*.
   Nessuna verifica SMTP, nessun servizio esterno.

Colonne nuove (tabella ed export): **Decisore, Ruolo, LinkedIn decisore, Confidenza LinkedIn, Email decisore,
Fonte email, Stato outreach**; nell'export anche pagina e citazione da cui viene il decisore e il titolo del
risultato LinkedIn. **Stato outreach** (da contattare / contattato / risposto / call / no) si cambia direttamente
nella tabella, viene salvato subito nel database e si può filtrare. Costo indicativo con Haiku 4.5: ≈ 0,007 $ di
AI + 1 ricerca web per agenzia.

## Configurazione

Tutti i parametri sono in `config/settings.py` e si possono sovrascrivere con variabili
d'ambiente con prefisso `PS_`:

| Parametro | Default | |
|---|---|---|
| `MAX_PAGES_PER_DOMAIN` | 10 | pagine visitate per sito |
| `MAX_WORKERS` | 5 | siti elaborati in parallelo |
| `REQUEST_TIMEOUT` | 10 | secondi |
| `REQUEST_DELAY` | 1 | pausa minima tra richieste allo stesso host |
| `MAX_RETRIES` | 2 | retry su errori temporanei/429 (rispetta `Retry-After`) |
| `DOMAIN_TIME_BUDGET` | 90 | secondi massimi per sito |
| `REENRICH_AFTER_DAYS` | 7 | i siti arricchiti più di recente vengono riusati dalla cache |
| `CONTACT` | vuoto | contatto aggiunto allo user-agent (consigliato) |
| `SEARXNG_URL` | vuoto | attiva la ricerca web |
| `DB_PATH` | `data/prospects.db` | |

Esempio: `PS_MAX_WORKERS=3 PS_CONTACT=tuo@email.it streamlit run app.py`

## Cosa fa l'enrichment

- Visita `/`, poi le pagine utili individuate **dai link** (URL o anchor text: contatti,
  scrivici, chi siamo, azienda, team, impressum, note legali...); prova `/contatti` e
  `/contact` solo se i link non rivelano nulla. Visita in ordine di priorità, fino al massimo di pagine.
- **Email**: `mailto:` + testo + attributi HTML; minuscole, deduplicate; escluse le
  tecniche (`noreply@`, `no-reply@`, `donotreply@`, `mailer-daemon@`...) e quelle segnaposto.
  `info@`, `hello@`, `commerciale@`, `booking@`, `sales@` sono mantenute. Email principale:
  prima quelle sul dominio del sito e con prefisso commerciale, in fondo PEC e privacy.
- **Telefoni**: link `tel:` + testo, validati con libphonenumber (italiani e internazionali),
  in formato internazionale; formato originale in `phone_raw`. P.IVA, CF, REA non vengono scambiati per telefoni.
- **Social**: solo URL di profilo effettivamente linkati (LinkedIn, Instagram, Facebook,
  YouTube, X/Twitter); esclusi i link di condivisione, i post e i plugin.
- **Azienda**: nome, titolo, descrizione, indirizzo, CAP, città, regione, paese, P.IVA, da
  schema.org JSON-LD, microdata, meta tag e formato indirizzo italiano (`Via ..., 90133 Palermo (PA)`).
- Dati non mappati: nel campo `raw_data` (JSON), es. pagine visitate, errori per pagina, tag OSM.

## Robustezza e buone maniere

- Timeout, retry limitati, pausa per host, user-agent identificabile, max pagine per dominio, max 5 siti in parallelo.
- robots.txt rispettato (RFC 9309).
- Login, CAPTCHA, paywall e protezioni anti-bot **non** vengono aggirati: il prospect risulta
  `failed` con il motivo.
- Ogni errore (timeout, DNS, SSL, 403, 404, 429, redirect verso un social, contenuto non HTML...)
  viene salvato in `status = failed` + `error_message` e il processo continua. Con un
  certificato SSL non valido il sito viene riprovato in `http://`, senza mai disattivare la verifica.
- Log tecnico scaricabile dalla UI; log su file in `logs/prospect_scraper.log`.

Status possibili: `found` (trovato, non ancora arricchito), `no_website`, `enriched`, `failed`.

## Deduplicazione

Chiave primaria: dominio normalizzato (`https://www.x.it`, `http://x.it/`, `x.it` → `x.it`).
Senza dominio: nome normalizzato (senza forme societarie) + città. Vale sia dentro una
ricerca sia tra ricerche diverse: un prospect già presente viene aggiornato, non duplicato.
Un sito social o di portale (Facebook, Booking, TripAdvisor...) non viene mai usato come
sito aziendale: il link finisce nella colonna social oppure in `raw_data`.

## Struttura

```
prospect-scraper/
├── desktop.py                app Mac: server locale + finestra nativa (pywebview)
├── packaging/                build dell'app Mac e del DMG (GitHub Actions)
├── Avvia Prospect Scraper (Windows).bat, avvia-prospect-scraper-linux.sh
├── launcher.py               avvio da sorgente: prepara l'ambiente, apre la finestra
├── .streamlit/config.toml    aspetto e impostazioni dell'interfaccia
├── app.py                    UI Streamlit (solo interfaccia)
├── core/pipeline.py          orchestrazione ricerca → dedup → DB → enrichment
├── config/settings.py        parametri
├── config/user_settings.py   impostazioni dell'utente (chiavi API) in user_settings.json
├── config/agency_blacklist.txt, agency_scoring.toml   valori predefiniti di blacklist e pesi (Agenzie)
├── qualify/                  Agenzie: pagine, blog, schema/prompt/provider AI (Claude, OpenAI, Gemini), score
├── decision_makers/          Agenzie: decisore dal sito (AI + verifica), LinkedIn da risultati di ricerca, email
├── database/db.py, schema.sql
├── scrapers/
│   ├── http.py               client HTTP: rate limit, retry, robots.txt, errori
│   ├── web_search/           Web Search (Tavily, Brave, SearXNG): provider, discovery, dedup per dominio
│   ├── search/               motore di ricerca modulare (locale: OSM + Wikidata)
│   │   ├── base.py           interfaccia SearchProvider
│   │   ├── geo.py            geocoding località (Nominatim)
│   │   ├── osm.py, wikidata.py, searxng.py
│   ├── website.py            crawler + Playwright opzionale
│   ├── contacts.py           email e telefoni
│   ├── social.py             profili social
│   └── company.py            nome, indirizzo, città, P.IVA
├── models/prospect.py
├── exporters/export.py       CSV (UTF-8) e XLSX
├── utils/                    normalizzazione, deduplicazione, logging
└── tests/                    test + server locale con siti di prova
```

## Test

```bash
pip install pytest
python -m pytest
```

I test non usano Internet: un server locale simula siti con robots.txt, CAPTCHA, timeout,
404, redirect e pagine JavaScript; le API dei provider sono simulate. Per provare la UI
senza rete: `python -m tests.site_server 8765` e poi
`PS_SEARXNG_URL=http://127.0.0.1:8765 streamlit run app.py` (keyword `hotel`, fonte "Web (SearXNG)").

## Limiti noti

- **Copertura delle fonti**: OpenStreetMap è ottimo per attività con sede fisica
  (hotel, ristoranti, negozi), ma copre poco startup e SaaS; Wikidata copre solo realtà
  note. Per "SaaS Italia" serve SearXNG.
- La mappa keyword → tag OSM copre le categorie più comuni. Le keyword non riconosciute
  vengono cercate nel nome delle attività con sito web.
- Le API pubbliche (Overpass, Nominatim) hanno limiti d'uso: ricerche molto ampie
  (es. tutta Italia) possono andare in timeout. Meglio restringere la località.
- Le email offuscate (Cloudflare email protection, `nome [at] dominio`) e quelle dentro immagini
  non vengono lette, per scelta: sono protezioni anti-raccolta.
- Siti che richiedono JavaScript: senza Playwright vengono letti solo i dati presenti nell'HTML iniziale.
- Città e indirizzo si ricavano solo da dati strutturati o dal formato italiano: indirizzi esteri
  in testo libero non vengono riconosciuti.
- La ricerca web può restituire blog o elenchi ("I 10 migliori hotel..."): i portali noti sono
  filtrati, gli altri no.

## Idee per una V2

- App firmata e notarizzata da Apple (niente passaggio "Apri comunque"); versione Intel e Windows.

- Provider aggiuntivi: Brave Search API (piano gratuito), registro imprese / OpenCorporates,
  Google Places API (a pagamento), sitemap.xml del sito per trovare le pagine contatti.
- Coda persistente e ripresa delle esecuzioni interrotte; enrichment in background.
- Blacklist/whitelist di domini modificabile dalla UI; eliminazione e modifica manuale dei prospect.
- Storico delle esecuzioni consultabile e confronto tra ricerche.
- Estrazione dei nomi dei referenti dalle pagine team (con attenzione al GDPR).
- Verifica sintattica e MX delle email (senza invii).
- Più lingue e formati di indirizzo (FR, DE, ES).
