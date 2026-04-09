#!/bin/bash
#
# Development server with hot reload
# Use this during development for automatic reloading
#

echo "🔥 FastAPI Development Server with Hot Reload"
echo "============================================"

# Activate virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

echo ""
echo "🚀 Starting development server with auto-reload..."
echo "   API: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo "   Press Ctrl+C to stop"
echo ""

# Start with uvicorn directly for development
uvicorn irrigation_api:app --host 0.0.0.0 --port 8000 --reload --log-level info