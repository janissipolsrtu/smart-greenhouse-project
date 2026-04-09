#!/bin/bash
# Run Celery-based irrigation system locally (replaces APScheduler)

# Set environment variables
export DATABASE_URL="postgresql://irrigation_user:irrigation_pass@localhost:5432/irrigation_db"
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/0"
export MQTT_BROKER="192.168.8.151"

echo "🌱 Starting Celery-based Irrigation System"
echo "=========================================="

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Please start Redis first:"
    echo "   sudo systemctl start redis"
    echo "   or: redis-server"
    exit 1
fi

echo "✅ Redis is running"

# Check if PostgreSQL is running (optional)
if ! pg_isready -h localhost -U irrigation_user > /dev/null 2>&1; then
    echo "⚠️  PostgreSQL may not be running or accessible"
    echo "   Make sure PostgreSQL is started and accessible"
fi

# Install dependencies if needed
if [ ! -d "fastapi_env" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv fastapi_env
fi

source fastapi_env/bin/activate

echo "📦 Installing Celery dependencies..."
pip install -r requirements.txt
pip install -r requirements_celery.txt

# Start services in background
echo ""
echo "🚀 Starting Celery services..."

# Start Celery worker
echo "📋 Starting Celery Worker..."
celery -A celery_config.celery_app worker --loglevel=info --queues=irrigation_checks,irrigation_execution,irrigation_scheduling &
WORKER_PID=$!

# Wait a moment for worker to start
sleep 3

# Start Celery beat (scheduler)
echo "⏰ Starting Celery Beat (scheduler)..."
celery -A celery_config.celery_app beat --loglevel=info &
BEAT_PID=$!

# Start Flower monitoring (optional)
echo "🌸 Starting Flower monitoring on http://localhost:5555..."
celery -A celery_config.celery_app flower --port=5555 &
FLOWER_PID=$!

# Start API server
echo "🌐 Starting API server on http://localhost:8000..."
python irrigation_api.py &
API_PID=$!

echo ""
echo "🎉 All services started!"
echo "========================"
echo "📊 Flower monitoring: http://localhost:5555"
echo "🌐 API documentation: http://localhost:8000/docs"
echo "📈 API health: http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop all services"

# Function to cleanup processes on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $WORKER_PID $BEAT_PID $FLOWER_PID $API_PID 2>/dev/null
    echo "✅ All services stopped"
    exit 0
}

# Set trap to cleanup on exit
trap cleanup SIGINT SIGTERM

# Wait for all background processes
wait