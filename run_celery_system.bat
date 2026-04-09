@echo off
REM Run Celery-based irrigation system on Windows (replaces APScheduler)

REM Set environment variables
set DATABASE_URL=postgresql://irrigation_user:irrigation_pass@localhost:5432/irrigation_db
set CELERY_BROKER_URL=redis://localhost:6379/0
set CELERY_RESULT_BACKEND=redis://localhost:6379/0
set MQTT_BROKER=192.168.8.151

echo 🌱 Starting Celery-based Irrigation System
echo ==========================================

REM Check if Redis is accessible
redis-cli ping >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Redis is not running. Please start Redis first
    echo    Download and start Redis from: https://redis.io/download
    pause
    exit /b 1
)

echo ✅ Redis is running

REM Activate virtual environment
if not exist "fastapi_env" (
    echo 📦 Creating virtual environment...
    python -m venv fastapi_env
)

call fastapi_env\Scripts\activate.bat

echo 📦 Installing Celery dependencies...
pip install -r requirements.txt
pip install -r requirements_celery.txt

echo.
echo 🚀 Starting Celery services...
echo.

REM Start services in separate command windows
echo 📋 Starting Celery Worker...
start "Celery Worker" cmd /k "fastapi_env\Scripts\activate.bat && celery -A celery_config.celery_app worker --loglevel=info --queues=irrigation_checks,irrigation_execution,irrigation_scheduling"

timeout /t 3 /nobreak >nul

echo ⏰ Starting Celery Beat (scheduler)...  
start "Celery Beat" cmd /k "fastapi_env\Scripts\activate.bat && celery -A celery_config.celery_app beat --loglevel=info"

echo 🌸 Starting Flower monitoring...
start "Flower Monitor" cmd /k "fastapi_env\Scripts\activate.bat && celery -A celery_config.celery_app flower --port=5555"

echo 🌐 Starting API server...
start "API Server" cmd /k "fastapi_env\Scripts\activate.bat && python irrigation_api.py"

echo.
echo 🎉 All services started in separate windows!
echo =============================================
echo 📊 Flower monitoring: http://localhost:5555
echo 🌐 API documentation: http://localhost:8000/docs  
echo 📈 API health: http://localhost:8000/health
echo.
echo Press any key to exit...
pause >nul