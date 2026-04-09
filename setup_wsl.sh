#!/bin/bash
#
# WSL Setup Script for FastAPI Irrigation System
# Run this in WSL2 Ubuntu to set up the development environment
#

echo "🌱 FastAPI Irrigation System - WSL Setup"
echo "========================================"
echo ""

# Update package list
echo "📦 Updating package list..."
sudo apt update

# Install Python 3 and pip if not already installed
echo "🐍 Installing Python 3 and dependencies..."
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Install additional useful packages for development
echo "🛠️ Installing development tools..."
sudo apt install -y curl git nano htop net-tools

# Check Python installation
python3 --version
pip3 --version

echo ""
echo "✅ WSL Environment Setup Complete!"
echo ""
echo "🚀 Next Steps:"
echo "   1. Run: ./run_api.sh"
echo "   2. Open browser: http://localhost:8000/docs"
echo "   3. Test with: python3 test_api.py"
echo ""
echo "🌐 Access from Windows:"
echo "   API: http://localhost:8000"
echo "   Docs: http://localhost:8000/docs"
echo ""
echo "💡 Tip: You can access this project from Windows at:"
echo "   /mnt/c/Users/[username]/repos/bakalaurs"