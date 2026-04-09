#!/bin/bash

# Complete Docker Installation for Raspberry Pi
echo "🍓 Installing Docker on Raspberry Pi"
echo "===================================="
echo ""

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "⚠️ Don't run this script as root. Run as regular user."
   exit 1
fi

# Update system
echo "1️⃣ Updating system packages..."
sudo apt-get update
sudo apt-get upgrade -y

echo ""

# Remove any old Docker installations
echo "2️⃣ Removing old Docker installations..."
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true

echo ""

# Install prerequisites
echo "3️⃣ Installing prerequisites..."
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

echo ""

# Add Docker's official GPG key
echo "4️⃣ Adding Docker GPG key..."
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo ""

# Add Docker repository
echo "5️⃣ Adding Docker repository..."
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo ""

# Update package index
echo "6️⃣ Updating package index..."
sudo apt-get update

echo ""

# Install Docker Engine
echo "7️⃣ Installing Docker Engine..."
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo ""

# Start and enable Docker service
echo "8️⃣ Starting Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

echo ""

# Add user to docker group
echo "9️⃣ Adding user to docker group..."
sudo usermod -aG docker $USER

echo ""

# Install Docker Compose (standalone)
echo "🔟 Installing Docker Compose..."
sudo apt-get install -y docker-compose

echo ""

# Test Docker installation
echo "🧪 Testing Docker installation..."
if sudo docker run --rm hello-world; then
    echo "✅ Docker installation successful!"
else
    echo "❌ Docker installation failed"
    exit 1
fi

echo ""
echo "✅ Docker Installation Complete!"
echo ""
echo "⚠️  IMPORTANT: You must LOG OUT and LOG BACK IN for docker group changes to take effect"
echo ""
echo "After logging back in, verify with:"
echo "   docker --version"
echo "   docker ps"
echo "   docker-compose --version"
echo ""
echo "Then run the sensor collector setup:"
echo "   ./setup_raspberry_pi.sh"