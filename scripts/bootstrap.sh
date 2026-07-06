#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
if [ -f .venv/Scripts/activate ]; then
  # shellcheck disable=SC1091
  source .venv/Scripts/activate
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
pip install -r requirements.txt
npm install
mkdir -p data/music backend/static/generated/covers backend/static/generated/tts backend/static/generated/clips
python - <<'PY'
from backend.art.cover_generator import generate_covers
from backend.config import Settings
from backend.database import init_db
settings = Settings.from_env()
init_db(settings)
generate_covers(settings)
print("RadioTEDU bootstrap complete.")
PY
