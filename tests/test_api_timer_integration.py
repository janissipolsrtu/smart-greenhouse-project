#!/usr/bin/env python3
"""
Test Timer Service Integration via FastAPI
"""
import requests
import time
import json

API_BASE = "http://localhost:8000"

def test_timer_service_integration():
    """Test the timer service through FastAPI endpoints"""
    
    print("🧪 Testing Timer Service Integration via FastAPI")
    print("=" * 60)
    
    # Test 1: Check API health
    print("\n🔍 Test 1: API Health Check")
    try:
        response = requests.get(f"{API_BASE}/api/health")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Test 2: Check system status 
    print("\n🔍 Test 2: System Status")
    try:
        response = requests.get(f"{API_BASE}/api/system/status")
        if response.status_code == 200:
            data = response.json()
            print(f"MQTT Connected: {data['data']['system']['mqtt_connected']}")
            print(f"Timing Mode: {data['data']['system']['timing_mode']}")
            if data['data']['timer_service']:
                print(f"Timer Service Status: Available")
            else:
                print(f"Timer Service Status: No data yet")
        else:
            print(f"Status check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ System status check failed: {e}")
    
    # Test 3: Direct irrigation control
    print("\n🎯 Test 3: Direct Control (ON)")
    try:
        response = requests.post(f"{API_BASE}/api/irrigation/control", 
                               json={"action": "ON"})
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ ON command sent via timer service")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ Control failed: {response.json()}")
    except Exception as e:
        print(f"❌ Control test failed: {e}")
    
    time.sleep(3)
    
    # Test 4: Turn OFF
    print("\n🎯 Test 4: Direct Control (OFF)")
    try:
        response = requests.post(f"{API_BASE}/api/irrigation/control", 
                               json={"action": "OFF"})
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ OFF command sent via timer service")
        else:
            print(f"❌ Control failed: {response.json()}")
    except Exception as e:
        print(f"❌ Control test failed: {e}")
    
    time.sleep(2)
    
    # Test 5: Schedule irrigation
    print("\n⏰ Test 5: Schedule Irrigation (10 seconds)")
    try:
        response = requests.post(f"{API_BASE}/api/irrigation/schedule", 
                               json={"duration": 10})
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Schedule request sent via timer service")
            print(f"Duration: {result['data']['duration']} seconds")
            print(f"Timing Mode: {result['data']['timing_mode']}")
            print(f"Expected OFF time: {result['data']['expected_off_time']}")
            
            # Monitor for timer service updates
            print("\n📊 Monitoring timer service status...")
            for i in range(15):
                time.sleep(1)
                try:
                    status_resp = requests.get(f"{API_BASE}/api/irrigation/schedule/status", timeout=2)
                    if status_resp.status_code == 200:
                        status_data = status_resp.json()
                        print(f"   Timer Status: {status_data}")
                        break
                except:
                    pass
                print(f"   {i+1}/15 seconds - waiting for status updates...", end='\r')
            
        else:
            print(f"❌ Schedule failed: {response.json()}")
    except Exception as e:
        print(f"❌ Schedule test failed: {e}")
    
    # Test 6: Final status check
    print("\n\n📋 Test 6: Final Status Check")
    try:
        response = requests.get(f"{API_BASE}/api/devices")
        if response.status_code == 200:
            data = response.json()
            print("Device Status Summary:")
            if 'irrigation_controller' in data['data']['device_status']:
                controller = data['data']['device_status']['irrigation_controller']
                print(f"  Irrigation Controller: {controller}")
            else:
                print("  No irrigation controller data available")
                
            if data['data']['sensor_data']:
                print(f"  Temperature Sensor: Available")
            else:
                print("  No sensor data available")
    except Exception as e:
        print(f"❌ Final status check failed: {e}")
    
    print("\n✅ Timer Service Integration Test Completed!")
    print("\nNote: If timer service is not running on Pi, you'll see")
    print("successful API responses but no device actions.")

if __name__ == "__main__":
    test_timer_service_integration()