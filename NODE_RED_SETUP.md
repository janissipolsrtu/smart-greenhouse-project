# Node-RED Irrigation Timer Setup

## Install Node-RED on Raspberry Pi
```bash
# On your Raspberry Pi (192.168.8.151)
sudo apt update
sudo apt install nodejs npm
sudo npm install -g --unsafe-perm node-red

# Install MQTT nodes (if not included)
cd ~/.node-red
npm install node-red-contrib-timer
```

## Start Node-RED
```bash
node-red
# Access at http://192.168.8.151:1880
```

## Flow Design
1. **MQTT In** node: Subscribe to `irrigation/schedule/request`
2. **Function** node: Parse schedule request, start timer
3. **MQTT Out** nodes: Send ON immediately, OFF after delay
4. **Status** nodes: Update irrigation status

## API Integration
Your FastAPI just sends:
```json
{
  "device": "0x540f57fffe890af8",
  "duration": 300,
  "action": "schedule"
}
```

To topic: `irrigation/schedule/request`

## Benefits
- ✅ Visual programming interface
- ✅ Built-in timer nodes
- ✅ MQTT integration
- ✅ Runs locally on Pi (no network latency)
- ✅ Can handle multiple irrigation zones
- ✅ Persistent across reboots