# Simple Mosquitto MQTT Broker Setup for WSL
Write-Host "🦟 Setting up Mosquitto MQTT Broker" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Green
Write-Host ""

# Check if in WSL
Write-Host "🔍 Checking environment..." -ForegroundColor Cyan
if (Get-Command wsl -ErrorAction SilentlyContinue) {
    Write-Host "✅ WSL detected" -ForegroundColor Green
} else {
    Write-Host "❌ WSL not found. Please install WSL first." -ForegroundColor Red
    exit 1
}

# Create mosquitto directories if they don't exist
Write-Host "📁 Creating Mosquitto directories..." -ForegroundColor Cyan
if (!(Test-Path "mosquitto")) { New-Item -ItemType Directory -Path "mosquitto" -Force }
if (!(Test-Path "mosquitto/config")) { New-Item -ItemType Directory -Path "mosquitto/config" -Force }
if (!(Test-Path "mosquitto/data")) { New-Item -ItemType Directory -Path "mosquitto/data" -Force }
if (!(Test-Path "mosquitto/log")) { New-Item -ItemType Directory -Path "mosquitto/log" -Force }

# Set permissions in WSL
Write-Host "🔐 Setting permissions..." -ForegroundColor Cyan
wsl chmod -R 755 mosquitto/

# Stop existing mosquitto container if running
Write-Host "⏹️ Stopping any existing Mosquitto containers..." -ForegroundColor Yellow
wsl docker stop mosquitto-broker 2>$null || $true
wsl docker rm mosquitto-broker 2>$null || $true

# Start Mosquitto
Write-Host "🚀 Starting Mosquitto MQTT broker..." -ForegroundColor Green
wsl docker-compose -f docker-compose.mqtt.yml up -d

# Wait for startup
Write-Host "⏳ Waiting for Mosquitto to start..." -ForegroundColor Magenta
Start-Sleep -Seconds 5

# Get WSL IP
$wslIP = (wsl hostname -I).Trim() -split '\s+' | Select-Object -First 1
Write-Host "🌐 WSL IP Address: $wslIP" -ForegroundColor Cyan

# Check if container is running
$containerStatus = wsl docker ps --filter "name=mosquitto-broker" --format "table {{.Names}}\t{{.Status}}"
Write-Host ""
Write-Host "📊 Container Status:" -ForegroundColor Yellow
Write-Host $containerStatus

# Test MQTT broker
Write-Host ""
Write-Host "🧪 Testing MQTT broker..." -ForegroundColor Cyan
$testResult = wsl docker run --rm eclipse-mosquitto:2.0 mosquitto_pub -h $wslIP -t "test/broker" -m "Hello Mosquitto" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ MQTT broker is working!" -ForegroundColor Green
} else {
    Write-Host "⚠️ MQTT broker test failed. Container may still be starting." -ForegroundColor Yellow
}

# Configure Windows Firewall
Write-Host ""
Write-Host "🔥 Configuring Windows Firewall..." -ForegroundColor Yellow
try {
    New-NetFirewallRule -DisplayName "Mosquitto MQTT" -Direction Inbound -Protocol TCP -LocalPort 1883 -Action Allow -ErrorAction SilentlyContinue | Out-Null
    Write-Host "✅ Firewall rule added for port 1883" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Could not add firewall rule (run as Administrator if needed)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Mosquitto MQTT Broker Setup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 MQTT Broker Access:" -ForegroundColor Cyan
Write-Host "   Broker Address: $wslIP" -ForegroundColor White
Write-Host "   MQTT Port:      1883" -ForegroundColor White
Write-Host "   WebSocket Port: 9001" -ForegroundColor White
Write-Host ""
Write-Host "🧪 Test Commands:" -ForegroundColor Yellow
Write-Host "   Subscribe: wsl docker run --rm eclipse-mosquitto mosquitto_sub -h $wslIP -t 'test/#'" -ForegroundColor White
Write-Host "   Publish:   wsl docker run --rm eclipse-mosquitto mosquitto_pub -h $wslIP -t 'test/hello' -m 'World'" -ForegroundColor White
Write-Host ""
Write-Host "🔧 Management Commands:" -ForegroundColor Magenta
Write-Host "   View logs:  wsl docker logs mosquitto-broker -f" -ForegroundColor White
Write-Host "   Stop:       wsl docker-compose -f docker-compose.mqtt.yml down" -ForegroundColor White
Write-Host "   Restart:    wsl docker-compose -f docker-compose.mqtt.yml restart" -ForegroundColor White
Write-Host "   Status:     wsl docker ps --filter name=mosquitto-broker" -ForegroundColor White
Write-Host ""
Write-Host "📝 Configuration files are in: .\mosquitto\config\" -ForegroundColor Cyan