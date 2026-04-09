#!/usr/bin/env python3
"""
MQTT Connection Test Script
Tests direct MQTT communication with your Raspberry Pi
"""

import paho.mqtt.client as mqtt
import json
import time

# Configuration
MQTT_BROKER = "192.168.8.151"  # Your Raspberry Pi
MQTT_PORT = 1883

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to MQTT broker successfully!")
        print(f"   Broker: {MQTT_BROKER}:{MQTT_PORT}")
        
        # Subscribe to all zigbee2mqtt topics
        client.subscribe("zigbee2mqtt/#")
        print("📡 Subscribed to zigbee2mqtt topics")
    else:
        print(f"❌ Failed to connect. Return code: {rc}")

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        print(f"📨 Received: {topic}")
        print(f"   Data: {json.dumps(payload, indent=2)}")
        print("-" * 50)
    except Exception as e:
        print(f"❌ Error processing message: {e}")

def test_mqtt_connection():
    """Test MQTT connection and device communication"""
    print("🌱 MQTT Connection Test")
    print("=" * 40)
    
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"🔌 Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Start the loop
        client.loop_start()
        
        print("👂 Listening for messages (press Ctrl+C to stop)...")
        print("   You should see messages from your Zigbee devices")
        print()
        
        # Keep listening for messages
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n👋 Stopping MQTT test...")
        client.loop_stop()
        client.disconnect()
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("\n🔧 Troubleshooting suggestions:")
        print("   1. Ensure Raspberry Pi is reachable: ping 192.168.8.151")
        print("   2. Check if Mosquitto is running: ssh pi@192.168.8.151 'sudo systemctl status mosquitto'")
        print("   3. Verify firewall allows port 1883")
        print("   4. Try running this from the Raspberry Pi directly")

def send_test_command():
    """Send a test command to irrigation controller"""
    print("\n🧪 Sending test irrigation command...")
    
    client = mqtt.Client()
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Send ON command to irrigation controller
        topic = "zigbee2mqtt/0x540f57fffe890af8/set"
        message = {"state": "ON"}
        
        result = client.publish(topic, json.dumps(message))
        if result.rc == 0:
            print(f"✅ Command sent successfully!")
            print(f"   Topic: {topic}")
            print(f"   Message: {message}")
        else:
            print(f"❌ Failed to send command. Result code: {result.rc}")
            
        time.sleep(2)
        
        # Send OFF command
        message = {"state": "OFF"}
        result = client.publish(topic, json.dumps(message))
        if result.rc == 0:
            print(f"✅ OFF command sent successfully!")
            
        client.disconnect()
        
    except Exception as e:
        print(f"❌ Error sending command: {e}")

if __name__ == "__main__":
    print("🌱 MQTT Test Suite for Irrigation System")
    print("=" * 50)
    print()
    print("Choose an option:")
    print("1. Test MQTT connection and listen for messages")
    print("2. Send test irrigation commands")
    print("3. Exit")
    
    while True:
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == '1':
            test_mqtt_connection()
            break
        elif choice == '2':
            send_test_command()
            break
        elif choice == '3':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-3.")