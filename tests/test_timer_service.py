#!/usr/bin/env python3
"""
Test MQTT Timer Service functionality
"""
import paho.mqtt.client as mqtt
import json
import time
import threading

class TimerServiceTester:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.responses = []
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ Connected to MQTT broker for testing")
            # Subscribe to status updates and device responses
            client.subscribe("irrigation/status/+")
            client.subscribe("zigbee2mqtt/0x540f57fffe890af8")
        else:
            print(f"❌ Failed to connect. Return code: {rc}")
            
    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = msg.payload.decode()
            
            print(f"📨 Received: {topic}")
            try:
                json_payload = json.loads(payload)
                print(f"   Data: {json.dumps(json_payload, indent=2)}")
            except:
                print(f"   Data: {payload}")
            print()
            
            self.responses.append({"topic": topic, "payload": payload})
            
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def test_schedule_request(self, duration=10):
        """Test irrigation scheduling"""
        print(f"🧪 Testing irrigation schedule: {duration} seconds")
        
        schedule_request = {
            "device": "0x540f57fffe890af8",
            "duration": duration,
            "action": "schedule",
            "test_mode": True
        }
        
        print(f"📤 Sending schedule request...")
        result = self.client.publish("irrigation/schedule/request", 
                                   json.dumps(schedule_request))
        
        if result.rc == 0:
            print("✅ Schedule request sent successfully")
        else:
            print("❌ Failed to send schedule request")
            
    def test_control_request(self, action):
        """Test direct irrigation control"""
        print(f"🧪 Testing irrigation control: {action}")
        
        control_request = {
            "device": "0x540f57fffe890af8", 
            "action": action,
            "test_mode": True
        }
        
        print(f"📤 Sending control request...")
        result = self.client.publish("irrigation/control/request",
                                   json.dumps(control_request))
        
        if result.rc == 0:
            print("✅ Control request sent successfully")
        else:
            print("❌ Failed to send control request")
    
    def start_testing(self):
        """Run the test suite"""
        try:
            print("🚀 Starting Timer Service Tests")
            print("=" * 50)
            
            self.client.connect("localhost", 1883, 60)
            self.client.loop_start()
            time.sleep(2)
            
            print("\n🎯 Test 1: Direct ON command")
            self.test_control_request("ON")
            time.sleep(3)
            
            print("\n🎯 Test 2: Direct OFF command") 
            self.test_control_request("OFF")
            time.sleep(3)
            
            print("\n🎯 Test 3: 10-second irrigation schedule")
            self.test_schedule_request(10)
            print("⏰ Waiting for auto-turnoff...")
            
            # Wait for the schedule to complete
            for i in range(15):
                time.sleep(1)
                print(f"   {i+1}/15 seconds", end='\r')
            
            print("\n\n📊 Test Summary:")
            print(f"Total responses received: {len(self.responses)}")
            
            self.client.loop_stop()
            self.client.disconnect()
            
            print("✅ Testing completed!")
            
        except Exception as e:
            print(f"❌ Error during testing: {e}")

if __name__ == "__main__":
    tester = TimerServiceTester()
    tester.start_testing()