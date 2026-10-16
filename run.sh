#!/usr/bin/env bash
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"
source venv/bin/activate
exec uvicorn app.main:app --host "${GATEWAY_HOST:-0.0.0.0}" --port "${GATEWAY_PORT:-8000}" --workers 1
