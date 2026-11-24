#!/bin/sh
# 停止 run_server.sh 起的服务；没在跑就直说
cd "$(dirname "$0")" || exit 1
if [ ! -f .tmp/server.pid ]; then
  echo "没在跑：没有 .tmp/server.pid"
  exit 0
fi
pid=$(cat .tmp/server.pid)
if kill "$pid" 2>/dev/null; then
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    echo "还在跑 pid $pid，可能卡在模型请求上，等一下再试"
  else
    rm -f .tmp/server.pid
    echo "已停止 pid $pid"
  fi
else
  rm -f .tmp/server.pid
  echo "pid $pid 已经不存在，清掉过期的 pid 文件"
fi
