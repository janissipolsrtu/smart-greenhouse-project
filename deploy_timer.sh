#!/bin/bash
# Deploy MQTT Timer Service to Raspberry Pi

PI_HOST="192.168.8.151" 
PI_USER="pi"

echo "🚀 Deploying MQTT Timer Service to Raspberry Pi"
echo "================================================"

# Copy files to Pi
echo "📋 Step 1: Copying files to Pi..."
scp mqtt_timer_service.py ${PI_USER}@${PI_HOST}:~/
scp Dockerfile.timer ${PI_USER}@${PI_HOST}:~/

# Connect to Pi and build/run Docker container
echo "🐳 Step 2: Building and running Docker container on Pi..."

ssh ${PI_USER}@${PI_HOST} << 'ENDSSH'

echo "🏗️  Building Docker image..."
docker build -f Dockerfile.timer -t irrigation-timer .

echo "🛑 Stopping any existing timer container..."
docker stop irrigation-timer-service 2>/dev/null || true
docker rm irrigation-timer-service 2>/dev/null || true

echo "🚀 Starting new timer service container..."
docker run -d \
  --name irrigation-timer-service \
  --network host \
  --restart unless-stopped \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  irrigation-timer

echo "📊 Container status:"
docker ps | grep irrigation-timer

echo "📝 Container logs (last 10 lines):"
sleep 2
docker logs --tail 10 irrigation-timer-service

echo "✅ Timer service deployed successfully!"
echo "Monitor logs with: docker logs -f irrigation-timer-service"

ENDSSH

echo ""
echo "🎯 Deployment Complete!"
echo "Timer service is running on ${PI_HOST} in Docker container"
echo ""
echo "📊 To monitor:"
echo "ssh ${PI_USER}@${PI_HOST}"
echo "docker logs -f irrigation-timer-service"