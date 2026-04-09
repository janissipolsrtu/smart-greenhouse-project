#!/bin/bash
# Setup Server-Side Irrigation Timer Service

echo "🏗️  Setting up Server-Side Irrigation Control Architecture"
echo "================================================"

# On Raspberry Pi (192.168.8.151):
echo "📍 Step 1: Deploy Timer Service on Raspberry Pi"
echo "Copy mqtt_timer_service.py to your Raspberry Pi:"
echo "scp mqtt_timer_service.py pi@192.168.8.151:~/"
echo ""

echo "📍 Step 2: Install dependencies on Pi"
echo "ssh pi@192.168.8.151"
echo "pip3 install paho-mqtt"
echo ""

echo "📍 Step 3: Create systemd service for auto-start"
echo "sudo nano /etc/systemd/system/irrigation-timer.service"
echo ""

cat << 'EOF'
[Unit]
Description=Irrigation Timer Service
After=network.target

[Service]
Type=simple
User=pi
ExecStart=/usr/bin/python3 /home/pi/mqtt_timer_service.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "📍 Step 4: Enable and start the service"
echo "sudo systemctl daemon-reload"
echo "sudo systemctl enable irrigation-timer.service"
echo "sudo systemctl start irrigation-timer.service"
echo "sudo systemctl status irrigation-timer.service"
echo ""

echo "📍 Step 5: Update FastAPI (on your development machine)"
echo "Replace scheduling endpoints with server-side timing calls"
echo ""

echo "🎯 Architecture Benefits:"
echo "✅ Timer runs on Pi (no network latency for OFF commands)"
echo "✅ More reliable timing (closer to Zigbee devices)"  
echo "✅ Pi can handle multiple irrigation zones"
echo "✅ FastAPI becomes stateless (easier scaling)"
echo "✅ Timer survives API restarts"
echo "✅ Can add web dashboard directly on Pi"

echo ""
echo "📊 Message Flow:"
echo "API -> irrigation/schedule/request -> Timer Service -> zigbee2mqtt/device/set"
echo "Device -> zigbee2mqtt/device -> Timer Service -> irrigation/status/schedule -> API"