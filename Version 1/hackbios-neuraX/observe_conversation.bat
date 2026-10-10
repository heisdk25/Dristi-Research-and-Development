@echo off
TITLE Drishti Live LLM Conversation Observation Terminal
echo ========================================================
echo   Launching Drishti Live LLM Conversation Observer
echo ========================================================
echo.

cd /d "%~dp0agent"
uv run --with-requirements requirements.txt python observe_conversation.py

pause
