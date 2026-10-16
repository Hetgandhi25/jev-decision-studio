#!/usr/bin/env bash
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

tmux kill-session -t decision-stack 2>/dev/null || true

OLLAYA_BIN="${OLLAYA_BIN:-$HOME/.local/bin/ollaya}"

echo "Starting Ollaya and Decision Gateway in tmux session 'decision-stack'..."
tmux new-session -d -s decision-stack -n ollaya "$OLLAYA_BIN serve"
sleep 2

tmux new-window -t decision-stack:1 -n gateway "cd $DIR && source venv/bin/activate && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"
sleep 3

echo "Tmux session created:"
tmux ls
echo ""
echo "Testing health:"
curl -s http://127.0.0.1:8000/health || echo "Waiting for gateway..."
