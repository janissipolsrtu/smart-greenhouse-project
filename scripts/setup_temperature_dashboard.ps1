# Setup and deploy temperature dashboard
Write-Host "🚀 Setting up Temperature Dashboard..." -ForegroundColor Green

# Stop existing containers
Write-Host "⏹️ Stopping existing containers..." -ForegroundColor Yellow
docker-compose -f docker-compose-celery.yml down

# Build new containers
Write-Host "🔨 Building containers..." -ForegroundColor Cyan
docker-compose -f docker-compose-celery.yml build

# Start database services first
Write-Host "🗄️ Starting database services..." -ForegroundColor Blue
docker-compose -f docker-compose-celery.yml up -d postgres redis

# Wait for database to be ready
Write-Host "⏳ Waiting for database to be ready..." -ForegroundColor Magenta
Start-Sleep -Seconds 15

# Run Django migrations to create SensorData table
Write-Host "🔄 Running Django migrations..." -ForegroundColor Cyan
docker-compose -f docker-compose-celery.yml run --rm django-webapp python manage.py makemigrations irrigation
docker-compose -f docker-compose-celery.yml run --rm django-webapp python manage.py migrate

# Start all services
Write-Host "🚀 Starting all services..." -ForegroundColor Green
docker-compose -f docker-compose-celery.yml up -d

# Check service status
Write-Host "📊 Checking service status..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
docker-compose -f docker-compose-celery.yml ps

Write-Host ""
Write-Host "✅ Temperature Dashboard Setup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Services Available:" -ForegroundColor Cyan
Write-Host "   - Django Web App: http://localhost:8080" -ForegroundColor White
Write-Host "   - Temperature Dashboard: http://localhost:8080/temperature/" -ForegroundColor White
Write-Host "   - FastAPI: http://localhost:8000" -ForegroundColor White
Write-Host "   - Flower Monitoring: http://localhost:5555" -ForegroundColor White
Write-Host ""
Write-Host "📊 Check logs with:" -ForegroundColor Yellow
Write-Host "   docker-compose -f docker-compose-celery.yml logs -f sensor-collector" -ForegroundColor White
Write-Host ""
Write-Host "🔄 The sensor data collector is now running and will automatically:" -ForegroundColor Cyan
Write-Host "   - Connect to your Raspberry Pi MQTT broker (192.168.8.151)" -ForegroundColor White
Write-Host "   - Subscribe to zigbee2mqtt sensor data" -ForegroundColor White
Write-Host "   - Store temperature and humidity readings in the database" -ForegroundColor White
Write-Host "   - Make data available in the temperature dashboard" -ForegroundColor White