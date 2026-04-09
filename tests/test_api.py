#!/usr/bin/env python3
"""
Test script for Irrigation System FastAPI
Demonstrates how to control devices via the REST API
"""

import requests
import json
import time

# API Configuration
API_BASE_URL = "http://localhost:8000"

def test_api_connection():
    """Test basic API connectivity"""
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print("🌐 API Connection Test:")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False

def test_health_check():
    """Test health check endpoint"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/health")
        print("\n💊 Health Check:")
        print(f"Status: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
    except Exception as e:
        print(f"❌ Error checking health: {e}")

def get_api_docs():
    """Show API documentation URLs"""
    print(f"\n📚 API Documentation:")
    print(f"   Interactive Docs: {API_BASE_URL}/docs")
    print(f"   Alternative Docs: {API_BASE_URL}/redoc")
    print("   Open these URLs in your browser for complete API documentation!")

def get_system_status():
    """Get comprehensive system status"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/system/status")
        print("\n📊 System Status:")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error getting system status: {e}")

def get_temperature_data():
    """Get current temperature sensor data"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/sensor/temperature")
        print("\n🌡️ Temperature Sensor Data:")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        elif response.status_code == 404:
            print("📭 No temperature data available yet")
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error getting temperature data: {e}")

def control_irrigation(action):
    """Control irrigation system (ON/OFF)"""
    try:
        data = {"action": action}
        response = requests.post(
            f"{API_BASE_URL}/api/irrigation/control",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\n💧 Irrigation Control ({action}):")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            error_detail = response.json().get('detail', response.text)
            print(f"Error: {error_detail}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error controlling irrigation: {e}")
        return False

def schedule_irrigation(duration_seconds):
    """Schedule irrigation for specific duration"""
    try:
        data = {"duration": duration_seconds}
        response = requests.post(
            f"{API_BASE_URL}/api/irrigation/schedule",
            json=data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\n⏰ Schedule Irrigation ({duration_seconds}s):")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        else:
            error_detail = response.json().get('detail', response.text)
            print(f"Error: {error_detail}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error scheduling irrigation: {e}")
        return False

def get_irrigation_status():
    """Get current irrigation system status"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/irrigation/status")
        print("\n🚿 Irrigation Status:")
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2))
        elif response.status_code == 404:
            print("📭 No irrigation status available yet")
        else:
            print(f"Error {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Error getting irrigation status: {e}")

def main():
    """Run API tests"""
    print("🌱 FastAPI Automated Irrigation System - API Test")  
    print("=" * 55)
    
    # Test API connection
    if not test_api_connection():
        print("❌ Cannot connect to API. Make sure the FastAPI server is running.")
        print(f"   Start it with: python irrigation_api.py")
        return
    
    # Show API documentation
    get_api_docs()
    
    # Test health check
    test_health_check()
    
    # Get system status
    get_system_status()
    
    # Get temperature data
    get_temperature_data()
    
    # Get irrigation status
    get_irrigation_status()
    
    # Interactive control
    print("\n🎮 Interactive Control Options:")
    print("1. Turn irrigation ON")
    print("2. Turn irrigation OFF") 
    print("3. Schedule irrigation for 10 seconds")
    print("4. Schedule irrigation for 30 seconds")
    print("5. View API docs URLs")
    print("6. Exit")
    
    while True:
        try:
            choice = input("\nEnter choice (1-6): ").strip()
            
            if choice == '1':
                control_irrigation("ON")
            elif choice == '2':
                control_irrigation("OFF")
            elif choice == '3':
                schedule_irrigation(10)
            elif choice == '4':
                schedule_irrigation(30)
            elif choice == '5':
                get_api_docs()
            elif choice == '6':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-6.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == '__main__':
    main()