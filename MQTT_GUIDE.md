# 🌱 API to MQTT Communication Guide

## How Your FastAPI Sends Commands to MQTT Server

Your irrigation system uses this workflow:

```
📱 API Request → 🖥️ FastAPI Server → 📡 MQTT Broker → 🏠 Zigbee2MQTT → 💧 Irrigation Device
```

## 🔄 **Complete Workflow:**

### 1. **API Request (You → FastAPI)**
```bash
curl -X POST http://localhost:8000/api/irrigation/control \
  -H "Content-Type: application/json" \
  -d '{"action": "ON"}'
```

### 2. **FastAPI Processing (irrigation_api.py)**
```python
@app.post("/api/irrigation/control")
async def control_irrigation(command: IrrigationCommand):
    # Validate request
    action = command.action.upper()  # "ON" or "OFF"
    
    # Prepare MQTT message
    topic = "zigbee2mqtt/R7060/set"
    message = {"state": action}
    
    # Publish to MQTT broker
    success = mqtt_client.publish(topic, message)
```

### 3. **MQTT Broker (Mosquitto on Raspberry Pi)**
- Receives message on topic `zigbee2mqtt/R7060/set`
- Routes message to Zigbee2MQTT subscriber

### 4. **Zigbee2MQTT Processing**
- Receives MQTT message
- Converts to Zigbee command
- Sends to R7060 irrigation controller
- Device turns ON/OFF

### 5. **Device Status Feedback**
- R7060 reports status via Zigbee
- Zigbee2MQTT publishes to `zigbee2mqtt/R7060`
- FastAPI receives status update via MQTT subscription

## 🛠️ **Connection Solutions**

### **Option A: Run API on Raspberry Pi**
```bash
# SSH to your Raspberry Pi
ssh raspberry-user@192.168.8.151

# Clone and run API there
git clone [your-repo] irrigation-system
cd irrigation-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 irrigation_api.py

# Access from anywhere: http://192.168.8.151:8000
```

### **Option B: Configure WSL Networking**
```bash
# Test connectivity from WSL
wsl ping 192.168.8.151

# Check if port 1883 is accessible
wsl bash -c "timeout 5 bash -c '</dev/tcp/192.168.8.151/1883' && echo 'Port accessible' || echo 'Port blocked'"
```

### **Option C: Windows Host Networking**
```bash
# Run API on Windows directly (not WSL)
python irrigation_api.py

# Windows can usually reach local network devices directly
```

## 🧪 **Testing Steps**

### 1. **Test MQTT Connection**
```bash
# Run our MQTT test script
python3 mqtt_test.py
```

### 2. **Test API Endpoints**
```bash
# Test API connectivity
curl http://localhost:8000/api/health

# Test irrigation control (will show MQTT connection status)
curl -X POST http://localhost:8000/api/irrigation/control \
  -H "Content-Type: application/json" \
  -d '{"action": "ON"}'
```

### 3. **Monitor MQTT Messages**
```bash
# On Raspberry Pi, monitor all MQTT traffic
mosquitto_sub -h localhost -t "zigbee2mqtt/#" -v

# Publish test message manually
mosquitto_pub -h localhost -t "zigbee2mqtt/R7060/set" -m '{"state": "ON"}'
```

## 📡 **MQTT Topics Your API Uses**

### **Command Topics (API → Device)**
```
zigbee2mqtt/R7060/set          # Send commands to irrigation controller
zigbee2mqtt/E6/set             # Send commands to temperature sensor
```

### **Status Topics (Device → API)**
```
zigbee2mqtt/R7060              # Irrigation controller status
zigbee2mqtt/E6                 # Temperature sensor readings
```

## 🔧 **Troubleshooting**

### **"Connection Refused" Errors**
```bash
# Check if Mosquitto is running
ssh raspberry-user@192.168.8.151 'sudo systemctl status mosquitto'

# Check if port is listening
ssh raspberry-user@192.168.8.151 'netstat -tlnp | grep 1883'

# Restart Mosquitto if needed
ssh raspberry-user@192.168.8.151 'sudo systemctl restart mosquitto'
```

### **WSL Network Issues**
```bash
# Get WSL IP address
wsl hostname -I

# Test from Windows PowerShell instead of WSL
python irrigation_api.py
```

### **Firewall Issues**
```bash
# On Raspberry Pi, check if firewall allows MQTT
sudo ufw status
sudo ufw allow 1883/tcp  # If needed
```

## 🎯 **API Command Examples**

Once connected, these API calls will send MQTT commands:

```bash
# Turn irrigation ON
curl -X POST http://192.168.8.151:8000/api/irrigation/control \
  -H "Content-Type: application/json" \
  -d '{"action": "ON"}'

# Schedule 30-second watering
curl -X POST http://192.168.8.151:8000/api/irrigation/schedule \
  -H "Content-Type: application/json" \
  -d '{"duration": 30}'

# Get temperature data  
curl http://192.168.8.151:8000/api/sensor/temperature
```

The API automatically handles the MQTT communication, device control, and status monitoring!