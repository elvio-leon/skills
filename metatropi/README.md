# Metatropi

Convertitore universale per macOS che lavora **interamente in locale**: nessun
file viene caricato su internet.

Trascina file o cartelle nella finestra, scegli il formato e premi **Converti**.
I file convertiti finiscono accanto agli originali (o in una cartella a scelta),
senza mai sovrascrivere nulla.

## Cosa converte

| Categoria | Da | A |
|---|---|---|
| PDF | PDF (anche scansioni, con OCR) | **Word (DOCX)**, DOC, ODT, RTF, HTML, Markdown, EPUB, TXT, **Excel/ODS/CSV** (le tabelle), **PowerPoint** (una slide per pagina), PNG/JPG (una per pagina) |
| Immagini | JPG, PNG, WebP, AVIF, HEIC, GIF, TIFF, BMP, ICO, SVG, PSD, RAW (DNG, CR2, CR3, NEF, ARW…) | JPG, PNG, WebP, AVIF, HEIC, GIF, TIFF, BMP, ICO, PDF, **TXT/Word con l'OCR** |
| Video | MP4, MOV, MKV, WebM, AVI, M4V, WMV, FLV, MPEG, 3GP, TS | MP4, MOV, MKV, WebM, AVI, GIF animata, solo audio |
| Audio | MP3, WAV, AAC/M4A, FLAC, OGG, Opus, AIFF, WMA, AMR, CAF | MP3, M4A (AAC), ALAC, WAV, FLAC, AIFF, OGG, Opus |
| Documenti | DOCX, DOC, ODT, RTF, Markdown, HTML, TXT, EPUB, LaTeX, RST, Org, Jupyter | PDF, DOCX, DOC, ODT, RTF, HTML, Markdown, TXT, EPUB, LaTeX, RST, PPTX, PNG/JPG |
| Presentazioni | PPTX | PDF, Word, ODT, HTML, Markdown, TXT, EPUB (testo, tabelle e immagini delle slide) |
| Presentazioni* | PPTX, PPT, ODP, Keynote, Pages | PDF fedele all'originale, PPTX, ODP, PNG/JPG per slide |
| Fogli e dati | XLSX, XLS, ODS, Numbers, CSV, TSV, JSON, YAML | XLSX, ODS, CSV, TSV, JSON, YAML, HTML, Markdown, PDF, Word, ODT |
| Sottotitoli | SRT, VTT, ASS, SSA | SRT, VTT, ASS |

\* Richiede [LibreOffice](https://www.libreoffice.org) (gratuito). Se è installato,
Metatropi lo usa automaticamente anche per avere PDF più fedeli da Word ed Excel.

Motori inclusi: ffmpeg, pandoc, un Python portatile con
[pdf2docx](https://github.com/ArtifexSoftware/pdf2docx) e PyMuPDF (PDF → Word ed
Excel), il riconoscimento del testo di macOS (Vision) per l'OCR.

Opzioni: qualità e dimensione massima delle immagini, unione di più immagini in
un solo PDF, bitrate audio, qualità e risoluzione video, conversione video
rapida senza ricodifica, DPI per PDF → immagine, separatore CSV.

## Scaricare il DMG

Ogni build riuscita pubblica i DMG nella Release del repository, scaricabile
senza account GitHub:

- **Mac con chip Apple** (M1, M2, M3, M4…):
  https://github.com/elvio-leon/skills/releases/download/metatropi-v1.1.0/Metatropi-1.1.0-arm64.dmg
- **Mac con processore Intel**:
  https://github.com/elvio-leon/skills/releases/download/metatropi-v1.1.0/Metatropi-1.1.0-x64.dmg

Pagina della release: https://github.com/elvio-leon/skills/releases/tag/metatropi-v1.1.0

I DMG vengono creati da GitHub Actions su un Mac (workflow
`.github/workflows/metatropi-macos.yml`). Quando cambi `version` in
`package.json`, la build successiva crea una nuova release con quel numero.

### Primo avvio

L'app non è firmata con un certificato Apple Developer, quindi al primo avvio
macOS la blocca. Per aprirla:

- **Impostazioni di Sistema → Privacy e sicurezza**, scorri in basso e premi
  **Apri comunque** accanto a Metatropi; oppure
- da Terminale: `xattr -dr com.apple.quarantine /Applications/Metatropi.app`

Va fatto una sola volta.

## Sviluppo

```bash
cd metatropi
npm install
npm run fetch-binaries   # scarica ffmpeg e pandoc per il tuo sistema in vendor/
npm start                # avvia l'app
npm run selftest         # converte file di prova in tutti i formati
npm run dist:mac         # crea il DMG per Apple Silicon (va eseguito su un Mac)
npm run dist:mac-intel   # crea il DMG per Mac Intel
```

Struttura:

- `src/main.js` – processo principale Electron, coda di conversione, IPC
- `src/core/formats.js` – catalogo formati e conversioni possibili
- `src/core/convert.js` – sceglie il motore per ogni conversione
- `src/core/media.js` – ffmpeg e `sips` (immagini, audio, video, sottotitoli)
- `src/core/docs.js` – pandoc, `textutil`, LibreOffice
- `src/core/sheets.js` – SheetJS e YAML
- `src/core/chromium.js` – stampa PDF e motore pdf.js/SVG nascosto
- `src/ui/` – interfaccia
