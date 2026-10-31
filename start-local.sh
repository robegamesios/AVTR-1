#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
export PATH="$HOME/.pixi/bin:$PATH"
export JARVIS_ROOT="${JARVIS_ROOT:-/home/rob/Documents/Github/JARVIS-AI}"
export STREAMER_PORT="${STREAMER_PORT:-8081}"
export RENDERER_PORT="${RENDERER_PORT:-8082}"
"$JARVIS_ROOT/venv/bin/python" scripts/jarvis_voice_worker.py &
voice_pid=$!
cleanup() { kill "$voice_pid" 2>/dev/null || true; }
trap cleanup EXIT
pixi run -e streamer python scripts/run_local_stream.py
