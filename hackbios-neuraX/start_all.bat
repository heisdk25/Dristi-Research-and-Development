@echo off
TITLE Drishti Multi-Service Launcher
echo ========================================================
echo        Starting Drishti Backend Services
echo ========================================================
echo.

echo Cleaning up any previous Drishti processes and freeing port 8000...
taskkill /F /FI "WINDOWTITLE eq Drishti*" >nul 2>nul
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }" >nul 2>nul
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name = 'python.exe'\" | Where-Object { $_.CommandLine -like '*drishti_agent*' -or $_.CommandLine -like '*main:app*' -or $_.CommandLine -like '*8000*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>nul

REM 1. Start Token Server
echo [1/2] Starting LiveKit Token Server on port 8000 with uv...
start "Drishti Token Server" cmd /k "cd /d "%~dp0token-server" && uv run --with-requirements requirements.txt uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

REM Reverse port 8000 for USB-connected Android device if ADB exists
if exist "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" (
    "%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" reverse tcp:8000 tcp:8000 >nul 2>nul
) else (
    where adb >nul 2>nul && adb reverse tcp:8000 tcp:8000 >nul 2>nul
)

echo.
REM 2. Start LiveKit Agent Worker (Production 'start' mode for 24/7 continuous resilience)
echo [2/2] Starting Drishti LiveKit Agent Worker with uv...
start "Drishti Agent Worker" cmd /k "cd /d "%~dp0agent" && uv run --with-requirements requirements.txt python drishti_agent.py start"

echo.
echo All backend services launched with full uv dependency environments!
echo Token Server: http://localhost:8000/health
echo Press any key to exit this launcher window...
pause >nul
