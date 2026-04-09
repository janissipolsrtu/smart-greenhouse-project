#!/bin/bash

# Raspberry Pi Sensor Collector Setup Script
# Run this on your Raspberry Pi to deploy the sensor data collector

echo "🍓 Raspberry Pi Sensor Collector Setup"
echo "======================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Installing Docker..."
    
    # Update package list
    sudo apt-get update
    
    # Install Docker
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    
    # Add current user to docker group
    sudo usermod -aG docker $USER
    
    echo "✅ Docker installed. Please log out and back in, then run this script again."
    exit 1
fi

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "📦 Installing Docker Compose..."
    sudo apt-get update
    sudo apt-get install -y docker-compose
fi

# Stop any existing containers
echo "⏹️ Stopping existing sensor collector..."
docker-compose -f docker-compose.raspberry-pi.yml down 2>/dev/null || true

# Create logs directory
mkdir -p logs

# Get backend server IP address
echo ""
echo "🔧 Configuration Setup"
echo "---------------------"

# Check current backend server setting
current_backend=$(grep "BACKEND_SERVER=" docker-compose.raspberry-pi.yml | head -1 | cut -d'=' -f2 | tr -d ' ')
echo "Current backend server: $current_backend"

read -p "📍 Enter your main server IP address (press Enter to keep current $current_backend): " backend_ip

if [ ! -z "$backend_ip" ]; then
    # Update the backend server IP in docker-compose file
    sed -i "s|BACKEND_SERVER=.*|BACKEND_SERVER=http://$backend_ip:8080|g" docker-compose.raspberry-pi.yml
    echo "✅ Updated backend server to: http://$backend_ip:8080"
fi

# Build the container
echo ""
echo "🔨 Building sensor collector container..."
docker-compose -f docker-compose.raspberry-pi.yml build

# Test backend connectivity
backend_url=$(grep "BACKEND_SERVER=" docker-compose.raspberry-pi.yml | head -1 | cut -d'=' -f2 | tr -d ' ')
echo ""
echo "🔍 Testing backend connectivity..."
if curl -s --timeout 10 "$backend_url/api/health/" > /dev/null; then
    echo "✅ Backend server is reachable"
else
    echo "⚠️ Cannot reach backend server at $backend_url"
    echo "   This may be normal if the server isn't running yet"
    echo "   The collector will retry when sending data"
fi

# Start the service
echo ""
echo "🚀 Starting sensor collector..."
docker-compose -f docker-compose.raspberry-pi.yml up -d

# Wait a moment and check status
sleep 5
echo ""
echo "📊 Service Status:"
docker-compose -f docker-compose.raspberry-pi.yml ps

# Show logs
echo ""
echo "📋 Recent Logs:"
docker-compose -f docker-compose.raspberry-pi.yml logs --tail=20 sensor-collector

echo ""
echo "✅ Raspberry Pi Sensor Collector Setup Complete!"
echo ""
echo "🔧 Management Commands:"
echo "   View logs:    docker-compose -f docker-compose.raspberry-pi.yml logs -f"
echo "   Stop service: docker-compose -f docker-compose.raspberry-pi.yml down"
echo "   Restart:      docker-compose -f docker-compose.raspberry-pi.yml restart"
echo "   Status:       docker-compose -f docker-compose.raspberry-pi.yml ps"
echo ""
echo "🌐 Optional Log Viewer:"
echo "   Start log viewer: docker-compose -f docker-compose.raspberry-pi.yml --profile logs up -d"
echo "   View logs at:     http://$(hostname -I | awk '{print $1}'):8888"
echo ""
echo "📊 The sensor collector will automatically:"
echo "   - Connect to local MQTT broker (Zigbee2MQTT)"
echo "   - Collect temperature and humidity data"
echo "   - Send batched data to your backend server every 3 minutes"
echo "   - Retry failed transmissions with exponential backoff"