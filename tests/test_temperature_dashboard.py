#!/usr/bin/env python3
"""
Temperature Dashboard Test Script
Tests the temperature sensor data collection and dashboard functionality
"""

import requests
import json
import time
import paho.mqtt.publish as publish
from datetime import datetime

def test_database_connection():
    """Test if Django server is responding"""
    try:
        response = requests.get('http://localhost:8080', timeout=5)
        if response.status_code == 200:
            print("✅ Django web server is running")
            return True
        else:
            print(f"❌ Django server returned status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Django server not accessible: {e}")
        return False

def test_temperature_dashboard():
    """Test if temperature dashboard is accessible"""
    try:
        response = requests.get('http://localhost:8080/temperature/', timeout=5)
        if response.status_code == 200:
            print("✅ Temperature dashboard is accessible")
            return True
        else:
            print(f"❌ Temperature dashboard returned status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Temperature dashboard not accessible: {e}")
        return False

def test_sensor_api():
    """Test if sensor data API is working"""
    try:
        response = requests.get('http://localhost:8080/api/sensor-data/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Sensor API working - {len(data.get('data', []))} readings found")
            return True
        else:
            print(f"❌ Sensor API returned status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Sensor API not accessible: {e}")
        return False

def send_test_sensor_data():
    """Send test sensor data via MQTT"""
    print("🧪 Sending test sensor data...")
    
    test_data = {
        "temperature": 22.5,
        "humidity": 65,
        "linkquality": 200,
        "max_temperature": 35.0,
        "temperature_unit_convert": "celsius"
    }
    
    try:
        # Try to publish test data
        publish.single(
            "zigbee2mqtt/test_sensor",
            json.dumps(test_data),
            hostname="192.168.8.151",
            port=1883,
            keepalive=60
        )
        print("✅ Test sensor data sent successfully")
        return True
    except Exception as e:
        print(f"⚠️ Could not send test data to MQTT broker: {e}")
        print("   This is normal if the MQTT broker isn't accessible")
        return False

def check_docker_containers():
    """Check if required Docker containers are running"""
    import subprocess
    
    print("🐳 Checking Docker containers...")
    
    try:
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Docker is not running or accessible")
            return False
            
        containers = result.stdout
        required_containers = [
            'irrigation-postgres',
            'irrigation-django-webapp',
            'irrigation-sensor-collector'
        ]
        
        running_containers = []
        for container in required_containers:
            if container in containers:
                running_containers.append(container)
                print(f"✅ {container} is running")
            else:
                print(f"❌ {container} is not running")
        
        return len(running_containers) >= 2  # At least postgres and django
        
    except Exception as e:
        print(f"❌ Could not check Docker containers: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Temperature Dashboard Test Suite")
    print("=" * 50)
    print(f"Test run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("")
    
    # Test results
    results = []
    
    # Check Docker containers
    results.append(("Docker Containers", check_docker_containers()))
    
    # Test web services
    results.append(("Django Web App", test_database_connection()))
    results.append(("Temperature Dashboard", test_temperature_dashboard()))
    results.append(("Sensor API", test_sensor_api()))
    
    # Test MQTT (optional)
    results.append(("MQTT Test Data", send_test_sensor_data()))
    
    # Print summary
    print("")
    print("📊 Test Summary")
    print("-" * 30)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        icon = "✅" if result else "❌"
        print(f"{icon} {test_name}: {status}")
        if result:
            passed += 1
    
    print("")
    print(f"Overall: {passed}/{total} tests passed")
    
    if passed >= 3:  # Django + Dashboard + API working
        print("")
        print("🎉 Temperature dashboard is working!")
        print("   Open http://localhost:8080/temperature/ to see your dashboard")
    elif passed >= 1:
        print("")
        print("⚠️ Partial functionality detected")
        print("   Some services may need troubleshooting")
    else:
        print("")
        print("❌ Temperature dashboard is not working")
        print("   Please check the setup guide: TEMPERATURE_DASHBOARD_SETUP.md")
    
    print("")
    print("💡 Tips:")
    print("   - Wait 1-2 minutes after starting containers for full initialization")
    print("   - Check container logs: docker logs <container-name>")
    print("   - Verify network connectivity to MQTT broker (192.168.8.151)")

if __name__ == "__main__":
    main()