#!/bin/bash

# Raspberry Pi Docker Troubleshooting & Fix Script
echo "🔧 Docker Troubleshooting for Raspberry Pi"
echo "=========================================="
echo ""

# Check if script is run as root
if [[ $EUID -eq 0 ]]; then
   echo "⚠️ Don't run this script as root (sudo). Run as regular user."
   exit 1
fi

echo "👤 Current user: $(whoami)"
echo ""

# 1. Check Docker installation
echo "1️⃣ Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Installing now..."
    
    # Install Docker using the official script
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    
    echo "✅ Docker installed"
else
    echo "✅ Docker is installed: $(docker --version)"
fi

echo ""

# 2. Check if Docker daemon is running
echo "2️⃣ Checking Docker daemon status..."
if sudo systemctl is-active --quiet docker; then
    echo "✅ Docker daemon is running"
else
    echo "❌ Docker daemon is not running. Starting it..."
    sudo systemctl start docker
    sudo systemctl enable docker
    echo "✅ Docker daemon started and enabled"
fi

echo ""

# 3. Check user permissions
echo "3️⃣ Checking Docker permissions..."
if groups $USER | grep -q docker; then
    echo "✅ User $(whoami) is in docker group"
else
    echo "❌ User $(whoami) is NOT in docker group. Adding now..."
    sudo usermod -aG docker $USER
    echo "✅ User added to docker group"
    echo "⚠️ You need to LOG OUT and LOG BACK IN for group changes to take effect"
    echo "   After logging back in, run this script again"
    exit 0
fi

echo ""

# 4. Test Docker access
echo "4️⃣ Testing Docker access..."
if docker ps &> /dev/null; then
    echo "✅ Docker is accessible without sudo"
else
    echo "❌ Cannot access Docker without sudo"
    echo "💡 Solutions:"
    echo "   1. Log out and log back in (most common fix)"
    echo "   2. Or run: newgrp docker"
    echo "   3. Or reboot the Raspberry Pi"
    echo ""
    echo "🔄 Trying to refresh group membership..."
    exec sg docker "$0"
fi

echo ""

# 5. Test Docker functionality
echo "5️⃣ Testing Docker functionality..."
if docker run --rm hello-world &> /dev/null; then
    echo "✅ Docker is working correctly"
else
    echo "❌ Docker test failed"
    echo "📋 Docker daemon status:"
    sudo systemctl status docker --no-pager -l
    exit 1
fi

echo ""

# 6. Install Docker Compose if needed
echo "6️⃣ Checking Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose not found. Installing..."
    
    # Install Docker Compose
    sudo apt-get update
    sudo apt-get install -y docker-compose
    
    echo "✅ Docker Compose installed: $(docker-compose --version)"
else
    echo "✅ Docker Compose is available: $(docker-compose --version)"
fi

echo ""

# 7. Test Docker Compose
echo "7️⃣ Testing Docker Compose..."
if docker-compose --version &> /dev/null; then
    echo "✅ Docker Compose is working"
else
    echo "❌ Docker Compose test failed"
fi

echo ""
echo "✅ Docker troubleshooting complete!"
echo ""
echo "🚀 Now you can run the setup script:"
echo "   ./setup_raspberry_pi.sh"
echo ""
echo "🔧 If you still have issues:"
echo "   - Reboot the Raspberry Pi: sudo reboot"
echo "   - Check logs: sudo journalctl -u docker.service"
echo "   - Verify system: cat /etc/os-release"