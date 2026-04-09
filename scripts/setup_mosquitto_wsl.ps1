# Setup MQTT Broker (Mosquitto) on WSL
Write-Host "🦟 Setting up Mosquitto MQTT Broker in WSL" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Check if running in WSL or Windows
if ($env:WSL_DISTRO_NAME) {
    Write-Host "✅ Running in WSL environment" -ForegroundColor Green
} else {
    Write-Host "⚠️ This script should be run in WSL" -ForegroundColor Yellow
    Write-Host "   Launch WSL and navigate to this directory" -ForegroundColor Yellow
    exit 1
}

# Create necessary directories and set permissions
Write-Host "📁 Setting up directories..." -ForegroundColor Cyan
if (!(Test-Path "mosquitto/data")) { New-Item -ItemType Directory -Path "mosquitto/data" -Force }
if (!(Test-Path "mosquitto/log")) { New-Item -ItemType Directory -Path "mosquitto/log" -Force }

# Set proper permissions for Mosquitto container
Write-Host "🔐 Setting directory permissions..." -ForegroundColor Cyan
chmod -R 755 mosquitto/
chown -R 1883:1883 mosquitto/data mosquitto/log 2>/dev/null || true

# Stop existing containers
Write-Host "⏹️ Stopping existing containers..." -ForegroundColor Yellow
docker-compose -f docker-compose.mosquitto.yml down 2>/dev/null || true

# Build and start Mosquitto
Write-Host "🚀 Starting Mosquitto MQTT broker..." -ForegroundColor Green
docker-compose -f docker-compose.mosquitto.yml up -d

# Wait for service to start
Write-Host "⏳ Waiting for Mosquitto to start..." -ForegroundColor Magenta
Start-Sleep -Seconds 5

# Check service status
Write-Host "📊 Checking service status..." -ForegroundColor Yellow
docker-compose -f docker-compose.mosquitto.yml ps

# Test MQTT broker
Write-Host ""
Write-Host "🧪 Testing MQTT broker..." -ForegroundColor Cyan

# Get WSL IP address for external access
$wslIP = $(wsl hostname -I).Trim()
Write-Host "   WSL IP Address: $wslIP" -ForegroundColor White

# Test local connection
Write-Host "   Testing local MQTT connection..."
$testResult = docker run --rm --network irrigation_network eclipse-mosquitto:2.0 mosquitto_pub -h irrigation-mosquitto -t "test/topic" -m "Hello MQTT" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "   ✅ MQTT broker is working" -ForegroundColor Green
} else {
    Write-Host "   ❌ MQTT test failed: $testResult" -ForegroundColor Red
}

Write-Host ""
Write-Host "✅ Mosquitto MQTT Broker Setup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 MQTT Broker Access:" -ForegroundColor Cyan
Write-Host "   Internal (containers): irrigation-mosquitto:1883" -ForegroundColor White
Write-Host "   External (sensors):    $($wslIP):1883" -ForegroundColor White  
Write-Host "   WebSocket:             $($wslIP):9001" -ForegroundColor White
Write-Host ""
Write-Host "📊 Optional Monitoring:" -ForegroundColor Yellow
Write-Host "   Start MQTT Explorer: docker-compose -f docker-compose.mosquitto.yml --profile monitoring up -d" -ForegroundColor White
Write-Host "   Access at: http://localhost:4000" -ForegroundColor White
Write-Host ""
Write-Host "🔧 Management Commands:" -ForegroundColor Magenta
Write-Host "   View logs:    docker-compose -f docker-compose.mosquitto.yml logs -f" -ForegroundColor White
Write-Host "   Stop broker:  docker-compose -f docker-compose.mosquitto.yml down" -ForegroundColor White
Write-Host "   Restart:      docker-compose -f docker-compose.mosquitto.yml restart" -ForegroundColor White
Write-Host ""
Write-Host "🧪 Test MQTT:" -ForegroundColor Cyan
Write-Host "   Publish:  docker run --rm eclipse-mosquitto mosquitto_pub -h $wslIP -t 'test/topic' -m 'Hello World'" -ForegroundColor White
Write-Host "   Subscribe: docker run --rm eclipse-mosquitto mosquitto_sub -h $wslIP -t 'test/topic'" -ForegroundColor White
Write-Host ""
Write-Host "🍓 Next: Configure your sensors to connect to: $wslIP:1883" -ForegroundColor Green