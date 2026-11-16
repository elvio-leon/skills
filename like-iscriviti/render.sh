#!/usr/bin/env bash
# Rigenera like-iscriviti.mov (ProRes 4444 + alpha). Argomenti extra passati a render.py,
# es.:  ./render.sh --like-text Like --subscribe-text Subscribe --subscribed-text Subscribed --out like-subscribe.mov
set -euo pipefail
cd "$(dirname "$0")"
python3 -c "import skia, numpy" 2>/dev/null || python3 -m pip install -q -r requirements.txt
python3 render.py "$@"
