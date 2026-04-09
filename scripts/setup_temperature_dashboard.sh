#!/bin/bash

# Setup and deploy temperature dashboard
echo "🚀 Setting up Temperature Dashboard..."

# Stop existing containers
echo "⏹️ Stopping existing containers..."
docker-compose -f docker-compose-celery.yml down

# Build new containers
echo "🔨 Building containers..."
docker-compose -f docker-compose-celery.yml build

# Start database services first
echo "🗄️ Starting database services..."
docker-compose -f docker-compose-celery.yml up -d postgres redis

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 15

# Run Django migrations to create SensorData table
echo "🔄 Running Django migrations..."
docker-compose -f docker-compose-celery.yml run --rm django-webapp python manage.py makemigrations irrigation
docker-compose -f docker-compose-celery.yml run --rm django-webapp python manage.py migrate

# Start all services
echo "🚀 Starting all services..."
docker-compose -f docker-compose-celery.yml up -d

# Check service status
echo "📊 Checking service status..."
sleep 5
docker-compose -f docker-compose-celery.yml ps

echo ""
echo "✅ Temperature Dashboard Setup Complete!"
echo ""
echo "🌐 Services Available:"
echo "   - Django Web App: http://localhost:8080"
echo "   - Temperature Dashboard: http://localhost:8080/temperature/"
echo "   - FastAPI: http://localhost:8000"
echo "   - Flower Monitoring: http://localhost:5555"
echo ""
echo "📊 Check logs with:"
echo "   docker-compose -f docker-compose-celery.yml logs -f sensor-collector"
echo ""
echo "🔄 The sensor data collector is now running and will automatically:"
echo "   - Connect to your Raspberry Pi MQTT broker (192.168.8.151)"
echo "   - Subscribe to zigbee2mqtt sensor data"
echo "   - Store temperature and humidity readings in the database"
echo "   - Make data available in the temperature dashboard"