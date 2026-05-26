#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 &>/dev/null; then
  echo "Python 3 is required." >&2
  exit 1
fi

if ! python3 -c "import fastapi" 2>/dev/null; then
  echo "Installing backend dependencies..."
  python3 -m pip install -r backend/requirements.txt
fi

if [[ ! -d frontend/node_modules ]]; then
  echo "Installing frontend dependencies..."
  (cd frontend && npm install)
fi

if [[ ! -d node_modules ]]; then
  echo "Installing root dev dependencies..."
  npm install
fi

echo "Starting backend (http://127.0.0.1:8000) and frontend (http://localhost:5173)..."
npm run dev
