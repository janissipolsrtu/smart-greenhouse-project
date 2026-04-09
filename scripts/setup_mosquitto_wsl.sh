#!/bin/bash

# Setup MQTT Broker (Mosquitto) on WSL
echo "🦟 Setting up Mosquitto MQTT Broker in WSL"
echo "=========================================="
echo ""

# Create necessary directories
echo "📁 Setting up directories..."
mkdir -p mosquitto/{data,log}

# Set proper permissions for Mosquitto container
echo "🔐 Setting directory permissions..."
chmod -R 755 mosquitto/
sudo chown -R 1883:1883 mosquitto/data mosquitto/log 2>/dev/null || true

# Stop existing containers
echo "⏹️ Stopping existing containers..."
docker-compose -f docker-compose.mosquitto.yml down 2>/dev/null || true

# Check if Docker is running
if ! docker ps &> /dev/null; then
    echo "❌ Docker is not running. Starting Docker..."
    sudo systemctl start docker || sudo service docker start
fi

# Create network if it doesn't exist
echo "🔗 Creating Docker network..."
docker network create irrigation_network 2>/dev/null || true

# Build and start Mosquitto
echo "🚀 Starting Mosquitto MQTT broker..."
docker-compose -f docker-compose.mosquitto.yml up -d

# Wait for service to start
echo "⏳ Waiting for Mosquitto to start..."
sleep 5

# Check service status
echo "📊 Checking service status..."
docker-compose -f docker-compose.mosquitto.yml ps

# Test MQTT broker
echo ""
echo "🧪 Testing MQTT broker..."

# Get WSL IP address for external access
WSL_IP=$(hostname -I | awk '{print $1}')
echo "   WSL IP Address: $WSL_IP"

# Test local connection
echo "   Testing local MQTT connection..."
if docker run --rm --network irrigation_network eclipse-mosquitto:2.0 mosquitto_pub -h irrigation-mosquitto -t "test/topic" -m "Hello MQTT" &> /dev/null; then
    echo "   ✅ MQTT broker is working"
else
    echo "   ❌ MQTT test failed"
    echo "   Checking logs..."
    docker-compose -f docker-compose.mosquitto.yml logs --tail=10 mosquitto
fi

# Test external connection
echo "   Testing external MQTT connection..."
if docker run --rm eclipse-mosquitto:2.0 mosquitto_pub -h "$WSL_IP" -t "test/external" -m "External test" &> /dev/null; then
    echo "   ✅ External MQTT access working"
else
    echo "   ⚠️ External MQTT access may need firewall configuration"
fi

echo ""
echo "✅ Mosquitto MQTT Broker Setup Complete!"
echo ""
echo "🌐 MQTT Broker Access:"
echo "   Internal (containers): irrigation-mosquitto:1883"
echo "   External (sensors):    $WSL_IP:1883"  
echo "   WebSocket:             $WSL_IP:9001"
echo ""
echo "📊 Optional Monitoring:"
echo "   Start MQTT Explorer: docker-compose -f docker-compose.mosquitto.yml --profile monitoring up -d"
echo "   Access at: http://localhost:4000"
echo ""
echo "🔧 Management Commands:"
echo "   View logs:    docker-compose -f docker-compose.mosquitto.yml logs -f"
echo "   Stop broker:  docker-compose -f docker-compose.mosquitto.yml down"
echo "   Restart:      docker-compose -f docker-compose.mosquitto.yml restart"
echo ""
echo "🧪 Test MQTT:"
echo "   Publish:  docker run --rm eclipse-mosquitto mosquitto_pub -h $WSL_IP -t 'test/topic' -m 'Hello World'"
echo "   Subscribe: docker run --rm eclipse-mosquitto mosquitto_sub -h $WSL_IP -t 'test/topic'"
echo ""
echo "🔥 Important: Configure Windows Firewall to allow port 1883"
echo "   Run in Windows PowerShell as Administrator:"
echo "   New-NetFirewallRule -DisplayName 'MQTT Mosquitto' -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow"
echo ""
echo "🍓 Next: Configure your sensors to connect to: $WSL_IP:1883"