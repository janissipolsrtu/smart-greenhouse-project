#!/usr/bin/env python3
"""
Test script for the decoupled irrigation system
"""
import requests
import json
from datetime import datetime, timedelta

def test_irrigation_plan_creation():
    """Create a test irrigation plan"""
    
    # Calculate a time 2 minutes from now
    future_time = datetime.now() + timedelta(minutes=2)
    
    # Create test irrigation plan
    plan_data = {
        "scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration": 30,
        "description": "Test APScheduler integration",
        "timezone": "UTC"
    }
    
    print(f"Creating irrigation plan for: {plan_data['scheduled_time']}")
    
    try:
        response = requests.post(
            "http://localhost:8000/api/irrigation/plan",
            json=plan_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ Successfully created irrigation plan!")
        else:
            print("❌ Failed to create irrigation plan")
            
    except Exception as e:
        print(f"Error: {e}")

def test_get_plans():
    """Get current irrigation plans"""
    try:
        response = requests.get("http://localhost:8000/api/irrigation/plans")
        print(f"Current plans: {response.json()}")
    except Exception as e:
        print(f"Error getting plans: {e}")

if __name__ == "__main__":
    print("🧪 Testing decoupled irrigation system...")
    test_irrigation_plan_creation()
    test_get_plans()