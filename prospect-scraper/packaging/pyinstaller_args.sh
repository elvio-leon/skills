# Argomenti PyInstaller comuni (build Mac e build di prova su Linux).
# Uso: ROOT=<cartella progetto>; source packaging/pyinstaller_args.sh; pyinstaller "${PYI_ARGS[@]}" ...
# Streamlit esegue app.py come script: va incluso come file, insieme a config e schema DB.
# anthropic e il pacchetto qualify (importati in modo pigro) vanno raccolti esplicitamente.
# uvicorn e phonenumbers caricano moduli per nome: vanno raccolti esplicitamente.
PYI_ARGS=(
  --add-data "$ROOT/app.py:."
  --add-data "$ROOT/.streamlit/config.toml:.streamlit"
  --add-data "$ROOT/database/schema.sql:database"
  --add-data "$ROOT/config/agency_blacklist.txt:config"
  --add-data "$ROOT/config/agency_scoring.toml:config"
  --collect-all streamlit
  --collect-submodules uvicorn
  --collect-submodules phonenumbers
  --collect-submodules anthropic
  --collect-submodules qualify
  --copy-metadata streamlit
  --exclude-module playwright
  --exclude-module pytest
  --exclude-module tkinter
)
