# Linea di Fondo: pacchetto animazioni per DaVinci Resolve (free)

Titoli, transizioni, effetti, look colore e suoni costruiti sull'identità visiva di **Linea di Fondo — Storie di calcio nel mondo**. Tutto funziona nella versione gratuita di DaVinci Resolve (18 o successivo).

Elenco completo: **[CATALOGO.md](CATALOGO.md)**.

## Cosa ho preso dal moodboard (e cosa no)

| Preso | Come è applicato |
|---|---|
| Palette | Verde profondo `#183A2F` per pannelli e sfondi, avorio `#F5EFE6` per i testi, terracotta `#B5323C` **solo** per linee, punti, rotte e date, ardesia `#1E1E1E` per il testo su carta |
| Tipografia | **Optima** per tutto: Regular per titoli e anni, Bold per nomi e luoghi, tracking ampio per coordinate e label. Niente secondo font |
| La linea | Elemento centrale di quasi tutti i template: appare, si estende, diventa rotta, timeline, sottolineatura, confine tra due clip, campo da calcio |
| Motion | Lento, preciso, geometrico: solo easing morbidi, nessun rimbalzo, nessuno zoom aggressivo (per le parti intense c'è il pack [Ritmo](../linea-di-fondo-ritmo/README.md)) |
| Spazio negativo | Testi piccoli e allineati a sinistra, tanto verde intorno |
| Carta | Texture presente ma discreta (micro-grana), mai vintage |

**Escluso volutamente** (perché il brief lo vieta): glitch, particelle, glow, zoom aggressivi, grana pesante, vignette, filtri verde/seppia forzati sulle foto. Esclusi anche logo, banner e thumbnail, come mi hai chiesto.

## 1. Font

Tutti i titoli usano **Optima** (Regular per i titoli, Bold per nomi e luoghi): è già disponibile in DaVinci Resolve, non serve installare nulla. SangBleu e Inter della guida di brand non sono più richiesti.

Per cambiare peso a un testo usa il campo **Stile** nell'Inspector: *Regular*, *Italic*, *Bold*, *Bold Italic* ed *ExtraBlack* (se la tua versione di Optima lo include).

## 2. Installazione

**Metodo semplice:** doppio clic su `LineaDiFondo.drfx` (oppure trascinalo nella finestra di Resolve) → *Install* → riavvia Resolve.

**In alternativa:** estrai `LineaDiFondo-completo.zip` e lancia `installa_windows.bat` o `installa_mac.command`.

Nella **Effects Library** cerca **`LDF`**: tutti gli elementi iniziano così e sono nella cartella *Linea di Fondo*.

## 3. Come si usa

Regola generale: **titoli** su una traccia sopra la clip, **transizioni** sul taglio, **effetti** sopra la clip. Le animazioni di entrata restano lente e uguali qualunque sia la durata; l'uscita è una dissolvenza negli ultimi frame (regolabile).

Ogni titolo ha il controllo **"Durata animazioni"**: 1 = normale, 1.5-2 = ancora più lento e solenne, 0.7 = più rapido.

### Titoli

| Titolo | Uso tipico | Suono consigliato |
|---|---|---|
| **LDF Linea** | La firma del canale: punto che appare e linea che si estende. Sottolinea una parola, separa due blocchi, con *Rotazione 90* diventa verticale | `linea_breve` |
| **LDF Titolo Editoriale** | Apertura del video o di un capitolo: sopratitolo terracotta ("CAPITOLO 01"), titolo serif, linea, sottotitolo. Con *Sfondo verde pieno* diventa una schermata titolo | `colpo_documentario` + `linea_breve` |
| **LDF Coordinate** | Quando la storia arriva in un luogo: KABUL + coordinate che si scrivono + data e paese. Colonna data disattivabile | `macchina_da_scrivere_archivio` |
| **LDF Persona** | Presentare un calciatore o un personaggio: nome, descrizione, periodo. Opzione ombra morbida se la foto è chiara | `linea_breve` |
| **LDF Club** | Presentare un club: nome, payoff, città, anno di fondazione | `linea_breve` |
| **LDF Evento** | Data dominante (es. 1986) + titolo evento. Opzione "l'anno scorre fino alla data" per il passaggio del tempo | `colpo_documentario` |
| **LDF Archivio** | Didascalia di una foto d'archivio: anno terracotta e testo su cartoncino avorio | `carta_foglio`, `timbro` |
| **LDF Timeline** | La linea attraversa lo schermo e accende 2-6 date (scrivi le date nei campi "Punto 1...6") | `linea_traccia` + `tick_timeline` su ogni data |
| **LDF Rotta** | Sopra una mappa: la linea parte da un luogo e disegna la rotta fino all'altro. Trascina **Punto di partenza** e **Punto di arrivo** nel viewer sulle città della tua mappa | `punto_mappa`, `linea_traccia`, `punto_mappa` |
| **LDF Punto Luogo** | Evidenziare una città sulla mappa con nome e coordinate; anello che pulsa lentamente (disattivabile) | `punto_mappa` |
| **LDF Campo** | La linea si trasforma nel campo da calcio: chiusura, sigla o passaggio tra capitoli | `linea_traccia` |

### Transizioni

Durate consigliate: **20-40 frame**. Qui la calma fa parte dello stile.

| Transizione | Uso |
|---|---|
| **LDF Dip Verde** | Cambio di capitolo o di luogo: la scena si chiude sul verde, la linea compare al centro, si riapre |
| **LDF Linea Apre** | La linea attraversa l'immagine e la scena nuova si apre da lì |
| **LDF Scorrimento Linea** | Spostamento orizzontale tra due luoghi o due persone, con la linea come confine |
| **LDF Tendina Linea** | Confronto "prima / dopo" o "qui / là": la linea scorre e rivela la nuova immagine |
| **LDF Dissolvenza Morbida** | La transizione di tutti i giorni, con un avvicinamento appena percepibile |

### Effetti

| Effetto | Uso |
|---|---|
| **LDF Foto Archivio** | Mettilo su una foto: diventa una stampa con bordo carta, leggermente ruotata, su verde, con movimento lento. Togli lo sfondo verde per sovrapporla a un video |
| **LDF Movimento Documentario** | Movimento lento su foto e filmati statici: avvicina, allontana o panoramica |
| **LDF Texture Carta** | Texture carta discreta, da usare su schermate grafiche, non sulle foto |
| **LDF Look Editoriale** | Armonizza materiale di fonti diverse (neri ardesia, bianchi avorio) senza cambiare il carattere della foto. Intensità di partenza 70% |
| **LDF Look Archivio B&N** | Per foto e filmati in bianco e nero: neutro, senza seppia |

In linea con il brief (§17) i look **non** sono pensati per essere applicati a tutto: usali solo quando una clip stona con le altre.

### Generatori

**LDF Sfondo Verde** e **LDF Sfondo Carta**: fondi pieni con texture minima per schermate titolo, mappe e grafiche.

## 4. Audio

I suoni (cartella `SFX/`) sono sobri, da documentario. Tienili bassi: **tra -18 e -26 dB** sotto la voce.

**Catena voce per un tono documentario** (Fairlight, tutto gratuito):

| Passaggio | Impostazione |
|---|---|
| EQ banda 1 | High-pass 80 Hz |
| EQ banda 2 | Bell 250 Hz, -2 dB (toglie il rimbombo della stanza) |
| EQ banda 3 | Bell 3 kHz, +1.5 dB (chiarezza, senza aggressività) |
| EQ banda 4 | High shelf 12 kHz, +1 dB |
| Compressor | Threshold -20 dB, Ratio 2.5:1, Attack 15 ms, Release 150 ms |
| De-Esser (Fairlight FX) | 6 kHz, 4-6 dB |
| Limiter sul Main | Ceiling -1 dB |
| Loudness finale | circa -14 LUFS integrati |
| Musica sotto la voce | -22 / -28 dB mentre si parla, più alta nelle pause |

Salva EQ e Dynamics come preset ("Voce LDF") per riusarli in ogni puntata.
