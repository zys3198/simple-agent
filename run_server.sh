#!/bin/sh
# 启动 web 演示，默认 http://localhost:8765；解释器用 PYTHON 覆盖，默认 python3
cd "$(dirname "$0")" || exit 1
PY="${PYTHON:-python3}"
mkdir -p .tmp
if [ -f .tmp/server.pid ] && kill -0 "$(cat .tmp/server.pid)" 2>/dev/null; then
  echo "已在运行：pid $(cat .tmp/server.pid)"
  exit 0
fi
[ -f web/dist/index.html ] || echo "警告：web/dist 不存在，先 cd web && npm install && npm run build"
PYTHONPATH=. PYTHONDONTWRITEBYTECODE=1 nohup "$PY" server.py > .tmp/server.log 2>&1 &
echo $! > .tmp/server.pid
sleep 2
echo "BioEvidence Agent: http://localhost:8765  (pid $(cat .tmp/server.pid))"
