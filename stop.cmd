@echo off
rem Double-click stopper: runs stop_server.sh inside WSL.
rem Uses an absolute path, so double-clicking from \\wsl.localhost\... works too.
chcp 65001 >nul
set "REPO=/home/zys/.my/code/simple-agent/.mainlines/main"
wsl.exe --cd "%REPO%" -- bash ./stop_server.sh
echo.
echo Stop done. Start again with start.cmd
ping -n 4 127.0.0.1 >nul
