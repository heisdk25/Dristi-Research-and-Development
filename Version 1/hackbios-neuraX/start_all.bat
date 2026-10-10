@echo off
TITLE Drishti Multi-Service Launcher
echo ========================================================
echo        Starting Drishti Backend Services
echo ========================================================
echo.

echo Cleaning up any previous Drishti processes and freeing ports 8000 and 8081...
taskkill /F /FI "WINDOWTITLE eq Drishti*" >nul 2>nul
powershell -NoProfile -Command "try { Get-NetTCPConnection -LocalPort 8000,8081 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue } } catch {}; try { Get-Process python,uv -ErrorAction SilentlyContinue | Where-Object { $_.Path -like '*vision_man*' } | Stop-Process -Force -ErrorAction SilentlyContinue } catch {}; exit 0" >nul 2>nul

REM Wait 2 seconds to allow Windows TCP stack to fully release sockets
timeout /t 2 /nobreak >nul

REM 1. Start Token Server
echo [1/2] Starting LiveKit Token Server on port 8000 with uv...
start "Drishti Token Server" /D "%~dp0token-server" cmd /k uv run --with-requirements requirements.txt uvicorn main:app --host 0.0.0.0 --port 8000

REM Reverse port 8000 for USB-connected Android device if ADB exists
if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000 >nul 2>nul
) else (
    where adb >nul 2>nul && adb reverse tcp:8000 tcp:8000 >nul 2>nul
)

echo.
REM 2. Start LiveKit Agent Worker (Production 'start' mode for 24/7 continuous resilience)
echo [2/2] Starting Drishti LiveKit Agent Worker with uv...
start "Drishti Agent Worker" /D "%~dp0agent" cmd /k uv run --with-requirements requirements.txt python drishti_agent.py start

echo.
echo All backend services launched with full uv dependency environments!
echo Token Server: http://localhost:8000/health
echo Press any key to exit this launcher window...
pause >nul

