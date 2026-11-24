@echo off
rem Double-click launcher: start the agent server inside WSL, then open the browser.
rem Uses an absolute path, so double-clicking from \\wsl.localhost\... works too.
chcp 65001 >nul
set "REPO=/home/zys/.my/code/simple-agent/.mainlines/main"
wsl.exe --cd "%REPO%" -- bash -lc "PYTHON=python3 ./run_server.sh"
start "" http://localhost:8765
echo.
echo URL:  http://localhost:8765
echo Logs: %REPO%/.tmp/server.log
echo Stop: double-click stop.cmd
ping -n 5 127.0.0.1 >nul
