import requests
import json
from datetime import datetime, timedelta

# Create a future irrigation plan
plan_data = {
    "scheduled_time": "2026-04-05T19:48:00",
    "duration": 30,
    "timezone": "UTC",
    "description": "Future test irrigation - should be automatically scheduled"
}

print(f"Sending request to API at: {datetime.now()}")
print(f"Plan data: {json.dumps(plan_data, indent=2)}")

try:
    response = requests.post(
        "http://localhost:8000/api/irrigation/plan",
        json=plan_data,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        print("✅ Irrigation plan created successfully!")
    else:
        print("❌ Failed to create irrigation plan")
        
except Exception as e:
    print(f"Error making request: {e}")