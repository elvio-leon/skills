#!/bin/bash
# Avvio di Prospect Scraper con doppio clic (Linux)
cd "$(dirname "$0")" || exit 1
PY="$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)"
if [ -z "$PY" ]; then
  echo "Python 3.11 o superiore non trovato: installalo con il gestore pacchetti."
  exit 1
fi
exec "$PY" launcher.py
