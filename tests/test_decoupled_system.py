#!/usr/bin/env python3
"""
Test script for the decoupled irrigation system
"""
import requests
import json
from datetime import datetime, timedelta

def test_watering_cycle_creation():
    """Create a test watering cycle"""
    
    # Calculate a time 2 minutes from now
    future_time = datetime.now() + timedelta(minutes=2)
    
    # Create test watering cycle
    cycle_data = {
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
            print("✅ Successfully created watering cycle!")
        else:
            print("❌ Failed to create watering cycle")
            
    except Exception as e:
        print(f"Error: {e}")

def test_get_cycles():
    """Get current watering cycles"""
    try:
        response = requests.get("http://localhost:8000/api/watering/cycle")
        print(f"Current cycles: {response.json()}")
    except Exception as e:
        print(f"Error getting cycles: {e}")

if __name__ == "__main__":
    print("🧪 Testing decoupled watering system...")
    test_watering_cycle_creation()
    test_get_cycles()