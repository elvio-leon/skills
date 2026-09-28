# YTGrab

App per Mac, piccola e veloce, per cercare, guardare e scaricare video da YouTube con
[yt-dlp](https://github.com/yt-dlp/yt-dlp). È pensata per recuperare B-roll da montare in DaVinci Resolve.

- Cerchi e guardi i video direttamente nell'app (lettore YouTube integrato).
- Scarichi video+audio, solo video o solo audio.
- Con **I** e **O** segni punti di ingresso e uscita, anche più volte: scarichi solo gli spezzoni che ti
  servono, ognuno in un file separato.
- Usa poca memoria: un server locale in Python con la sola libreria standard e una finestra WebKit nativa
  (niente Electron). Esegue al massimo 2 download in parallelo.

## Installazione

1. Scarica **YTGrab.dmg** dalla release
   [ytgrab-latest](https://github.com/elvio-leon/skills/releases/tag/ytgrab-latest). La release viene
   ricreata automaticamente a ogni modifica della cartella `ytgrab/`.
2. Apri il DMG e trascina **YTGrab** nella cartella **Applicazioni**.
3. **Solo la prima volta:** l'app non è firmata con un certificato sviluppatore Apple, quindi macOS la blocca.
   Aprila una volta (comparirà l'avviso), poi vai in **Impostazioni di Sistema → Privacy e sicurezza**,
   scorri in basso e premi **Apri comunque** accanto a "YTGrab". Dalle volte successive si apre normalmente.

L'app contiene già tutto quello che le serve: yt-dlp, ffmpeg e deno (un runtime JavaScript che yt-dlp usa
per leggere YouTube). Non devi installare nulla e non serve il Terminale. È compilata per Apple Silicon (M1/M2/M3/M4).

### Per sviluppatori

- `packaging/build_mac.sh` costruisce `dist/YTGrab.app` e `dist/YTGrab.dmg` su un Mac. Lo stesso script gira
  nel workflow `.github/workflows/ytgrab-mac.yml`.
- `./install.sh` installa invece la versione "da sorgente" con Homebrew, in un ambiente Python.
- `python3 app.py --browser` avvia l'app nel browser, senza finestra nativa.

## Come si usa

1. Scrivi nella barra di ricerca (<kbd>/</kbd> o <kbd>⌘K</kbd>) oppure incolla un link YouTube, poi premi Invio.
2. Clicca un risultato, o scorri con <kbd>↑</kbd> <kbd>↓</kbd>, per caricarlo nel lettore.
3. Se ti servono solo alcune parti, premi <kbd>I</kbd> all'inizio e <kbd>O</kbd> alla fine di ogni spezzone.
   Puoi anche scrivere gli intervalli a mano nel campo `1:20-1:45`.
4. Scegli la modalità e premi <kbd>D</kbd> o il pulsante **Scarica**. Senza spezzoni scarica il video intero.
   Il pulsante ⬇︎ su un risultato lo scarica subito, senza aprirlo.

| Tasto | Azione |
|---|---|
| <kbd>Spazio</kbd> / <kbd>K</kbd> | Play / pausa |
| <kbd>J</kbd> / <kbd>L</kbd> | −10 s / +10 s |
| <kbd>←</kbd> / <kbd>→</kbd> | −5 s / +5 s (con <kbd>⇧</kbd>: 1 s) |
| <kbd>,</kbd> / <kbd>.</kbd> | Frame precedente / successivo |
| <kbd>I</kbd> / <kbd>O</kbd> | Punto IN / OUT: ogni coppia crea uno spezzone |
| <kbd>Esc</kbd> | Annulla l'IN in sospeso |
| <kbd>⌫</kbd> / <kbd>X</kbd> | Elimina l'ultimo spezzone |
| <kbd>1</kbd> <kbd>2</kbd> <kbd>3</kbd> | Video+audio / solo video / solo audio |
| <kbd>D</kbd> | Scarica |

Se premi **O** senza aver segnato un **I**, lo spezzone parte dalla fine di quello precedente, oppure
dall'inizio del video se non ce ne sono.

## Qualità e DaVinci Resolve

| Opzione | Cosa scarica | Quando usarla |
|---|---|---|
| **H.264 · pronto per DaVinci** (predefinita) | H.264 + AAC in `.mp4`, fino a 1080p | È la più veloce: nessuna conversione e il file si importa subito in DaVinci. |
| **Massima → HEVC .mov** | Il flusso migliore (anche 4K VP9/AV1), ricodificato in HEVC con l'encoder hardware del chip M1 (VideoToolbox) | Quando ti serve il 4K. La conversione è rapida e il file si legge bene in DaVinci. |
| **Massima originale** | VP9/AV1 così come arriva da YouTube | Per archivio. DaVinci su M1 non legge il VP9 e legge male l'AV1. |

In **Solo audio** puoi scegliere M4A (AAC originale, senza perdita), WAV o MP3.

**Taglio preciso al frame**: di norma gli spezzoni vengono copiati senza ricodifica, quindi il taglio
cade sul keyframe più vicino e può anticipare di qualche frame. Se attivi l'opzione, i punti di taglio
vengono ricodificati: il taglio è esatto ma il download è più lento.

I file finiscono in `~/Movies/YTGrab` (la cartella si cambia in basso a destra) con nomi come
`Titolo [id]_00h01m20s-00h01m45s.mp4`.

## Problemi comuni

- **"Sign in to confirm you're not a bot"**: in basso a destra, alla voce *Cookie*, scegli il browser in
  cui hai fatto l'accesso a YouTube (Safari potrebbe chiederti l'accesso completo al disco per il Terminale).
- **Un download che prima funzionava ora fallisce**: YouTube cambia spesso. Premi **Aggiorna yt-dlp**
  (in basso a destra) e riapri l'app. La nuova versione viene salvata in
  `~/Library/Application Support/YTGrab` e non serve riscaricare il DMG.
- **Anteprima non disponibile**: alcuni video non si possono incorporare. Puoi comunque scaricarli e
  aggiungere gli spezzoni a mano.

## Struttura

```
ytgrab/
├── app.py          server locale + API + download (yt-dlp come libreria)
├── web/index.html  interfaccia (HTML/CSS/JS in un unico file, nessuna dipendenza)
├── packaging/      build dell'app .app/.dmg (PyInstaller) e icona
├── install.sh      installazione da sorgente con Homebrew
└── requirements.txt
```
