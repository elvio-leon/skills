# SilenceCut per DaVinci Resolve (Mac)

Taglia in automatico le pause dalle tue clip e crea una **nuova timeline** con solo le parti parlate. Le clip originali non vengono toccate: ogni pezzo in timeline resta collegato al file sorgente, quindi puoi allungarlo, accorciarlo o recuperare un taglio con il trim.

Flusso di lavoro: importi il girato, lanci SilenceCut, ottieni una timeline già "sgrossata" e da lì scegli tu le take migliori ed elimini le altre.

## Installazione (una volta sola)

1. **ffmpeg**: apri il Terminale ed esegui `brew install ffmpeg` (se non hai Homebrew: https://brew.sh).
2. Copia **`SilenceCut.lua`** in
   `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility/`
   (nel Finder: Cmd + Shift + G e incolla il percorso), oppure fai doppio clic su `Installa.command`.
3. Riavvia DaVinci Resolve.

La versione Lua non richiede Python: Lua è integrato in Resolve. `SilenceCut.py` fa le stesse cose, ma Resolve lo mostra solo se trova una versione di Python che supporta.

## Uso dentro Resolve

1. Apri la **timeline** che hai montato. Va bene anche con video del telefono su V1/A1 e microfono esterno su A2, già sincronizzati.
2. *(Facoltativo, Resolve 21.0.4 o successivo)* Seleziona in timeline le clip da tagliare. Se non selezioni niente, o la tua versione non lo supporta, lavora su tutta la timeline.
3. Menu **Workspace → Scripts → SilenceCut**.
4. Scegli **su quale traccia audio cercare il parlato**: di solito il microfono, che viene già proposto.
5. Scegli il preset:
   | Preset | Quando usarlo |
   |---|---|
   | **Delicato** | parlato lento e ragionato, vuoi tenere i respiri |
   | **Normale** | la maggior parte dei casi (talking head, tutorial) |
   | **Aggressivo** | ritmo serrato stile YouTube/Reels/TikTok |
6. Viene creata una nuova timeline `… - SilenceCut`. Il taglio è applicato a **tutte le tracce nello stesso punto** (video, audio del telefono, microfono), quindi resta tutto a sync, e i pezzi di ogni frase sono collegati tra loro. La timeline originale non viene toccata.

Senza nessuna timeline aperta, lo script lavora sulle clip selezionate nel Media Pool, prese per intero.

I dettagli dell'analisi compaiono in **Workspace → Console** (scheda Lua).

## Regolazioni

In cima a `SilenceCut.lua` (o `SilenceCut.py`) trovi i preset. I valori principali:

- `noise_db`: sotto questo volume è "silenzio". Se taglia parole sussurrate, abbassalo (es. -40); se lascia pause con rumore di fondo, alzalo (es. -30).
- `min_silence`: pausa minima (in secondi) da tagliare.
- `pad_before` / `pad_after`: margine lasciato prima e dopo ogni frase, così non tronca l'attacco o la coda delle parole.

Dopo una modifica, ricopia lo script nella cartella `Utility` e riavvia Resolve.

## Alternativa da Terminale (FCPXML)

Senza aprire Resolve puoi anche generare la timeline da Terminale e importarla:

```bash
python3 SilenceCut.py clip1.mov clip2.mov -p Normale -o tagliato.fcpxml
```

In Resolve: **File → Import → Timeline…** e scegli `tagliato.fcpxml`. Opzioni extra: `--noise -38`, `--min-silence 0.4`, `--pad 0.15`.

## Limiti

- Se hai sincronizzato il microfono **dentro la clip** nel Media Pool (Auto Sync Audio), lo script legge solo l'audio originale del file video. Meglio tenere il microfono su una traccia separata in timeline.
- Titoli, generatori ed effetti non vengono copiati nella nuova timeline: aggiungili dopo il taglio.
- Clip con velocità modificata (retime) non sono gestite.
- La versione Python (`SilenceCut.py`) lavora solo sulle clip del Media Pool; la versione Lua è quella completa.
- Rileva il silenzio dal volume, non dal significato: le take ripetute o sbagliate le scegli tu, ed è proprio quello che resta da fare.
