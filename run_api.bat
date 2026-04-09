@echo off
REM FastAPI Automated Irrigation System - Setup and Run Script (Windows/WSL)

echo 🌱 FastAPI Automated Irrigation System
echo ========================================

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is required but not installed.
    echo    Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔄 Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo ⬆️ Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo 📥 Installing FastAPI dependencies...
pip install -r requirements.txt

REM Display network info
echo.
echo 🌐 Network Information:
echo    Local API: http://localhost:8000
echo    API Docs: http://localhost:8000/docs
echo    Alternative Docs: http://localhost:8000/redoc
echo.

REM Start the FastAPI server
echo 🚀 Starting FastAPI server with uvicorn...
echo    Press Ctrl+C to stop the server
echo.
python irrigation_api.py

pause