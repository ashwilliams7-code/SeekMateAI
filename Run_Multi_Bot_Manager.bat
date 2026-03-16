@echo off
cd /d "%~dp0"
echo Starting SeekMateAI Dashboard...
python multi_bot_gui.py
if errorlevel 1 (
    echo.
    echo Failed to start. Make sure Python is installed and you're in the SeekMateAI folder.
    pause
)
