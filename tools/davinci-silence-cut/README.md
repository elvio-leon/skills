# SilenceCut per DaVinci Resolve (Mac)

Taglia in automatico le pause dalle tue clip e crea una **nuova timeline** con solo le parti parlate. Le clip originali non vengono toccate: ogni pezzo in timeline resta collegato al file sorgente, quindi puoi allungarlo, accorciarlo o recuperare un taglio con il trim.

Flusso di lavoro: importi il girato, lanci SilenceCut, ottieni una timeline già "sgrossata" e da lì scegli tu le take migliori ed elimini le altre.

## Installazione (una volta sola)

1. Se non l'hai già: `brew install ffmpeg` nel Terminale.
2. Scarica `Installa-SilenceCut.command` ed eseguilo nel Terminale:
   `bash ~/Downloads/Installa-SilenceCut.command`
3. Si apre una finestra con l'app **SilenceCut Analizza**: trascinala nel Dock.
4. Riavvia DaVinci Resolve.

## Uso di tutti i giorni

1. **Una volta per ogni girato**: trascina la cartella del girato (o i file del microfono) sull'app **SilenceCut Analizza** nel Dock. Analizza l'audio di tutti i file; quelli già analizzati vengono saltati.
2. **In Resolve**: apri la timeline (V1/A1 telefono, A2 microfono, già sincronizzati) e scegli **Workspace → Scripts → SilenceCut** (oppure *SilenceCut Aggressivo* / *SilenceCut Delicato*).
3. Si crea una nuova timeline `… - SilenceCut`, tagliata su tutte le tracce nello stesso punto. Il parlato viene cercato sull'audio del telefono (quello registrato col video), che di solito ha pause più pulite del microfono. Per usare il microfono: in Console scrivi `SC_DETECT="microfono";` prima di `dofile(...)`, oppure cambia `DETECT_ON` in cima a `SilenceCut.lua`. La timeline originale non viene toccata.

Se dimentichi il passo 1, lo script mette un **marker rosso** all'inizio della timeline con il promemoria (e scrive i dettagli in Workspace → Console). Il marker sparisce quando il taglio riesce.

Perché serve l'app esterna: questa versione di Resolve non permette agli script di avviare programmi come ffmpeg, quindi l'analisi dell'audio si fa fuori da Resolve.

## Regolazioni

In cima a `SilenceCut.lua` (o `SilenceCut.py`) trovi i preset. I valori principali:

- `noise_db`: sotto questo volume è "silenzio". Se taglia parole sussurrate, abbassalo (es. -40); se lascia pause con rumore di fondo, alzalo (es. -30).
- `min_silence`: pausa minima (in secondi) da tagliare.
- `pad_before` / `pad_after`: margine lasciato prima e dopo ogni frase, così non tronca l'attacco o la coda delle parole.

Dopo una modifica a `SilenceCut.lua` o `analizza.sh`, rigenera l'installer con `python3 crea-installer.py`.

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
