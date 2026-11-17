# Moviola per DaVinci Resolve

Gli stessi titoli, transizioni ed effetti di **Moviola Studio**, dentro Resolve e modificabili nell'Inspector: testi, colori, durate, punti di zoom. Le foto non si mettono su un livello sopra: trascini l'effetto **sulla tua foto o sul tuo video** e lavora su quello.

Design: Anton, Inter, scrittura a mano, macchina da scrivere, Playfair Display; carta, rosso, verde campo, crocini di registro, grana.

Funziona con DaVinci Resolve 18 o successivo (anche 21 e la versione gratuita).

## Installazione (una volta sola)

1. **Font**: apri la cartella `Font` e fai doppio clic su ogni file → *Installa*. Senza i font i titoli escono con un carattere di ripiego.
2. **Template**: chiudi Resolve, fai doppio clic su `Moviola.drfx` (o trascinalo nella finestra di Resolve) e scegli *Install*. Riapri Resolve.

In alternativa `Installa Moviola.command` fa entrambe le cose da solo.

**Progetti a 60 fps**: installa anche `Moviola-60fps.drfx` (cartella *Moviola 60fps*, nomi con "60fps"). I tempi sono tarati su 25 fps; a 30 fps vanno bene i normali.

Nella **Effects Library** cerca **MOV**.

## Dove si trovano e come si usano

| Tipo | Dove | Come |
|---|---|---|
| **Titoli** (16) | Toolbox → Titles → Fusion Titles | Su una traccia **sopra** la clip (V2). Allunga o accorcia: l'uscita segue sempre la fine della clip |
| **Transizioni** (6) | Toolbox → Video Transitions → Fusion Transitions | Sul **taglio** tra due clip. 12–25 fotogrammi |
| **Effetti** (8) | Toolbox → Effects | **Sulla clip** (la tua foto o il tuo video) |

### Titoli
- **MOV Apertura**: titolo del documentario (2 righe), occhiello, sottotitolo, filo rosso, riflesso di luce, cornice di registro. Sfondo trasparente, verde campo, nero o carta.
- **MOV Capitolo**: numero contornato che si riempie, etichetta, titolo in corsivo, data.
- **MOV Citazione**: virgolette, testo che passa da sfocato a nitido, sottolineatura a pennarello. *Posizione sottolineatura* si trascina nel viewer; scegli lunghezza e fotogramma in cui parte.
- **MOV Macchina da Scrivere**: testo battuto lettera per lettera con cursore; striscia di carta corta, media, lunga o sul video. Regola le lettere al secondo.
- **MOV Impatto Trailer**: fino a 4 battute (una per riga) che sbattono a ritmo. Imposta *Fotogrammi per battuta* sul tempo della musica (a 25 fps: 1500 ÷ BPM).
- **MOV Sottopancia** Cinema, Archivio, Minimale, Televisivo. *Posizione* sposta tutto (anche a destra).
- **MOV Luogo e Data**: lettere che si decifrano, coordinate che scorrono, mirino.
- **MOV Numero Gigante**: conta fino al valore (es. `1.257` o `0,61`), con prefisso e suffisso.
- **MOV Tabellino**: squadre, colori, marcatori (uno per riga, con il minuto: `Mazzola 15'`). I gol entrano in ordine di minuto e il punteggio scatta da solo.
- **MOV Classifica**: righe `Squadra|punti` (max 8), riga in evidenza.
- **MOV Testa a Testa**: righe `Statistica|sinistra|destra` (max 5); il migliore di ogni riga si illumina.
- **MOV Cornice Archivio**: dicitura, fonte, anno, bande cinema.
- **MOV Mirino REC**: angoli, REC, timecode, parametri.

### Transizioni
**Bruciatura Pellicola**, **Strappo di Carta**, **Luce Calda**, **Flash Magnesio**, **Barre del Canale** (con scritta sul taglio), **Disturbo VHS**.

### Effetti (sulla clip)
- **MOV Zoom sul Dettaglio**: trascina il *Punto* nel viewer sul giocatore; la camera entra, il resto si scurisce, cerchio a pennarello e nota scritta a mano.
- **MOV Ken Burns**: *Punto di partenza* e *Punto di arrivo* nel viewer, zoom iniziale e finale, rotazione, respiro.
- **MOV Zoom a Scatti**: scatti verso il punto con scia, scossa e lampo.
- **MOV Isola il Giocatore**: trascina *Piedi del giocatore* sui suoi piedi e regola l'altezza; anello, filo, cartellino.
- **MOV Foto sul Tavolo**: la tua foto diventa la cartolina d'archivio che cade sul tavolo, con data e luogo scritti a mano.
- **MOV Scheda Giocatore**: mettilo sul **ritratto**: cornice, numero di maglia gigante, nome, ruolo, statistiche (`Nome|valore`). *Posizione foto nella cornice* e *Ingrandimento foto* per inquadrare il viso.
- **MOV Pellicola Epoca**: tono, grana, polvere, graffi, sfarfallio, bordi bruciati, vignetta.
- **MOV Videocassetta**: linee, disturbo, PLAY, data e ora che avanzano.

Gli effetti con foto hanno il controllo **Tono**: originale, bianco e nero, seppia, duotono verde.

## Effetti sonori
Cartella `SFX`: whoosh, impatto, riser, macchina da scrivere, campanello, otturatore, disturbo VHS, pop, click. Trascinali dal Media Pool su una traccia audio.

## Se qualcosa non torna
Questi template sono stati costruiti e verificati con un simulatore di Fusion, non dentro Resolve. Se un elemento appare nel posto sbagliato, troppo grande o troppo piccolo, scrivimi quale template e cosa vedi (meglio con uno screenshot): si corregge in fretta.
