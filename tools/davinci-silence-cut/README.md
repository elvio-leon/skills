# SilenceCut per DaVinci Resolve (Mac)

Taglia in automatico le pause dalle tue clip e crea una **nuova timeline** con solo le parti parlate. Le clip originali non vengono toccate: ogni pezzo in timeline resta collegato al file sorgente, quindi puoi allungarlo, accorciarlo o recuperare un taglio con il trim.

Flusso di lavoro: importi il girato, lanci SilenceCut, ottieni una timeline già "sgrossata" e da lì scegli tu le take migliori ed elimini le altre.

## Installazione (una volta sola)

1. **ffmpeg**: apri il Terminale ed esegui `brew install ffmpeg` (se non hai Homebrew: https://brew.sh).
2. **Python 3**: se non è già installato, scaricalo da https://www.python.org/downloads/macos/ (Resolve usa quello).
3. Fai doppio clic su **`Installa.command`**. Se macOS lo blocca: tasto destro → Apri.
4. Riavvia DaVinci Resolve.

## Uso dentro Resolve

1. Nel **Media Pool** seleziona una o più clip (se non selezioni niente, usa tutte quelle della cartella aperta).
2. Menu **Workspace → Scripts → Edit → SilenceCut**.
3. Scegli il preset:
   | Preset | Quando usarlo |
   |---|---|
   | **Delicato** | parlato lento e ragionato, vuoi tenere i respiri |
   | **Normale** | la maggior parte dei casi (talking head, tutorial) |
   | **Aggressivo** | ritmo serrato stile YouTube/Reels/TikTok |
4. Si apre la pagina Edit con la timeline `SilenceCut - …` pronta. Se hai selezionato più clip, sono una dopo l'altra, colorate in modo diverso per file di origine.

I dettagli dell'analisi compaiono in **Workspace → Console**.

## Regolazioni

In cima a `SilenceCut.py` trovi i preset. I valori principali:

- `noise_db`: sotto questo volume è "silenzio". Se taglia parole sussurrate, abbassalo (es. -40); se lascia pause con rumore di fondo, alzalo (es. -30).
- `min_silence`: pausa minima (in secondi) da tagliare.
- `pad_before` / `pad_after`: margine lasciato prima e dopo ogni frase, così non tronca l'attacco o la coda delle parole.

Dopo una modifica, ricopia lo script con `Installa.command`.

## Alternativa da Terminale (FCPXML)

Se lo script non compare nel menu Scripts, puoi generare la timeline da Terminale e importarla:

```bash
python3 SilenceCut.py clip1.mov clip2.mov -p Normale -o tagliato.fcpxml
```

In Resolve: **File → Import → Timeline…** e scegli `tagliato.fcpxml`. Opzioni extra: `--noise -38`, `--min-silence 0.4`, `--pad 0.15`.

## Limiti

- Analizza la **prima traccia audio** del file (`AUDIO_STREAM` in cima allo script). Se registri l'audio con un recorder esterno, sincronizza e usa un file che contenga quell'audio, oppure imposta la traccia giusta.
- Rileva il silenzio dal volume, non dal significato: le take ripetute o sbagliate le scegli tu, ed è proprio quello che resta da fare.
