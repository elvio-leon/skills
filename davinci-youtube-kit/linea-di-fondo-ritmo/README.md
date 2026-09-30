# Linea di Fondo Ritmo: il pack per le parti intense

Il pack principale di Linea di Fondo è lento di proposito. Questo è il suo complemento per i momenti forti (il gol, la rivelazione, il dato che colpisce): **zoom stile social veloci e regolabili**, transizioni rapide, colpi di luce e di fuoco, e titoli che arrivano di scatto.

L'identità resta la stessa: verde `#183A2F`, avorio `#F5EFE6`, terracotta `#B5323C`, la linea come elemento ricorrente. Niente glitch, niente RGB split, niente colori estranei al brand.

Tutti i testi usano **Optima**, già disponibile in DaVinci Resolve: non c'è niente da installare.

Funziona con DaVinci Resolve 18 o successivo, compresa la versione 21 e la versione gratuita. Elenco completo: **[CATALOGO.md](CATALOGO.md)**.

## Installazione

Fai doppio clic su `LineaDiFondoRitmo.drfx` (oppure trascinalo nella finestra di Resolve), scegli *Install* e riavvia Resolve.

In alternativa estrai `LineaDiFondoRitmo-completo.zip` e lancia `installa_windows.bat` o `installa_mac.command`.

Nella **Effects Library** cerca **`LDF`**. Gli elementi di questo pack sono nella cartella *Linea di Fondo Ritmo*.

## Gli zoom social

Trascina lo zoom **sopra la clip** (non su una traccia separata). Tutti e sei gli zoom sono lo stesso effetto con impostazioni di partenza diverse: da ognuno puoi arrivare a tutti gli altri cambiando i controlli nell'Inspector.

| Zoom | Cosa fa di default | Quando |
|---|---|---|
| **LDF Zoom Social** | 100 → 130% in 8 frame, parte veloce e si ferma pulito | La base: enfasi su una frase o su un'azione |
| **LDF Zoom Punch-In** | 100 → 118% in 2 frame | Stacco secco sul viso, al posto di un jump cut |
| **LDF Zoom Colpo** | Entra al 140% con rimbalzo e scossa, tiene 12 frame, torna | Il momento clou, il gol, la battuta |
| **LDF Zoom Scalini** | Tre scatti da +15% ogni 12 frame | Tensione che sale, elenco di tre cose |
| **LDF Zoom Battito** | Pulsa al 106% ogni 15 frame | A tempo di musica, cori, battito |
| **LDF Zoom Rivelazione** | Parte al 160% su un dettaglio e si apre al 100% | Svelare la scena, il luogo, la folla |

### Tutti i controlli

| Controllo | A cosa serve |
|---|---|
| **Punto di zoom** | Il punto che resta fermo mentre si zooma. Trascinalo nel viewer sul viso o sul pallone |
| **Sposta inquadratura** | Riposiziona l'immagine (utile quando sei già zoomato) |
| **Andamento** | *Zoom e resta* / *Zoom e ritorno a fine clip* / *Colpo: entra e torna* / *Parte zoomato e si allarga* / *Zoom a scalini* / *Battito a ritmo* |
| **Zoom normale (%)** | Da dove parte (di solito 100) |
| **Zoom massimo (%)** | Dove arriva. 110-120 discreto, 130-150 deciso, oltre 180 estremo |
| **Inizia dopo (frame)** | Ritarda lo zoom rispetto all'inizio della clip, per farlo cadere sulla parola giusta |
| **Durata zoom (frame)** | La velocità: 0 = istantaneo, 2-4 = scatto, 6-10 = social, 15+ = più morbido |
| **Curva** | *Scatto* parte veloce e si ferma pulito (la più "social"); *Morbida* accelera e frena; *Accelera* parte lenta e finisce di colpo; *Lineare*; *Con rimbalzo* supera il valore e ci torna |
| **Quantità rimbalzo** | Solo con la curva *Con rimbalzo*: 0,5 appena percepibile, 1,5 evidente, 3 cartoon |
| **Tenuta prima del ritorno** | *Colpo* e *Battito*: quanti frame resta zoomato prima di tornare |
| **Durata ritorno** | *Colpo*, *Battito* e *ritorno a fine clip*: velocità del ritorno |
| **Numero di scalini** | *Zoom a scalini*: in quanti passi arriva allo zoom massimo |
| **Frame tra scalini / battiti** | Il ritmo. A 25 fps: 12 frame circa mezzo secondo. Per andare a tempo con la musica: 60 × fps / BPM (a 120 BPM e 25 fps = 12,5) |
| **Inclinazione (gradi)** | Ruota leggermente mentre zooma (2-4 gradi per un effetto dinamico) |
| **Scossa all'arrivo** | Piccolo tremolio che si smorza appena lo zoom arriva. 0 = nessuno, 0,5 leggero, 1,5 forte |
| **Sfocatura di movimento** | Mosso radiale durante lo zoom: rende lo scatto più fluido. 0 = nitido |

**Suggerimenti**
- Per un colpo preciso sulla parola: taglia la clip dove inizia la parola e metti lo zoom sulla parte dopo, oppure usa *Inizia dopo*.
- Per zoomare su una clip e tornare sulla successiva basta tagliare: ogni pezzo ha il suo effetto indipendente.
- Più zoom in fila stancano. Nella stessa scena alterna Punch-In e inquadratura normale.

## Altri effetti

| Effetto | Uso | Controlli principali |
|---|---|---|
| **LDF Scossa** | Impatto, esultanza, esplosione di gioia | Intensità, velocità, durata (0 = tutta la clip), zoom anti-bordi |
| **LDF Flash Colpo** | Lampo avorio e sovraesposizione all'inizio della clip | Inizio, durata, intensità, colore |
| **LDF Fuoco Rapido** | La clip parte sfocata e si mette a fuoco di scatto | Sfocatura, durata, assestamento zoom, sfocatura anche in uscita |
| **LDF Evidenzia Giocatore** | Isola un giocatore: il resto si scurisce, perde colore e vira al verde, con anello terracotta | Posizione (animabile con i keyframe per seguirlo), dimensione, forma, quanto scurire |
| **LDF Look Tensione** | Contrasto deciso, colore trattenuto, ombre verso il verde, pelle protetta | Intensità (default 80%) |

Per far seguire l'anello a un giocatore che si muove: in Inspector metti un keyframe su **Posizione giocatore** all'inizio, vai avanti di qualche frame, sposta il punto, e ripeti.

## Transizioni

Durate consigliate: **6-12 frame**.

| Transizione | Uso |
|---|---|
| **LDF Zoom Passaggio** | Zoom attraverso il taglio, in avanti o indietro, con punto di zoom, rotazione e lampo avorio opzionali |
| **LDF Frusta** | Panoramica a frusta nelle 4 direzioni (scegli dal menu Direzione) |
| **LDF Lampo Avorio** | Lampo sul taglio e piccolo scatto sulla clip nuova |
| **LDF Linea Veloce** | La linea terracotta attraversa lo schermo e rivela la scena con una leggera spinta |

## Titoli (Optima)

Mettili su una traccia **sopra** la clip. Ogni titolo ha **Durata animazioni** (1 = normale, 0,5 = più scattante, 2 = più lenta), **Durata uscita** e **Ombra per leggibilità su video**. Nel campo **Stile** puoi passare tra Regular, Italic, Bold ed ExtraBlack.

| Titolo | Uso |
|---|---|
| **LDF Parola Chiave** | Una parola grande che arriva di scatto con la linea sotto ("DECISIVO", "1986", "MAI") |
| **LDF Didascalie** | Sottotitoli parola per parola in stile social, con riquadro terracotta. Scrivi la frase nel campo *Frase* |
| **LDF Numero Impatto** | Un numero che corre fino al dato e batte un colpo (spettatori, gol, anni, cifre) |
| **LDF Titolo Colpo** | Titolo di capitolo che si stringe e si mette a fuoco di colpo |
| **LDF Testo Rivelato** | Il titolo esce da sopra la linea e il sottotitolo da sotto |
| **LDF Citazione** | Una frase detta da qualcuno, in corsivo, con virgolette terracotta e autore |
| **LDF Tabellino** | Il risultato: squadra, punteggio, squadra, competizione |
| **LDF Minuto** | Minuto ed evento (51' GOL, nome del giocatore) in basso a sinistra |

## Suoni

Nella cartella `SFX/` trovi 10 suoni pensati per questi effetti: punch-in, colpo di zoom, battito, frusta, whoosh rapido, lampo, riser breve, colpo basso, conteggio e colpo per i testi. Tienili tra **-14 e -22 dB** sotto la voce: qui possono essere un po' più presenti rispetto al pack documentario.
