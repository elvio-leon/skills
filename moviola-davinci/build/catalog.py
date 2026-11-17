"""Elenco dei template del pack Moviola: (categoria, nome, costruttore, descrizione, opzioni)."""
from __future__ import annotations

import altri as A
import titoli as T

ALL = [
    ("Titles", "MOV Apertura", T.t_apertura, "Il titolo del documentario: righe che salgono da una maschera, filo rosso, riflesso di luce sulle lettere, cornice di registro.", {"len": 160}),
    ("Titles", "MOV Capitolo", T.t_capitolo, "Cartello di capitolo: il numero appare a contorno e si riempie di colore dal basso, titolo in corsivo editoriale.", {"len": 150}),
    ("Titles", "MOV Citazione", T.t_citazione, "Citazione a tutto schermo con virgolette grandi, testo che passa da sfocato a nitido e sottolineatura a pennarello.", {"len": 175}),
    ("Titles", "MOV Macchina da Scrivere", T.t_macchina, "Testo battuto lettera per lettera con cursore, su striscia di carta strappata o direttamente sul video.", {"len": 150}),
    ("Titles", "MOV Impatto Trailer", T.t_impatto, "Parole che sbattono a schermo a ritmo, con scia, lampo e scossa. Per il gancio iniziale.", {"len": 120, "frames": [0.14, 0.2, 0.45, 0.8]}),
    ("Titles", "MOV Sottopancia Cinema", T.t_sott_cinema, "Nome e ruolo: barra rossa, nome in Anton che esce da una maschera.", {"len": 140}),
    ("Titles", "MOV Sottopancia Archivio", T.t_sott_archivio, "Cartellino di carta strappata con nastro, nome scritto a mano e sottolineato.", {"len": 140}),
    ("Titles", "MOV Sottopancia Minimale", T.t_sott_minimale, "Nome e ruolo essenziali con filo sottile e crocino di registro.", {"len": 140}),
    ("Titles", "MOV Sottopancia Televisivo", T.t_sott_tv, "Due riquadri obliqui stile telegiornale: carta per il nome, rosso per il ruolo.", {"len": 140}),
    ("Titles", "MOV Luogo e Data", T.t_luogo, "Luogo, data e coordinate che si decifrano lettera per lettera, con mirino.", {"len": 150}),
    ("Titles", "MOV Numero Gigante", A.t_numero, "Un numero che fa notizia: conta fino al valore con frenata finale, etichetta e nota.", {"len": 150}),
    ("Titles", "MOV Tabellino", A.t_tabellino, "Risultato con marcatori che entrano in ordine di minuto: a ogni gol il punteggio scatta. Tabellone o cartoncino.", {"len": 180}),
    ("Titles", "MOV Classifica", A.t_classifica, "Classifica a righe che entrano in sequenza, squadra protagonista evidenziata in rosso.", {"len": 160}),
    ("Titles", "MOV Testa a Testa", A.t_confronto, "Confronto tra due giocatori o squadre: barre dal centro, valori che contano, il migliore evidenziato.", {"len": 175}),
    ("Titles", "MOV Cornice Archivio", A.t_cornice, "Cornice di registro con dicitura di materiale d'archivio, fonte, anno e bande cinema opzionali.", {"len": 120}),
    ("Titles", "MOV Mirino REC", A.t_mirino, "Interfaccia di telecamera: angoli, REC che lampeggia, timecode che scorre, messa a fuoco.", {"len": 120}),
    ("Transitions", "MOV Bruciatura Pellicola", A.tr_pellicola, "La pellicola si incendia dal bordo e il nucleo bianco copre lo stacco.", {"len": 40, "frames": [0.25, 0.4, 0.5, 0.7]}),
    ("Transitions", "MOV Strappo di Carta", A.tr_carta, "Un foglio entra, copre e si strappa a metà rivelando la clip successiva.", {"len": 36, "frames": [0.25, 0.45, 0.6, 0.8]}),
    ("Transitions", "MOV Luce Calda", A.tr_luce, "Infiltrazione di luce da pellicola che sbianca lo stacco.", {"len": 50, "frames": [0.25, 0.45, 0.5, 0.75]}),
    ("Transitions", "MOV Flash Magnesio", A.tr_flash, "Il lampo dei fotografi d'epoca con alone caldo e fumo.", {"len": 30, "frames": [0.05, 0.1, 0.3, 0.7]}),
    ("Transitions", "MOV Barre del Canale", A.tr_barre, "Barre oblique nei colori del canale con scritta sul taglio.", {"len": 32, "frames": [0.2, 0.4, 0.5, 0.75]}),
    ("Transitions", "MOV Disturbo VHS", A.tr_vhs, "Salto di nastro: neve, bande colorate e scossa orizzontale sul taglio.", {"len": 28, "frames": [0.25, 0.45, 0.5, 0.7]}),
    ("Effects", "MOV Pellicola Epoca", A.fx_pellicola, "Look pellicola d'epoca: tono, grana, polvere, graffi, sfarfallio, bordi bruciati, vignetta.", {"len": 100}),
    ("Effects", "MOV Videocassetta", A.fx_vhs, "Registrazione su nastro con linee, banda di disturbo, testina e scritte PLAY, data e ora.", {"len": 100}),
    ("Effects", "MOV Zoom sul Dettaglio", A.fx_dettaglio, "La camera entra nella foto fino al punto scelto, il resto si scurisce, cerchio a pennarello e nota a mano.", {"len": 160}),
    ("Effects", "MOV Ken Burns", A.fx_kenburns, "Movimento lento fatto bene: punto di partenza e arrivo, zoom, rotazione, respiro di camera a mano.", {"len": 200}),
    ("Effects", "MOV Zoom a Scatti", A.fx_scatti, "Tre colpi di zoom secchi verso il punto con scia, scossa e lampo.", {"len": 100}),
    ("Effects", "MOV Isola il Giocatore", A.fx_isola, "Analisi da moviola: campo scurito, anello sotto i piedi, filo e cartellino con nome e ruolo.", {"len": 140}),
    ("Effects", "MOV Foto sul Tavolo", A.fx_cartolina, "La foto diventa una cartolina d'archivio che cade sul tavolo verde, con data e luogo scritti a mano.", {"len": 150}),
    ("Effects", "MOV Scheda Giocatore", A.fx_scheda, "Applicalo al ritratto: foto in duotono incorniciata, numero di maglia gigante, nome, ruolo, statistiche che contano.", {"len": 170}),
]
