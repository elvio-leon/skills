# Template DaVinci Resolve: «Mi piace Iscriviti»

Un titolo Fusion da trascinare sulla timeline. Testi e colori si cambiano dall'Inspector, senza rigenerare niente.

Rispetto al video `like-iscriviti.mov`, l'animazione e i tempi sono gli stessi. Il template:

- funziona a qualsiasi risoluzione 16:9 (HD, 4K) e a qualsiasi frame rate, perché i tempi sono in secondi;
- allarga le pillole se il testo è più lungo, mantenendo il gruppo centrato;
- non pesa 15 MB, ma è più pesante da riprodurre in timeline di un ProRes.

> Non l'ho potuto aprire in DaVinci Resolve: è scritto a mano e verificato offline (vedi «Verifica» sotto). Se qualcosa non si vede bene, manda uno screenshot.

## Installazione (Mac)

Servono due cose: il template e il font Roboto. Se manca il font, DaVinci ne usa un altro e le scritte cambiano aspetto.

**Metodo 1, script:** apri il Terminale, scrivi `bash ` (con lo spazio), trascina dentro `install-mac.sh` e premi Invio. Copia il template in
`~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Templates/Edit/Titles/Like e Iscriviti/`
e i font in `~/Library/Fonts/`.

**Metodo 2, a mano:**
1. Fai doppio clic su `Roboto-Medium.ttf` e `Roboto-Bold.ttf` (cartella `fonts`) → **Installa font**.
2. Fai doppio clic su `Mi piace Iscriviti.drfx`. DaVinci si apre e chiede conferma per installare il pacchetto.

Usa un solo metodo, altrimenti il titolo compare due volte.

Poi **chiudi e riapri DaVinci Resolve**.

## Uso

1. Pagina **Edit** → **Effects** → **Titles** → sezione **Fusion Titles** → «Mi piace Iscriviti».
2. Trascinalo su una traccia **sopra** il tuo video (es. Video 2). Dura 5 secondi; se lo allunghi, dopo i 5 s resta trasparente.
3. Selezionalo e apri l'**Inspector** → scheda **Title**:

| Controllo | Default |
|---|---|
| Testo Mi piace | Mi piace |
| Testo Iscriviti | Iscriviti |
| Testo Iscritto | Iscritto |
| Colore Mi piace | #272727 |
| Colore Iscriviti | #FF0000 |
| Colore Iscritto | #272727 |
| Colore testo e icone | bianco |
| Colore lineette | #3EA6FF |
| Posizione | centro (0.5, 0.5) |
| Dimensione | 1 |

Per la versione inglese basta scrivere «Like», «Subscribe», «Subscribed».

## Rigenerare il template

```bash
python3 davinci/build_template.py --check
```

Rigenera `.setting`, `.png` e `.drfx` partendo dalle stesse icone e dalla stessa timeline di `render.py`, poi lancia la verifica.

## Verifica (offline)

`check_template.py` controlla, senza DaVinci:

- che il `.setting` si legga come tabella Lua, con `Input { }` e `InstanceInput { }` corretti e collegamenti a nodi esistenti;
- che tutte le 55 espressioni compilino ed eseguano con **LuaJIT** (il motore di Fusion), su tutti i frame a 30 e 25 fps;
- che scala, opacità, posizioni del cursore, rotazione del pollice, oscillazione della campanella, crossfade e anello coincidano con `render.py` frame per frame;
- che con testi lunghi le pillole si allarghino restando centrate;
- che le forme (pollice, campanella, cursore) siano giuste, ridisegnandole in `check-forme.png`.

Non può verificare come Fusion disegna davvero i nodi. I punti più a rischio:

- **Dimensione del testo:** Text+ usa unità relative alla larghezza del frame. Ho convertito i 44 px con le metriche di Roboto, ma potrebbe venire un po' più grande o più piccolo.
- **Posizione verticale del testo:** può spostarsi di qualche pixel rispetto al video.
- **Ombre:** la morbidezza è un'approssimazione del blur da 22 px.

## Come è costruito

- Pillole: `Background` + `RectangleMask` (CornerRadius 1), ombra con una seconda maschera sfumata.
- Testi: `Text+` Roboto; la larghezza viene letta dal `DataWindow` del nodo.
- Icone e cursore: `PolylineMask` con i contorni delle icone Lucide calcolati con Skia (contorno, pieno, fori in Subtract).
- Animazione: espressioni Lua su `Merge` / `Transform` / `Dissolve` che leggono `time / fps` della timeline.
