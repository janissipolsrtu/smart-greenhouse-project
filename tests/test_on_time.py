#!/usr/bin/env python3
"""
Test if the R7060 irrigation controller supports on_time parameter
"""
import paho.mqtt.client as mqtt
import json
import time

DEVICE_ID = "0x540f57fffe890af8"

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = json.loads(msg.payload.decode())
        
        if DEVICE_ID in topic:
            print(f"Device Response: {payload}")
            
    except Exception as e:
        print(f"Error: {e}")

def test_on_time_feature():
    client = mqtt.Client()
    client.on_message = on_message
    
    print(f"🧪 Testing on_time feature for {DEVICE_ID}...")
    
    try:
        client.connect("192.168.8.151", 1883, 60)
        client.subscribe(f"zigbee2mqtt/{DEVICE_ID}")
        client.loop_start()
        
        # Test 1: Basic ON command (baseline)
        print("\n📝 Test 1: Basic ON command")
        basic_command = {"state": "ON"}
        client.publish(f"zigbee2mqtt/{DEVICE_ID}/set", json.dumps(basic_command))
        time.sleep(3)
        
        # Test 2: ON with on_time parameter (10 seconds)
        print("\n📝 Test 2: ON with on_time=10 seconds")
        timed_command = {"state": "ON", "on_time": 10}
        client.publish(f"zigbee2mqtt/{DEVICE_ID}/set", json.dumps(timed_command))
        
        print("⏰ Waiting 15 seconds to see if device auto-turns OFF...")
        for i in range(15):
            time.sleep(1)
            print(f"   {i+1}/15 seconds", end='\r')
            
        print("\n")
        
        # Test 3: ON with on_time and off_wait_time
        print("\n📝 Test 3: ON with on_time=5 and off_wait_time=3")
        advanced_command = {"state": "ON", "on_time": 5, "off_wait_time": 3}
        client.publish(f"zigbee2mqtt/{DEVICE_ID}/set", json.dumps(advanced_command))
        
        print("⏰ Waiting 10 seconds...")
        for i in range(10):
            time.sleep(1)
            print(f"   {i+1}/10 seconds", end='\r')
            
        print("\n")
        
        # Cleanup - ensure device is OFF
        print("\n🧹 Cleanup: Turning device OFF")
        cleanup = {"state": "OFF"}
        client.publish(f"zigbee2mqtt/{DEVICE_ID}/set", json.dumps(cleanup))
        time.sleep(2)
        
        client.loop_stop()
        client.disconnect()
        
        print("\n✅ Test completed!")
        print("\nResults analysis:")
        print("- If device supports on_time: You should see automatic OFF after specified time")
        print("- If device doesn't support on_time: Device stays ON until manual OFF")
        
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_on_time_feature()