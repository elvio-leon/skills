# YouTube Kit per DaVinci Resolve (versione gratuita)

Una libreria di **titoli animati, transizioni, effetti video, look colore ed effetti sonori** ispirata a quello che usano i principali YouTuber (MrBeast, Ali Abdaal, Hormozi, Peter McKinnon, MKBHD...), costruita **solo con strumenti disponibili nella versione free** di DaVinci Resolve (Fusion + Fairlight). Niente plugin a pagamento, niente Studio.

Tutto è pensato per il flusso "**trascino e funziona**": metti l'elemento in timeline sullo spezzone che ti interessa e si applica da solo. Le animazioni si adattano automaticamente alla durata della clip: entrata e uscita restano sempre alla stessa velocità, qualunque sia la lunghezza.

| Cosa | Quanti | Dove |
|---|---|---|
| Titoli animati | 11 | Macchina da scrivere, testo pop, parola per parola, lower third, iscriviti, contatore, glitch... |
| Transizioni | 11 | Zoom in/out, whip pan (4 direzioni), flash, glitch, spin, light leak, dissolvenza sfocata |
| Effetti video | 21 | Camera shake, zoom punch-in, zoom lento, RGB split, VHS, vignetta, bande cinema, censura, PiP, 8 look colore |
| Generatori | 3 | Barra di progresso, bande cinema, sfondo animato |
| Effetti sonori | 21 | Whoosh, riser, boom, pop, click, macchina da scrivere, ding, glitch, cassa... |
| LUT colore | 8 | Teal & Orange, Caldo, Freddo, Vintage, Moody, Vivace, B&N, Pastello |

L'elenco completo con la descrizione di ogni elemento è in **[CATALOGO.md](CATALOGO.md)**.

> **Pacchetto su misura "Linea di Fondo"**: titoli, transizioni ed effetti costruiti sull'identità del canale sono nella cartella [`linea-di-fondo/`](linea-di-fondo/README.md) (installer: [`dist/LineaDiFondo.drfx`](dist/LineaDiFondo.drfx)).

---

## 1. Installazione

Serve **DaVinci Resolve 18 o successivo** (gratuito). Scegli **uno** dei tre metodi.

### Metodo A: file unico `.drfx` (il più semplice)

1. Scarica [`dist/YouTubeKit.drfx`](dist/YouTubeKit.drfx).
2. Con DaVinci Resolve aperto, **fai doppio clic sul file** oppure **trascinalo dentro la finestra di Resolve** e conferma con *Install*.
3. Riavvia Resolve.

### Metodo B: installer automatico

1. Scarica [`dist/YouTubeKit-completo.zip`](dist/YouTubeKit-completo.zip) ed estrailo.
2. Chiudi Resolve.
3. **Windows**: doppio clic su `installa_windows.bat`.
   **Mac**: doppio clic su `installa_mac.command` (se macOS lo blocca: tasto destro → *Apri*).
4. Riapri Resolve.

L'installer copia anche le LUT nella cartella di Resolve.

### Metodo C: copia a mano

Copia il **contenuto** della cartella `Templates/Edit/` (le 4 cartelle `Titles`, `Transitions`, `Effects`, `Generators`) in:

| Sistema | Cartella |
|---|---|
| Windows | `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Fusion\Templates\Edit\` |
| macOS | `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit/` |
| Linux | `~/.local/share/DaVinciResolve/Fusion/Templates/Edit/` |

> Scorciatoia: nella pagina **Fusion** apri la *Effects Library*, clicca sui tre puntini → **Show Folder** per aprire direttamente la cartella giusta.

Per le LUT: in Resolve vai su **File → Project Settings → Color Management → Open LUT Folder**, copia lì dentro la cartella `LUT`, poi clicca **Update Lists**.

### Verifica

Pagina **Edit** → **Effects Library** (in alto a sinistra) → cerca **`YTK`** nella barra di ricerca. Tutti gli elementi del kit iniziano con `YTK`.

---

## 2. Come si usa

### Titoli (`Titles → Fusion Titles`)

1. Trascina il titolo su una **traccia sopra** il video (es. V2), in corrispondenza del punto in cui deve comparire.
2. Allunga o accorcia la clip del titolo: l'animazione di entrata e di uscita si adatta da sola.
3. Seleziona il titolo → **Inspector** (in alto a destra) → scheda **Video**: cambi testo, font, colori, posizione, durata dell'entrata ecc.

Consigli per ogni titolo:

| Titolo | Consiglio d'uso |
|---|---|
| **Macchina da Scrivere** | "Durata scrittura" = quanti frame per scrivere tutto il testo. Abbinalo all'SFX `macchina_da_scrivere_loop.wav`. Opzione per cancellare il testo lettera per lettera alla fine. |
| **Testo Pop** | Per enfatizzare frasi chiave, stile MrBeast. Abbinalo a `pop.wav` o `boom_meme.wav`. |
| **Parola per Parola** | Scrivi la frase intera nel campo "Frase": le parole appaiono una alla volta. "Frame per parola" regola la velocità (a 30 fps: 8 frame ≈ 4 parole al secondo). Togli la spunta "Mostra solo la parola corrente" per farle accumulare. Perfetto per Shorts/Reels/TikTok. |
| **Box Evidenziato** | Una parola chiave su riquadro colorato. Regola i margini se il box è troppo stretto o largo. |
| **Lower Third** | Nome + ruolo quando presenti una persona. Entrano da sinistra con un piccolo sfasamento. |
| **Iscriviti** | Pulsante rosso che dopo "Click dopo (frame)" diventa grigio con "ISCRITTO". Abbinalo a `click_mouse.wav` posizionato sul click. Puoi cambiare i due testi (es. "SUBSCRIBE"). |
| **Titolo Cinematico** | Titolo d'apertura: le lettere si allargano lentamente e appaiono dal fuori-fuoco. |
| **Titolo Glitch** | Titolo per video tech/gaming. Abbinalo a `glitch_digitale.wav`. |
| **Contatore** | Numeri che salgono: iscritti, euro, visualizzazioni. Imposta "Da", "A", prefisso (es. `€ `) e suffisso (es. ` iscritti`). |
| **Cerchio Evidenzia** / **Freccia** | Per indicare un dettaglio (tutorial, reaction, screen recording). Sposta la posizione trascinando il mirino nel viewer. |

### Transizioni (`Video Transitions → Fusion Transitions`)

1. Trascina la transizione **sul punto di taglio** tra due clip.
2. Allunga o accorcia la transizione dai bordi: l'animazione segue la durata. Per zoom/whip/glitch le durate migliori sono **8-15 frame**; per light leak e dissolvenza sfocata **20-40 frame**.
3. Abbina sempre un suono: `whoosh_veloce.wav` per zoom e whip, `glitch_digitale.wav` per il glitch, `swipe.wav` per whip brevi.

> ⚠️ Una transizione ha bisogno di qualche frame "in più" (handles) oltre al punto di taglio in entrambe le clip. Se Resolve ti avvisa che la clip non è abbastanza lunga, accorcia leggermente le clip vicino al taglio.

### Effetti (`Effects`)

1. Trascina l'effetto **direttamente sopra la clip** in timeline.
2. Per applicarlo a più clip insieme: `Effects Library → Effects → Adjustment Clip`, mettilo su V2 sopra le clip e trascina l'effetto sull'Adjustment Clip.
3. Le impostazioni si trovano selezionando la clip → Inspector → scheda **Effects**.

| Effetto | Consiglio d'uso |
|---|---|
| **Zoom Punch-In** | Il classico "jump cut zoom" degli youtuber: taglia la clip con `Ctrl+B`/`Cmd+B` e metti l'effetto sulla seconda metà. Durata animazione 0 = zoom istantaneo. |
| **Zoom Impatto** | Zoom improvviso con scossa per i momenti "WOW". Abbinalo a `impatto_boom.wav`. |
| **Zoom Lento** | Movimento lento continuo (Ken Burns) per rendere dinamiche riprese statiche e foto. |
| **Camera Shake** | Tremolio per esplosioni, urla, momenti di tensione. |
| **RGB Split** / **VHS Retro** / **Grana Pellicola** / **Glow Sogno** | Stilizzazioni. Usale su clip brevi o su un Adjustment Clip. |
| **Vignetta** / **Bianco e Nero** | Per concentrare l'attenzione o per flashback. |
| **Bande Cinema** | Bande nere 2.39:1. Per tutto il video conviene il **generatore** omonimo su una traccia sopra. |
| **Sfocatura Censura** | Sposta e ridimensiona l'area da sfocare (targhe, email, volti). |
| **Picture in Picture** | Riduce la clip in un riquadro con bordo arrotondato: mettilo sulla clip della facecam posizionata su V2 sopra lo screen recording. |
| **Look ...** | 8 look colore trascinabili con cursore "Intensità look". Applicali **dopo** aver corretto esposizione e bilanciamento del bianco. |

### Generatori (`Generators → Fusion Generators`)

| Generatore | Uso |
|---|---|
| **Barra Progresso** | Mettila su una traccia in alto per tutta la durata del video (o di un capitolo): si riempie da sola. Ottima per Shorts e video lunghi con capitoli. |
| **Bande Cinema** | Bande nere su una traccia sopra tutto il video. Entrata animata opzionale. |
| **Sfondo Animato** | Sfondo colorato in movimento per intro, outro, schermate di testo. |

### Effetti sonori (`SFX/`)

1. Nella pagina **Edit** o **Media**, trascina la cartella `SFX` nel **Media Pool**.
2. Trascina il suono su una traccia audio libera (A2, A3...) nel punto giusto.
3. Regola il volume dalla clip audio (linea orizzontale) o dall'Inspector. In genere gli SFX stanno bene **tra -12 e -20 dB** sotto la voce.

Tutti i suoni sono generati da zero (sintesi procedurale): **nessun problema di copyright**, puoi usarli anche in video monetizzati.

### LUT colore (`LUT/`)

Oltre agli effetti `YTK Look ...` trascinabili, puoi usare le LUT nella pagina **Color**: tasto destro su un nodo → **LUT** → **YouTube Kit** → scegli il look. Metti la LUT in un nodo **dopo** quello di correzione (esposizione, bilanciamento del bianco).

---

## 3. Effetti audio per la voce (Fairlight, versione free)

I preset audio di Fairlight non si possono distribuire come file, ma bastano 2 minuti per ricreare la catena usata dagli youtuber e **salvarla come preset** da riutilizzare in ogni video.

Pagina **Fairlight** → sulla traccia della voce apri **EQ** e **Dynamics** dal Mixer (doppio clic sulle rispettive caselle):

**EQ (voce chiara e "da YouTube")**

| Banda | Tipo | Frequenza | Guadagno | A cosa serve |
|---|---|---|---|---|
| 1 | High-pass | 80 Hz | – | Toglie rimbombi e rumori bassi |
| 2 | Bell | 300 Hz | -3 dB, Q 1.5 | Toglie l'effetto "stanza/scatola" |
| 3 | Bell | 4 kHz | +2.5 dB, Q 1 | Presenza e intelligibilità |
| 4 | High shelf | 10 kHz | +1.5 dB | "Aria" e brillantezza |

**Dynamics → Compressor**: Threshold -18 dB, Ratio 3:1, Attack 10 ms, Release 100 ms, Make-up gain finché la voce è costante.
**Dynamics → Gate** (se c'è rumore di fondo): Threshold -45 dB, Range -15 dB.

**Effetti dalla Effects Library → Audio FX → Fairlight FX** (trascinali sulla traccia):
- **De-Esser**: frequenza 6 kHz, Amount 5-8 dB, per le "S" troppo taglienti.
- **De-Hummer**: 50 Hz (Italia/Europa) se senti un ronzio elettrico.
- **Limiter** sulla traccia **Main (Bus 1)**: Ceiling **-1 dB**.

**Volume finale per YouTube**: circa **-14 LUFS** integrati. Apri il meter di loudness (Fairlight → *Loudness*) e regola il fader del Main finché "Integrated" è vicino a -14.

**Musica sotto la voce (ducking)**: sulla traccia musica tieni il volume **tra -20 e -25 dB** quando si parla, e alzalo nelle pause con i keyframe del volume (Alt/Option + clic sulla linea del volume).

**Salva come preset**: nel pannello EQ/Dynamics clicca l'icona del preset (in alto) → *Save Preset* → "Voce YouTube". Nel prossimo progetto lo richiami con un clic.

**Voci speciali con Fairlight FX gratuiti**

| Effetto | Come ottenerlo |
|---|---|
| Voce al telefono / radio | EQ: high-pass 300 Hz + low-pass 3.400 Hz, + un po' di *Distortion* |
| Eco "pensiero" | *Echo*: Delay 250 ms, Feedback 30%, Dry/Wet 25% |
| Stanza grande / flashback | *Reverb*: Room Size alto, Dry/Wet 30% |
| Voce robot / mostro | *Pitch*: -5 semitoni (mostro) o +5 (chipmunk); per il robot aggiungi *Modulation*/*Chorus* |

---

## 4. Domande frequenti

**Non vedo gli elementi del kit.** Riavvia Resolve dopo l'installazione. Controlla di aver copiato il *contenuto* di `Templates/Edit` (le cartelle `Titles`, `Transitions`...) e non la cartella `Edit` dentro un'altra `Edit`.

**Il testo usa un font diverso.** I titoli usano font presenti su Windows e Mac (Arial, Arial Black, Courier New). Se non li hai, scegline un altro dall'Inspector. Per lo stile YouTube consiglio i font gratuiti *Montserrat* (ExtraBold/Black), *Bebas Neue*, *Anton*, *Poppins*.

**La riproduzione scatta.** I template Fusion sono più pesanti delle clip normali. Attiva *Playback → Render Cache → Smart* e aspetta che la barra rossa sopra la timeline diventi blu.

**Voglio modificare un template più a fondo.** Tasto destro sull'elemento in timeline → **Open in Fusion Page**. Ogni template ha un nodo `Ctrl` che contiene i controlli principali.

**Posso usarlo in video verticali (Shorts)?** Sì: i template si adattano alla risoluzione della timeline. Nei titoli sposta solo la posizione se serve.

---

## 5. Per sviluppatori: rigenerare il kit

Tutto il kit (template Fusion, icone, LUT, suoni, pacchetti) è generato dal codice in `build/`:

```bash
pip install numpy scipy pillow lupa
python3 build/build_all.py
```

- `build/fusion.py`: writer dei file `.setting` di Fusion.
- `build/templates.py`: definizione di ogni titolo/transizione/effetto/generatore.
- `build/luts.py`: look colore → file `.cube`.
- `build/sfx.py`: sintesi degli effetti sonori.
- `build/build_all.py`: genera tutto, **valida** ogni template (parsing Lua, collegamenti tra nodi, esecuzione di ogni espressione in un ambiente simulato) e crea `dist/YouTubeKit.drfx` e `dist/YouTubeKit-completo.zip`.
