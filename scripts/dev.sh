#!/usr/bin/env bash
# Avvia backend (http://localhost:8000) e interfaccia (http://localhost:3000).
# Con --tunnel apre anche un tunnel Cloudflare temporaneo verso il backend.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1 || lsof -nP -iTCP:3000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Reel Studio sembra già acceso (porte 8000/3000 occupate): apri http://localhost:3000"
  echo "Per riavviarlo, chiudi prima l'altra istanza con Ctrl-C nel suo Terminale."
  exit 0
fi

[ -f .env ] ||{ cp .env.example .env; echo "Creato .env da .env.example"; }

# il virtualenv si ricrea se manca o se la cartella del progetto è stata spostata
if ! backend/.venv/bin/python -c "import uvicorn, fastapi, faster_whisper" 2>/dev/null; then
  echo "Installo le dipendenze Python…"
  rm -rf backend/.venv
  python3 -m venv backend/.venv
  backend/.venv/bin/python -m pip install -q --upgrade pip
  backend/.venv/bin/python -m pip install -q -r backend/requirements.txt
fi
if [ ! -x web/node_modules/.bin/next ]; then
  echo "Installo le dipendenze dell'interfaccia…"
  (cd web && npm install --silent)
fi

pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

(cd backend && .venv/bin/python -m uvicorn app.main:app --port 8000 --reload --reload-dir app) & pids+=($!)
(cd web && npm run dev -- --port 3000) & pids+=($!)

if [ "${1:-}" = "--tunnel" ]; then
  command -v cloudflared >/dev/null || { echo "Installa cloudflared: brew install cloudflared"; exit 1; }
  echo "Tunnel in avvio: copia l'URL https://….trycloudflare.com in PUBLIC_BASE_URL nel file .env e riavvia."
  cloudflared tunnel --url http://localhost:8000 & pids+=($!)
fi

echo ""
echo "  Reel Studio → http://localhost:3000"
echo ""
wait
