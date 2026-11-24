@echo off
rem 双击启动：在 WSL 里起服务（已在跑就只提示），再开浏览器。地址与日志在下面打印。
rem 这个文件用绝对路径，所以从 \\wsl.localhost\... 双击也能跑（cmd 会把当前目录退回 Windows 目录）。
chcp 65001 >nul
set "REPO=/home/zys/.my/code/simple-agent/.mainlines/main"
wsl.exe --cd "%REPO%" -- bash -lc "PYTHON=python3 ./run_server.sh"
start "" http://localhost:8765
echo.
echo URL:  http://localhost:8765
echo Logs: %REPO%/.tmp/server.log
echo Stop: wsl.exe --cd "%REPO%" -- bash -lc "kill $(cat .tmp/server.pid)"
ping -n 5 127.0.0.1 >nul
