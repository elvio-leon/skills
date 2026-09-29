#!/bin/bash
# Avvio di Prospect Scraper con doppio clic (macOS)
cd "$(dirname "$0")" || exit 1
PY="$(command -v python3.13 || command -v python3.12 || command -v python3.11 || command -v python3)"
if [ -z "$PY" ]; then
  osascript -e 'display alert "Python non trovato" message "Installa Python 3.11 o superiore da python.org, poi riapri Prospect Scraper."' >/dev/null 2>&1
  open "https://www.python.org/downloads/"
  exit 1
fi
if ! "$PY" launcher.py; then
  echo
  read -r -p "Si è verificato un errore. Premi Invio per chiudere."
  exit 1
fi
