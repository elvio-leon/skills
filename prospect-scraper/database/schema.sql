PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS prospects (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_key      TEXT NOT NULL UNIQUE,   -- "d:<dominio>" oppure "n:<nome>|<città>"
    company_name   TEXT,
    domain         TEXT,
    website        TEXT,
    category       TEXT,
    country        TEXT,
    region         TEXT,
    city           TEXT,
    address        TEXT,
    postal_code    TEXT,
    vat_id         TEXT,
    phone          TEXT,
    phones         TEXT,
    phone_raw      TEXT,
    email          TEXT,
    emails         TEXT,
    linkedin       TEXT,
    instagram      TEXT,
    facebook       TEXT,
    youtube        TEXT,
    twitter        TEXT,
    page_title     TEXT,
    description    TEXT,
    source         TEXT,
    source_url     TEXT,
    search_query   TEXT,
    status         TEXT,
    error_message  TEXT,
    raw_data       TEXT,                   -- JSON con dati raccolti ma non mappati
    first_seen     TEXT,
    last_seen      TEXT,
    enriched_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_prospects_domain ON prospects(domain);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT,
    finished_at  TEXT,
    mode         TEXT,
    category     TEXT,
    keyword      TEXT,
    location     TEXT,
    max_results  INTEGER,
    providers    TEXT,
    n_found      INTEGER,
    n_unique     INTEGER,
    n_enriched   INTEGER,
    n_failed     INTEGER
);

CREATE TABLE IF NOT EXISTS run_prospects (
    run_id       INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    prospect_id  INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    PRIMARY KEY (run_id, prospect_id)
);

-- Qualifica delle agenzie (ricerca "Agenzie"): una riga per prospect, liste/dizionari come JSON.
CREATE TABLE IF NOT EXISTS agency_qualifications (
    prospect_id        INTEGER PRIMARY KEY REFERENCES prospects(id) ON DELETE CASCADE,
    run_id             INTEGER,
    status             TEXT,                -- ok | failed | excluded
    error              TEXT,
    is_agency          TEXT,
    servizi            TEXT,
    servizi_altro      TEXT,
    seo_level          TEXT,
    servizi_ricorrenti TEXT,
    verticali          TEXT,
    size_signal        TEXT,
    blog_status        TEXT,
    blog_last_post     TEXT,
    note               TEXT,
    score              INTEGER,
    score_breakdown    TEXT,
    evidence           TEXT,
    pages_used         TEXT,
    llm_provider       TEXT,
    llm_model          TEXT,
    input_tokens       INTEGER,
    output_tokens      INTEGER,
    cost_usd           REAL,
    latency_s          REAL,
    qualified_at       TEXT
);

-- Decisore delle agenzie (pulsante "Trova contatti"): una riga per prospect.
CREATE TABLE IF NOT EXISTS decision_makers (
    prospect_id         INTEGER PRIMARY KEY REFERENCES prospects(id) ON DELETE CASCADE,
    status              TEXT,                -- trovato | non_trovato | fallito
    error               TEXT,
    nome                TEXT,
    cognome             TEXT,
    ruolo               TEXT,
    source_url          TEXT,
    evidence            TEXT,
    linkedin_url        TEXT,
    linkedin_title      TEXT,
    linkedin_confidence TEXT,                -- alta | media | non trovato | non cercato: motivo
    email               TEXT,
    email_source        TEXT,                -- sito | ipotesi
    email_verified      INTEGER,
    pages_used          TEXT,
    llm_provider        TEXT,
    llm_model           TEXT,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    cost_usd            REAL,
    latency_s           REAL,
    web_calls           INTEGER,
    found_at            TEXT
);

-- Stato del contatto commerciale, modificabile dalla tabella (da contattare, contattato, ...).
CREATE TABLE IF NOT EXISTS outreach (
    prospect_id INTEGER PRIMARY KEY REFERENCES prospects(id) ON DELETE CASCADE,
    stato       TEXT NOT NULL,
    updated_at  TEXT
);
