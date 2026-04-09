# Main Server Setup - Temperature Dashboard Backend
Write-Host "🌐 Main Server Temperature Dashboard Setup" -ForegroundColor Green
Write-Host "===========================================" -ForegroundColor Green
Write-Host ""

# Stop existing containers
Write-Host "⏹️ Stopping existing containers..." -ForegroundColor Yellow
docker stop $(docker ps -q) 2>$null

# Build new containers
Write-Host "🔨 Building backend containers..." -ForegroundColor Cyan
if (Test-Path "docker-compose-celery.yml") {
    # Use Docker directly since docker-compose may not be available
    Write-Host "   Building Django webapp..." -ForegroundColor Blue
    docker build -f Dockerfile.django -t irrigation-django .
    
    Write-Host "   Building FastAPI..." -ForegroundColor Blue
    docker build -f Dockerfile -t irrigation-api .
    
    Write-Host "   Building Celery services..." -ForegroundColor Blue
    docker build -f Dockerfile.celery -t irrigation-celery .
} else {
    Write-Host "❌ docker-compose-celery.yml not found" -ForegroundColor Red
    exit 1
}

# Create Docker network
Write-Host "🔗 Creating Docker network..." -ForegroundColor Cyan
docker network create irrigation_network 2>$null

# Start core services
Write-Host "🗄️ Starting database services..." -ForegroundColor Blue

# PostgreSQL
docker run -d --name irrigation-postgres `
  --network irrigation_network `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -p 5432:5432 `
  postgres:15-alpine

# Redis
docker run -d --name irrigation-redis `
  --network irrigation_network `
  -p 6379:6379 `
  redis:7-alpine

# Wait for database to be ready
Write-Host "⏳ Waiting for database to initialize..." -ForegroundColor Magenta
Start-Sleep -Seconds 15

# Run Django migrations
Write-Host "🔄 Running Django migrations..." -ForegroundColor Cyan
docker run --rm --network irrigation_network `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -e POSTGRES_HOST=irrigation-postgres `
  -e POSTGRES_PORT=5432 `
  irrigation-django python manage.py makemigrations irrigation

docker run --rm --network irrigation_network `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -e POSTGRES_HOST=irrigation-postgres `
  -e POSTGRES_PORT=5432 `
  irrigation-django python manage.py migrate

# Start Django Web Application
Write-Host "🌐 Starting Django web application..." -ForegroundColor Green
docker run -d --name irrigation-django-webapp `
  --network irrigation_network `
  -p 8080:8080 `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -e POSTGRES_HOST=irrigation-postgres `
  -e POSTGRES_PORT=5432 `
  -e REDIS_HOST=irrigation-redis `
  -e DJANGO_SECRET_KEY=django-secret-key-change-me `
  -e DEBUG=True `
  irrigation-django

# Start FastAPI (optional)
Write-Host "📡 Starting FastAPI service..." -ForegroundColor Blue
docker run -d --name irrigation-api `
  --network irrigation_network `
  -p 8000:8000 `
  -e DATABASE_URL=postgresql://irrigation_user:irrigation_pass@irrigation-postgres:5432/irrigation_db `
  -e CELERY_BROKER_URL=redis://irrigation-redis:6379/0 `
  -e CELERY_RESULT_BACKEND=redis://irrigation-redis:6379/0 `
  irrigation-api

# Start Celery Worker (optional)
Write-Host "⚙️ Starting Celery worker..." -ForegroundColor Magenta
docker run -d --name irrigation-celery-worker `
  --network irrigation_network `
  -e DATABASE_URL=postgresql://irrigation_user:irrigation_pass@irrigation-postgres:5432/irrigation_db `
  -e CELERY_BROKER_URL=redis://irrigation-redis:6379/0 `
  -e CELERY_RESULT_BACKEND=redis://irrigation-redis:6379/0 `
  -e MQTT_BROKER=192.168.8.151 `
  irrigation-celery celery -A celery_config.celery_app worker --loglevel=info

# Start Flower monitoring (optional)
Write-Host "🌸 Starting Flower monitoring..." -ForegroundColor Yellow
docker run -d --name irrigation-flower `
  --network irrigation_network `
  -p 5555:5555 `
  -e CELERY_BROKER_URL=redis://irrigation-redis:6379/0 `
  -e CELERY_RESULT_BACKEND=redis://irrigation-redis:6379/0 `
  irrigation-celery celery -A celery_config.celery_app flower --port=5555

# Wait for services to start
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Magenta
Start-Sleep -Seconds 10

# Check service status
Write-Host "📊 Checking service status..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Running Containers:" -ForegroundColor Cyan
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Test API endpoints
Write-Host ""
Write-Host "🔍 Testing API endpoints..." -ForegroundColor Cyan

try {
    $healthResponse = Invoke-RestMethod -Uri "http://localhost:8080/api/health/" -TimeoutSec 10
    Write-Host "✅ Health check API working" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Health check API not responding (may need more time)" -ForegroundColor Yellow
}

try {
    $webResponse = Invoke-WebRequest -Uri "http://localhost:8080" -TimeoutSec 10
    Write-Host "✅ Django web interface accessible" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Django web interface not accessible (may need more time)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Main Server Setup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Services Available:" -ForegroundColor Cyan
Write-Host "   - Django Web App: http://localhost:8080" -ForegroundColor White
Write-Host "   - Temperature Dashboard: http://localhost:8080/temperature/" -ForegroundColor White
Write-Host "   - Health Check API: http://localhost:8080/api/health/" -ForegroundColor White
Write-Host "   - Bulk Sensor API: http://localhost:8080/api/sensor-data/bulk/" -ForegroundColor White
Write-Host "   - FastAPI: http://localhost:8000" -ForegroundColor White
Write-Host "   - Flower Monitoring: http://localhost:5555" -ForegroundColor White
Write-Host ""
Write-Host "📊 Management Commands:" -ForegroundColor Yellow
Write-Host "   View logs: docker logs <container-name>" -ForegroundColor White
Write-Host "   Stop all: docker stop `$(docker ps -q)" -ForegroundColor White
Write-Host "   Remove all: docker rm `$(docker ps -aq)" -ForegroundColor White
Write-Host ""
Write-Host "🍓 Next Step:" -ForegroundColor Magenta
Write-Host "   Deploy the sensor collector on your Raspberry Pi using:" -ForegroundColor White
Write-Host "   setup_raspberry_pi.sh" -ForegroundColor Cyan
Write-Host ""
Write-Host "📡 The backend is now ready to receive sensor data from Raspberry Pi!" -ForegroundColor Green