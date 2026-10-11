# Metatropi

Convertitore universale per macOS che lavora **interamente in locale**: nessun
file viene caricato su internet.

Trascina file o cartelle nella finestra, scegli il formato e premi **Converti**.
I file convertiti finiscono accanto agli originali (o in una cartella a scelta),
senza mai sovrascrivere nulla.

## Cosa converte

| Categoria | Da | A |
|---|---|---|
| Immagini | JPG, PNG, WebP, AVIF, HEIC, GIF, TIFF, BMP, ICO, SVG, PSD, RAW (DNG, CR2, CR3, NEF, ARW…) | JPG, PNG, WebP, AVIF, HEIC, GIF, TIFF, BMP, ICO, PDF |
| Video | MP4, MOV, MKV, WebM, AVI, M4V, WMV, FLV, MPEG, 3GP, TS | MP4, MOV, MKV, WebM, AVI, GIF animata, solo audio |
| Audio | MP3, WAV, AAC/M4A, FLAC, OGG, Opus, AIFF, WMA, AMR, CAF | MP3, M4A (AAC), ALAC, WAV, FLAC, AIFF, OGG, Opus |
| Documenti | DOCX, DOC, ODT, RTF, Markdown, HTML, TXT, EPUB, LaTeX, RST, Org, Jupyter | PDF, DOCX, DOC, ODT, RTF, HTML, Markdown, TXT, EPUB, LaTeX, RST, PPTX |
| Fogli e dati | XLSX, XLS, ODS, Numbers, CSV, TSV, JSON, YAML | XLSX, ODS, CSV, TSV, JSON, YAML, HTML, Markdown, PDF |
| PDF | PDF | PNG o JPG (una immagine per pagina), TXT |
| Sottotitoli | SRT, VTT, ASS, SSA | SRT, VTT, ASS |
| Presentazioni* | PPTX, PPT, ODP, Keynote, Pages | PDF, PPTX, ODP, DOCX |

\* Richiede [LibreOffice](https://www.libreoffice.org) (gratuito). Se è installato,
Metatropi lo usa automaticamente anche per avere PDF più fedeli da Word ed Excel.

Opzioni: qualità e dimensione massima delle immagini, unione di più immagini in
un solo PDF, bitrate audio, qualità e risoluzione video, conversione video
rapida senza ricodifica, DPI per PDF → immagine, separatore CSV.

## Scaricare il DMG

Il DMG viene creato da GitHub Actions su un Mac (workflow
`.github/workflows/metatropi-macos.yml`):

1. Apri la scheda **Actions** del repository → **Metatropi (macOS)** →
   l'ultima esecuzione verde.
2. In fondo, sotto **Artifacts**, scarica:
   - `Metatropi-macOS-arm64` per i Mac con chip Apple (M1, M2, M3, M4…);
   - `Metatropi-macOS-x64` per i Mac con processore Intel.
3. Estrai lo zip e apri il `.dmg`, poi trascina Metatropi in **Applicazioni**.

Per pubblicare una release con il DMG scaricabile da un link fisso basta creare
un tag `metatropi-v1.0.0` (o successivo) e fare push del tag.

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
