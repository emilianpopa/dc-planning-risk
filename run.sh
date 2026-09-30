#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt
[ -f .env ] && set -a && . ./.env && set +a
exec ./venv/bin/uvicorn app.main:app --port 8099 --reload
