@echo off
REM Quick start script for DynoAI Qt6 Desktop Application

echo Starting DynoAI Qt6...

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

REM Run the application
python dynoai_qt6.py

pause
