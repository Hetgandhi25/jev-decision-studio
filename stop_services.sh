#!/usr/bin/env bash
echo "Stopping decision-stack tmux session..."
tmux kill-session -t decision-stack 2>/dev/null || true
pkill -u $(id -u) -f "ollaya serve" 2>/dev/null || true
pkill -u $(id -u) -f "uvicorn app.main:app" 2>/dev/null || true
echo "All decision services stopped."
