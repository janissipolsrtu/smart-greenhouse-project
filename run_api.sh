#!/bin/bash
# 
# Automated Irrigation System FastAPI - Setup and Run Script for WSL/Linux
#

echo "🌱 FastAPI Automated Irrigation System"
echo "======================================"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "   Install with: sudo apt update && sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing FastAPI dependencies..."
pip install -r requirements.txt

# Show network info
echo ""
echo "🌐 Network Information:"
echo "   Local API: http://localhost:8000"
echo "   Network API: http://$(hostname -I | awk '{print $1}'):8000" 
echo "   API Docs: http://localhost:8000/docs"
echo "   Alternative Docs: http://localhost:8000/redoc"
echo ""

# Start the FastAPI server
echo "🚀 Starting FastAPI server with uvicorn..."
echo "   Press Ctrl+C to stop the server"
echo ""

python3 irrigation_api.py