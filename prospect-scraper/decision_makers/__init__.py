"""Contatti dei decisori delle agenzie qualificate (pulsante «Trova contatti»).

Moduli: ``models`` (esito salvato nel database), ``extract`` (pagine del sito -> persone con
ruolo di vertice, estratte con l'AI e verificate sul testo), ``linkedin`` (profilo personale dai
SOLI risultati di ricerca: URL e titolo, le pagine linkedin.com non vengono mai aperte), ``email``
(email nominativa trovata sul sito, altrimenti ipotesi nome@dominio da verificare) e ``finder``
(orchestrazione per una agenzia, non solleva mai).
"""
