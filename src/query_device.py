#!/usr/bin/env python3
"""
Query Zigbee device capabilities
"""
import paho.mqtt.client as mqtt
import json
import time

DEVICE_ID = "0x540f57fffe890af8"

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode()
        
        print(f"Topic: {topic}")
        if topic == "zigbee2mqtt/bridge/devices":
            devices = json.loads(payload)
            for device in devices:
                if device.get('ieee_address') == DEVICE_ID:
                    print(f"Found device: {DEVICE_ID}")
                    print(f"Model: {device.get('model_id', 'Unknown')}")
                    print(f"Manufacturer: {device.get('manufacturer', 'Unknown')}")
                    print(f"Definition: {json.dumps(device.get('definition', {}), indent=2)}")
                    return
        else:
            print(f"Message: {payload}")
        print("-" * 60)
    except Exception as e:
        print(f"Error: {e}")

def query_device_capabilities():
    client = mqtt.Client()
    client.on_message = on_message
    
    print(f"🔍 Querying capabilities for device {DEVICE_ID}...")
    
    try:
        client.connect("192.168.8.151", 1883, 60)
        
        # Subscribe to relevant topics
        client.subscribe("zigbee2mqtt/bridge/devices")
        client.subscribe(f"zigbee2mqtt/{DEVICE_ID}")
        client.subscribe("zigbee2mqtt/bridge/response/device/options")
        
        client.loop_start()
        
        # Request device list
        print("📋 Requesting device list...")
        client.publish("zigbee2mqtt/bridge/request/devices", "")
        
        time.sleep(2)
        
        # Request specific device info
        print("🔎 Requesting device options...")
        client.publish("zigbee2mqtt/bridge/request/device/options", 
                      json.dumps({"id": DEVICE_ID}))
        
        time.sleep(2)
        
        # Try to get device attributes
        print("📊 Requesting device attributes...")
        client.publish(f"zigbee2mqtt/{DEVICE_ID}/get", json.dumps({}))
        
        time.sleep(3)
        
        client.loop_stop()
        client.disconnect()
        
    except Exception as e:
        print(f"Error querying device: {e}")

if __name__ == "__main__":
    query_device_capabilities()