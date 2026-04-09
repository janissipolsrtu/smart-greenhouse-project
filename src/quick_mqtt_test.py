#!/usr/bin/env python3
"""
Quick MQTT connectivity test
"""
import paho.mqtt.client as mqtt
import time
import sys

MQTT_BROKER = "192.168.8.151"
MQTT_PORT = 1883

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ MQTT broker is UP and running!")
        print(f"   Connected to {MQTT_BROKER}:{MQTT_PORT}")
        client.disconnect()
    else:
        print(f"❌ MQTT connection failed with code {rc}")

def on_disconnect(client, userdata, rc):
    print("   Disconnected from MQTT broker")

def test_mqtt_connection():
    print(f"🔌 Testing MQTT connection to {MQTT_BROKER}:{MQTT_PORT}...")
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        
        # Wait for connection
        time.sleep(3)
        
        client.loop_stop()
        
    except Exception as e:
        print(f"❌ MQTT connection error: {e}")
        return False
        
    return True

if __name__ == "__main__":
    test_mqtt_connection()