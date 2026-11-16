# Mi piace + Iscriviti: overlay animato per DaVinci Resolve

Overlay in stile YouTube con fondo trasparente: `like-iscriviti.mov`.

| | |
|---|---|
| Formato | QuickTime MOV, Apple ProRes 4444 (`ap4h`) con canale alpha |
| Pixel format | `yuva444p10le` in codifica (ffprobe lo legge come `yuva444p12le`, perché il decoder ProRes lavora a 12 bit) |
| Risoluzione / fps / durata | 1920×1080, 30 fps, 5 s (150 frame) |
| Colore | Rec.709, range video |
| Primo e ultimo frame | completamente trasparenti, quindi il loop non scatta |

## Rigenerare

```bash
./render.sh
```

Lo script installa `skia-python` e `numpy` se mancano, disegna i 150 frame e li passa a ffmpeg. Ogni frame dipende solo da `T = frame / 30`: due render producono gli stessi pixel. I font Roboto sono inclusi in `fonts/` (licenza Apache 2.0).

Servono Python 3.9 o superiore e ffmpeg. Su Linux, se `import skia` dà errore per `libEGL.so.1`, installa `libegl1` (`apt-get install libegl1`).

### Parametri

| Opzione | Default | Cosa fa |
|---|---|---|
| `--like-text` | `Mi piace` | testo della prima pillola |
| `--subscribe-text` | `Iscriviti` | testo della pillola rossa |
| `--subscribed-text` | `Iscritto` | testo dopo il clic |
| `--x` | `960` | centro orizzontale del gruppo, in px |
| `--y` | `540` | centro verticale delle pillole, in px |
| `--out` | `like-iscriviti.mov` | file di uscita |
| `--png-dir DIR` | — | salva anche la sequenza `frame_0001.png` … (RGBA) |
| `--no-mov` | — | solo PNG, senza il MOV |

Esempi:

```bash
./render.sh --like-text Like --subscribe-text Subscribe --subscribed-text Subscribed --out like-subscribe.mov
```

```bash
./render.sh --x 1350 --y 900 --out like-iscriviti-basso-destra.mov
```

Il cursore, gli anelli e le lineette si spostano insieme alle pillole. Se un testo è più lungo della pillola, la pillola si allarga e il contenuto resta centrato.

### Dalla sequenza PNG a ProRes 4444 (alternativa)

```bash
ffmpeg -framerate 30 -i frames/frame_%04d.png -vf "scale=out_color_matrix=bt709:out_range=tv,format=yuva444p10le" -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le -alpha_bits 16 -vendor apl0 -colorspace bt709 -color_primaries bt709 -color_trc bt709 like-iscriviti.mov
```

### Verifica

```bash
ffprobe -v error -show_entries stream=codec_name,profile,pix_fmt -of default=nw=1 like-iscriviti.mov
```

Deve mostrare `prores`, `4444` e un `pix_fmt` che comincia con `yuva` (la `a` è il canale alpha).

## In DaVinci Resolve

1. **Pagina Media** (o *File → Import → Media*): trascina `like-iscriviti.mov` nel Media Pool.
2. **Pagina Edit**: trascina la clip su **Video 2**, sopra il tuo video su Video 1, nel punto in cui vuoi che parta l'animazione. Se non c'è una seconda traccia, rilascia la clip nello spazio vuoto sopra Video 1 e Resolve la crea.
3. La trasparenza dovrebbe vedersi subito. Se vedi un fondo nero, nel Media Pool fai clic destro sulla clip → **Clip Attributes… → Video → Alpha Mode** e scegli **Straight**. Il file usa alpha non premoltiplicato.
4. Per spostarla o ridimensionarla usa **Inspector → Transform** (Zoom, Position), oppure rigenera il file con `--x` e `--y`, così non perdi nitidezza.

I timeline a 25 fps vanno bene: Resolve adatta la clip da 30 fps. Per avere ogni frame esatto, usa un timeline a 30 fps.

## Timeline dell'animazione (secondi)

| Tempo | Evento |
|---|---|
| 0.10–0.70 | entra «Mi piace» (scala 0.55→1, out-back, fade-in) |
| 0.25–0.85 | entra «Iscriviti» |
| 0.70–1.45 | il cursore arriva da (1560,880) a (735,585), in-out cubico, fade-in 0.7–0.9 |
| 1.50 | clic su «Mi piace»: pressione a 0.93 per 0.16 s e anello 12→52 px in 0.5 s |
| 1.56–2.00 | il pollice si riempie, ruota fino a −22° e scala fino a 1.5×; 6 lineette bianche e azzurre (0.64 s) |
| 1.70–2.60 | il cursore va su «Iscriviti» (1190,585) |
| 2.70 | clic su «Iscriviti» |
| 2.75–2.95 | rosso «Iscriviti» → grigio con campanella e «Iscritto» |
| 2.90–3.90 | la campanella oscilla di ±26°, smorzata, con perno in alto |
| 3.30–4.00 | il cursore esce in basso a destra e sparisce |
| 4.30–4.85 | le pillole scendono a scala 0.65 (ease-in) e svaniscono |
