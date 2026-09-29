# Argomenti PyInstaller comuni (build Mac e build di prova su Linux).
# Uso: ROOT=<cartella progetto>; source packaging/pyinstaller_args.sh; pyinstaller "${PYI_ARGS[@]}" ...
# Streamlit esegue app.py come script: va incluso come file, insieme a config e schema DB.
# uvicorn e phonenumbers caricano moduli per nome: vanno raccolti esplicitamente.
PYI_ARGS=(
  --add-data "$ROOT/app.py:."
  --add-data "$ROOT/.streamlit/config.toml:.streamlit"
  --add-data "$ROOT/database/schema.sql:database"
  --collect-all streamlit
  --collect-submodules uvicorn
  --collect-submodules phonenumbers
  --copy-metadata streamlit
  --exclude-module playwright
  --exclude-module pytest
  --exclude-module tkinter
)
