# Prospect Scraper

Tool locale per trovare aziende appartenenti a un ICP e raccogliere le informazioni
pubbliche dai loro siti web: email, telefoni, social, indirizzo, città, P.IVA.
Risultati in tabella (ordinabile, filtrabile, con selezione righe) ed export CSV/XLSX.

Niente AI, scoring, audit SEO, CRM o automazioni: è un MVP volutamente semplice.

## Installazione

Richiede Python 3.11+.

```bash
cd prospect-scraper
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# opzionale, per i siti che mostrano i contenuti solo via JavaScript
pip install playwright && playwright install chromium
```

## Avvio

```bash
streamlit run app.py
```

Si apre su http://localhost:8501. Il database viene creato in `data/prospects.db`,
i log tecnici in `logs/`.

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
   e selezionare righe; i pulsanti **DOWNLOAD CSV/XLSX** esportano le righe selezionate
   oppure, se non ne selezioni, tutte quelle filtrate.

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
├── app.py                    UI Streamlit (solo interfaccia)
├── core/pipeline.py          orchestrazione ricerca → dedup → DB → enrichment
├── config/settings.py        parametri
├── database/db.py, schema.sql
├── scrapers/
│   ├── http.py               client HTTP: rate limit, retry, robots.txt, errori
│   ├── search/               motore di ricerca modulare
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

- Provider aggiuntivi: Brave Search API (piano gratuito), registro imprese / OpenCorporates,
  Google Places API (a pagamento), sitemap.xml del sito per trovare le pagine contatti.
- Coda persistente e ripresa delle esecuzioni interrotte; enrichment in background.
- Blacklist/whitelist di domini modificabile dalla UI; eliminazione e modifica manuale dei prospect.
- Storico delle esecuzioni consultabile e confronto tra ricerche.
- Estrazione dei nomi dei referenti dalle pagine team (con attenzione al GDPR).
- Verifica sintattica e MX delle email (senza invii).
- Più lingue e formati di indirizzo (FR, DE, ES).
