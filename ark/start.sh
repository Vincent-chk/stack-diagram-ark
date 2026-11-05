#!/usr/bin/env bash
# 一句话架构图 · Ark Seed 2.1 — 本地启动
# 用法:  ARK_API_KEY=你的key bash start.sh     (或把 key 写进本目录 .env)
# 打开:  http://127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}

"$PY" -c 'import fastapi, uvicorn' 2>/dev/null || {
  echo "[setup] 安装 fastapi + uvicorn ..."
  "$PY" -m pip install --user fastapi uvicorn
}
"$PY" -c 'import playwright' 2>/dev/null || {
  echo "[setup] 安装 playwright（PNG 渲染需要，仅首次）..."
  "$PY" -m pip install --user playwright
  "$PY" -m playwright install chromium
}

if [ -f .env ]; then set -a; . ./.env; set +a; fi
if [ -z "${ARK_API_KEY:-}" ]; then
  echo "缺 ARK_API_KEY：在环境变量里传，或复制 .env.example 为 .env 填入" >&2
  exit 1
fi

echo "→ http://127.0.0.1:${PORT:-8000}"
exec "$PY" -m uvicorn server:app --host 127.0.0.1 --port "${PORT:-8000}"
