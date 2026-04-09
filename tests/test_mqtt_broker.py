#!/usr/bin/env python3
"""
MQTT Test Script - Test centralized Mosquitto broker functionality
"""

import paho.mqtt.client as mqtt
import json
import time
import threading
import sys
from datetime import datetime

class MQTTTester:
    def __init__(self, broker_host, broker_port=1883):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.received_messages = []
        self.connected = False
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"✅ Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.connected = True
            # Subscribe to test topics
            client.subscribe("sensor/+")
            client.subscribe("test/+")
            client.subscribe("zigbee2mqtt/+")
            print("📡 Subscribed to topics: sensor/+, test/+, zigbee2mqtt/+")
        else:
            print(f"❌ Failed to connect to MQTT broker, code: {rc}")
            self.connected = False
    
    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        print(f"📥 [{timestamp}] {topic}: {payload}")
        self.received_messages.append({
            'topic': topic,
            'payload': payload,
            'timestamp': timestamp
        })
    
    def test_connection(self):
        """Test basic MQTT connection"""
        print(f"🔌 Testing MQTT connection to {self.broker_host}:{self.broker_port}")
        
        client = mqtt.Client(client_id="mqtt_tester")
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        
        try:
            client.connect(self.broker_host, self.broker_port, 60)
            client.loop_start()
            
            # Wait for connection
            for i in range(10):
                if self.connected:
                    break
                time.sleep(0.5)
            
            if not self.connected:
                print("❌ Could not establish MQTT connection")
                return False
            
            # Test publishing messages
            test_messages = [
                ("test/connection", "Connection test"),
                ("sensor/temperature", json.dumps({
                    "temperature": 22.5,
                    "humidity": 65,
                    "device": "test_sensor_001"
                })),
                ("sensor/humidity", json.dumps({
                    "humidity": 70,
                    "temperature": 21.8,
                    "device": "test_sensor_002"
                })),
                ("zigbee2mqtt/test_device", json.dumps({
                    "temperature": 23.1,
                    "humidity": 68,
                    "linkquality": 200
                }))
            ]
            
            print("\n📤 Publishing test messages...")
            for topic, message in test_messages:
                result = client.publish(topic, message)
                if result.rc == 0:
                    print(f"✅ Published to {topic}")
                else:
                    print(f"❌ Failed to publish to {topic}")
                time.sleep(0.5)
            
            # Wait to receive messages
            print("\n⏳ Waiting for messages...")
            time.sleep(3)
            
            client.loop_stop()
            client.disconnect()
            
            # Report results
            print(f"\n📊 Test Results:")
            print(f"   Messages sent: {len(test_messages)}")  
            print(f"   Messages received: {len(self.received_messages)}")
            
            if len(self.received_messages) > 0:
                print("✅ MQTT broker is working correctly")
                return True
            else:
                print("⚠️ No messages received - check broker configuration")
                return False
                
        except Exception as e:
            print(f"❌ MQTT test failed: {e}")
            return False

def main():
    """Main test function"""
    print("🦟 Mosquitto MQTT Broker Test")
    print("=" * 40)
    print("")
    
    # Get broker address
    if len(sys.argv) > 1:
        broker_host = sys.argv[1]
    else:
        broker_host = input("🌐 Enter MQTT broker IP address (e.g. 192.168.8.100): ").strip()
    
    if not broker_host:
        print("❌ No broker address provided")
        return
    
    # Run test
    tester = MQTTTester(broker_host)
    success = tester.test_connection()
    
    print("")
    if success:
        print("🎉 MQTT broker test completed successfully!")
        print("")
        print("🍓 Ready for sensor connections!")
        print("   Sensors can connect to:")
        print(f"   - Broker: {broker_host}:1883")
        print("   - Topics: sensor/*, zigbee2mqtt/*")
        print("")
        print("📡 Example sensor publish:")
        print(f"   mosquitto_pub -h {broker_host} -t 'sensor/temp01' -m '{{\"temperature\":22.5,\"humidity\":65}}'")
        
    else:
        print("❌ MQTT broker test failed!")
        print("")
        print("🔍 Troubleshooting:")
        print("   - Check if Mosquitto container is running")
        print("   - Verify firewall allows port 1883")
        print("   - Confirm IP address is correct")
        print(f"   - Test with: telnet {broker_host} 1883")

if __name__ == "__main__":
    main()