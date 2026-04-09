#!/usr/bin/env python3
"""
Test script to verify Raspberry Pi to Backend communication
Run this on either Raspberry Pi or main server to test the connection
"""

import requests
import json
import sys
import time
from datetime import datetime

def test_backend_health(backend_url):
    """Test if backend health endpoint is working"""
    try:
        health_url = f"{backend_url}/api/health/"
        response = requests.get(health_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Backend Health Check: PASS")
            print(f"   Status: {data.get('status')}")
            print(f"   Database: {data.get('database')}")
            print(f"   Total Sensor Records: {data.get('total_sensor_records', 0)}")
            print(f"   Recent Readings (24h): {data.get('recent_readings_24h', 0)}")
            return True
        else:
            print(f"❌ Backend Health Check: FAIL (Status: {response.status_code})")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Backend Health Check: FAIL (Error: {e})")
        return False

def test_bulk_sensor_api(backend_url):
    """Test sending sample sensor data to bulk API"""
    try:
        api_url = f"{backend_url}/api/sensor-data/bulk/"
        
        # Sample sensor data
        test_data = {
            "readings": [
                {
                    "device_name": "test_sensor_001",
                    "temperature": 22.5,
                    "humidity": 65,
                    "linkquality": 200,
                    "max_temperature": 35.0,
                    "temperature_unit": "celsius",
                    "raw_data": {
                        "temperature": 22.5,
                        "humidity": 65,
                        "linkquality": 200,
                        "test": True
                    },
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                },
                {
                    "device_name": "test_sensor_002", 
                    "temperature": 21.8,
                    "humidity": 70,
                    "linkquality": 180,
                    "max_temperature": 35.0,
                    "temperature_unit": "celsius",
                    "raw_data": {
                        "temperature": 21.8,
                        "humidity": 70,
                        "linkquality": 180,
                        "test": True
                    },
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
            ],
            "source": "test_script",
            "collected_at": datetime.utcnow().isoformat() + "Z"
        }
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(api_url, json=test_data, headers=headers, timeout=10)
        
        if response.status_code in [200, 201]:
            data = response.json()
            print("✅ Bulk Sensor API Test: PASS")
            print(f"   Saved: {data.get('saved_count', 0)} readings")
            print(f"   Status: {data.get('status')}")
            if data.get('errors'):
                print(f"   Errors: {data.get('errors')[:3]}...")  # Show first 3 errors
            return True
        else:
            print(f"❌ Bulk Sensor API Test: FAIL (Status: {response.status_code})")
            print(f"   Response: {response.text[:200]}...")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Bulk Sensor API Test: FAIL (Error: {e})")
        return False

def test_web_dashboard(backend_url):
    """Test if web dashboard is accessible"""
    try:
        dashboard_url = f"{backend_url}/temperature/"
        response = requests.get(dashboard_url, timeout=10)
        
        if response.status_code == 200:
            print("✅ Temperature Dashboard: PASS")
            print(f"   Dashboard accessible at: {dashboard_url}")
            return True
        else:
            print(f"❌ Temperature Dashboard: FAIL (Status: {response.status_code})")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Temperature Dashboard: FAIL (Error: {e})")
        return False

def query_recent_data(backend_url):
    """Query recent sensor data to verify storage"""
    try:
        api_url = f"{backend_url}/api/sensor-data/?hours=1"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            readings = data.get('data', [])
            print("✅ Data Query Test: PASS")
            print(f"   Recent readings (1h): {len(readings)}")
            
            if readings:
                latest = readings[0]
                print(f"   Latest reading: {latest.get('device_name')} - {latest.get('temperature')}°C")
            
            return True
        else:
            print(f"❌ Data Query Test: FAIL (Status: {response.status_code})")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Data Query Test: FAIL (Error: {e})")
        return False

def main():
    """Main test function"""
    print("🧪 Raspberry Pi ↔ Backend Communication Test")
    print("=" * 50)
    print(f"Test time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")
    
    # Get backend URL
    if len(sys.argv) > 1:
        backend_url = sys.argv[1]
    else:
        backend_url = input("🌐 Enter backend server URL (e.g. http://192.168.8.100:8080): ").strip()
    
    if not backend_url.startswith("http"):
        backend_url = f"http://{backend_url}"
    
    backend_url = backend_url.rstrip('/')
    
    print(f"Testing backend: {backend_url}")
    print("")
    
    # Run tests
    results = []
    
    print("1️⃣ Testing backend health...")
    results.append(("Backend Health", test_backend_health(backend_url)))
    print("")
    
    print("2️⃣ Testing bulk sensor API...")
    results.append(("Bulk API", test_bulk_sensor_api(backend_url)))
    print("")
    
    print("3️⃣ Testing web dashboard...")
    results.append(("Web Dashboard", test_web_dashboard(backend_url)))
    print("")
    
    print("4️⃣ Testing data query...")
    results.append(("Data Query", query_recent_data(backend_url)))
    print("")
    
    # Summary
    print("📊 Test Summary")
    print("-" * 30)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        icon = "✅" if result else "❌"
        print(f"{icon} {test_name}: {status}")
    
    print("")
    print(f"Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("")
        print("🎉 All tests passed! Communication is working correctly.")
        print("")
        print("🍓 Your Raspberry Pi should be able to:")
        print("   - Send sensor data to the backend")
        print("   - View data in the temperature dashboard")
        print("   - Handle network interruptions gracefully")
        
    elif passed >= 2:
        print("")
        print("⚠️ Partial functionality detected.")
        print("   Basic communication works, but some features may need attention.")
        
    else:
        print("")
        print("❌ Communication test failed.")
        print("")
        print("🔍 Troubleshooting tips:")
        print("   - Check if backend server is running")
        print("   - Verify network connectivity between devices")
        print("   - Ensure firewall allows traffic on port 8080")
        print("   - Check backend server logs for errors")
    
    print("")
    print("🔧 Useful commands:")
    print(f"   Health check: curl {backend_url}/api/health/")
    print(f"   Dashboard: {backend_url}/temperature/")

if __name__ == "__main__":
    main()