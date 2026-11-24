@echo off
rem Double-click stopper: runs stop_server.sh inside WSL.
rem Uses an absolute path, so double-clicking from \\wsl.localhost\... works too.
rem Keep this file ASCII-only (see the start script comments).
chcp 65001 >nul
set "REPO=/home/zys/.my/code/simple-agent/.mainlines/main"
wsl.exe --cd "%REPO%" -- bash ./stop_server.sh
echo.
echo Done. Start again with the start script.
echo.
pause
