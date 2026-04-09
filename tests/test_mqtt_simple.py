#!/usr/bin/env python3
"""
Simple MQTT Broker Test
Tests basic Mosquitto MQTT broker functionality
"""

import paho.mqtt.client as mqtt
import time
import sys
from datetime import datetime

def test_mqtt_broker(broker_ip):
    """Test MQTT broker connection and messaging"""
    
    print(f"🧪 Testing MQTT Broker at {broker_ip}:1883")
    print("=" * 40)
    
    messages_received = []
    connected = False
    
    def on_connect(client, userdata, flags, rc):
        nonlocal connected
        if rc == 0:
            print("✅ Connected to MQTT broker")
            connected = True
            client.subscribe("test/+")
            print("📡 Subscribed to test/+ topics")
        else:
            print(f"❌ Connection failed with code: {rc}")
    
    def on_message(client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"📥 [{timestamp}] {topic}: {payload}")
        messages_received.append((topic, payload))
    
    # Create client and connect
    client = mqtt.Client(client_id="mqtt_test_client")
    client.on_connect = on_connect
    client.on_message = on_message
    
    try:
        print(f"🔌 Connecting to {broker_ip}:1883...")
        client.connect(broker_ip, 1883, 60)
        client.loop_start()
        
        # Wait for connection
        for i in range(10):
            if connected:
                break
            time.sleep(0.5)
        
        if not connected:
            print("❌ Failed to connect to MQTT broker")
            return False
        
        # Send test messages
        test_messages = [
            ("test/hello", "world"),
            ("test/timestamp", datetime.now().isoformat()),
            ("test/number", "42")
        ]
        
        print("\n📤 Publishing test messages...")
        for topic, message in test_messages:
            result = client.publish(topic, message)
            if result.rc == 0:
                print(f"✅ Published: {topic} = {message}")
            else:
                print(f"❌ Failed to publish: {topic}")
            time.sleep(0.5)
        
        # Wait for messages
        print("\n⏳ Waiting to receive messages...")
        time.sleep(2)
        
        client.loop_stop()
        client.disconnect()
        
        # Results
        print(f"\n📊 Results:")
        print(f"   Messages sent: {len(test_messages)}")
        print(f"   Messages received: {len(messages_received)}")
        
        if len(messages_received) >= len(test_messages):
            print("✅ MQTT broker is working correctly!")
            return True
        else:
            print("⚠️ Some messages may not have been received")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def main():
    if len(sys.argv) > 1:
        broker_ip = sys.argv[1]
    else:
        broker_ip = input("Enter broker IP address: ").strip()
    
    success = test_mqtt_broker(broker_ip)
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 MQTT broker test completed successfully!")
        print(f"\nYour broker is ready at {broker_ip}:1883")
    else:
        print("❌ MQTT broker test failed!")
        print("\n🔍 Troubleshooting:")
        print("- Check if Mosquitto container is running")
        print("- Verify firewall allows port 1883") 
        print("- Confirm IP address is correct")

if __name__ == "__main__":
    main()