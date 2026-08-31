#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已创建 .env。请填入 LLM_API_KEY、LLM_BASE_URL 和 LLM_MODEL；未填写时可使用演示降级模式。"
fi

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -q -r backend/requirements.txt

if [ ! -d frontend/node_modules ]; then
  npm --prefix frontend install --silent
fi

cleanup() {
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!
npm --prefix frontend run dev -- --host 127.0.0.1 &
FRONTEND_PID=$!

echo "观点火花已启动：http://localhost:5173"
wait "$BACKEND_PID" "$FRONTEND_PID"
