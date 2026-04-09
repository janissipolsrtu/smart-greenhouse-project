# Complete System Setup with Centralized MQTT Broker
Write-Host "🌐 Complete Irrigation System Setup (WSL + MQTT)" -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
Write-Host ""

# Get current IP address
$wslIP = $(wsl hostname -I).Trim() -split '\s+' | Select-Object -First 1
Write-Host "🔍 Detected WSL IP: $wslIP" -ForegroundColor Cyan

# Setup MQTT broker first
Write-Host "🦟 Setting up Mosquitto MQTT broker..." -ForegroundColor Yellow
if (Test-Path "setup_mosquitto_wsl.sh") {
    wsl bash setup_mosquitto_wsl.sh
} else {
    Write-Host "❌ setup_mosquitto_wsl.sh not found" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "⏳ Waiting for MQTT broker to stabilize..." -ForegroundColor Magenta
Start-Sleep -Seconds 10

# Setup main backend services  
Write-Host "🌐 Setting up backend services..." -ForegroundColor Yellow

# Create Docker network
wsl docker network create irrigation_network 2>$null || true

# Stop existing containers
Write-Host "⏹️ Stopping existing containers..." -ForegroundColor Yellow
wsl docker stop $(wsl docker ps -q) 2>$null || true
wsl docker rm $(wsl docker ps -aq) 2>$null || true

# Start core services using the full system compose
Write-Host "🚀 Starting complete irrigation system..." -ForegroundColor Green

if (Test-Path "docker-compose.full-system.yml") {
    wsl docker-compose -f docker-compose.full-system.yml up -d postgres redis
    
    # Wait for databases
    Write-Host "⏳ Waiting for databases to initialize..." -ForegroundColor Magenta
    Start-Sleep -Seconds 20
    
    # Run migrations
    Write-Host "🔄 Running Django migrations..." -ForegroundColor Cyan
    wsl docker-compose -f docker-compose.full-system.yml run --rm django-webapp python manage.py makemigrations irrigation
    wsl docker-compose -f docker-compose.full-system.yml run --rm django-webapp python manage.py migrate
    
    # Start all services
    Write-Host "🚀 Starting all services..." -ForegroundColor Green
    wsl docker-compose -f docker-compose.full-system.yml up -d
    
} else {
    Write-Host "❌ docker-compose.full-system.yml not found" -ForegroundColor Red
    exit 1
}

# Wait for services to start
Write-Host "⏳ Waiting for services to start..." -ForegroundColor Magenta
Start-Sleep -Seconds 15

# Configure Windows Firewall for MQTT
Write-Host "🔥 Configuring Windows Firewall..." -ForegroundColor Yellow
try {
    New-NetFirewallRule -DisplayName "MQTT Mosquitto" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow -ErrorAction SilentlyContinue
    New-NetFirewallRule -DisplayName "Django Backend" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow -ErrorAction SilentlyContinue
    Write-Host "✅ Firewall rules added" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Could not add firewall rules (may need admin privileges)" -ForegroundColor Yellow
}

# Check service status
Write-Host ""
Write-Host "📊 Service Status:" -ForegroundColor Yellow
wsl docker-compose -f docker-compose.full-system.yml ps

# Test services
Write-Host ""
Write-Host "🧪 Testing services..." -ForegroundColor Cyan

# Test MQTT
Write-Host "   Testing MQTT broker..."
$mqttTest = wsl docker run --rm eclipse-mosquitto:2.0 mosquitto_pub -h $wslIP -t "test/topic" -m "Hello MQTT" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ MQTT broker accessible" -ForegroundColor Green
} else {
    Write-Host "   ❌ MQTT broker test failed" -ForegroundColor Red
}

# Test Backend API
Write-Host "   Testing backend API..."
try {
    $response = Invoke-RestMethod -Uri "http://$($wslIP):8080/api/health/" -TimeoutSec 10
    Write-Host "   ✅ Backend API accessible" -ForegroundColor Green
} catch {
    Write-Host "   ⚠️ Backend API not ready (may need more time)" -ForegroundColor Yellow
}

# Test Django Web Interface
Write-Host "   Testing web interface..."
try {
    $web = Invoke-WebRequest -Uri "http://$($wslIP):8080" -TimeoutSec 10
    Write-Host "   ✅ Web interface accessible" -ForegroundColor Green
} catch {
    Write-Host "   ⚠️ Web interface not ready (may need more time)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Complete System Setup Finished!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 System Access URLs:" -ForegroundColor Cyan
Write-Host "   Main Dashboard:      http://$($wslIP):8080" -ForegroundColor White
Write-Host "   Temperature Dashboard: http://$($wslIP):8080/temperature/" -ForegroundColor White
Write-Host "   API Health Check:    http://$($wslIP):8080/api/health/" -ForegroundColor White
Write-Host "   FastAPI Docs:        http://$($wslIP):8000/docs" -ForegroundColor White
Write-Host "   Flower Monitoring:   http://$($wslIP):5555" -ForegroundColor White
Write-Host "   MQTT Explorer:       http://$($wslIP):4000 (if enabled)" -ForegroundColor White
Write-Host ""
Write-Host "📡 MQTT Broker:" -ForegroundColor Yellow
Write-Host "   Broker Address:      $($wslIP):1883" -ForegroundColor White
Write-Host "   WebSocket:           $($wslIP):9001" -ForegroundColor White
Write-Host "   Test Topics:         sensor/+, zigbee2mqtt/+" -ForegroundColor White
Write-Host ""
Write-Host "🍓 Raspberry Pi Setup:" -ForegroundColor Magenta
Write-Host "   1. Update IP addresses in docker-compose.raspberry-pi.yml:" -ForegroundColor White
Write-Host "      MQTT_BROKER=$wslIP" -ForegroundColor Cyan
Write-Host "      BACKEND_SERVER=http://$($wslIP):8080" -ForegroundColor Cyan
Write-Host "   2. Run setup script on Raspberry Pi:" -ForegroundColor White
Write-Host "      ./setup_raspberry_pi.sh" -ForegroundColor Cyan
Write-Host ""
Write-Host "🔧 Management Commands:" -ForegroundColor Yellow
Write-Host "   View all logs:       wsl docker-compose -f docker-compose.full-system.yml logs -f" -ForegroundColor White
Write-Host "   Stop all services:   wsl docker-compose -f docker-compose.full-system.yml down" -ForegroundColor White
Write-Host "   Restart services:    wsl docker-compose -f docker-compose.full-system.yml restart" -ForegroundColor White
Write-Host "   Check status:        wsl docker-compose -f docker-compose.full-system.yml ps" -ForegroundColor White
Write-Host ""
Write-Host "🧪 Test MQTT:" -ForegroundColor Green
Write-Host "   Publish:  wsl docker run --rm eclipse-mosquitto mosquitto_pub -h $wslIP -t 'sensor/test' -m 'Hello World'" -ForegroundColor White
Write-Host "   Subscribe: wsl docker run --rm eclipse-mosquitto mosquitto_sub -h $wslIP -t 'sensor/+'" -ForegroundColor White