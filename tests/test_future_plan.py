import requests
import json
from datetime import datetime, timedelta

# Create a future irrigation plan (3 minutes from now)
future_time = (datetime.now() + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%S")

plan_data = {
    "scheduled_time": future_time,
    "duration": 45,
    "timezone": "UTC",
    "description": "TEST: Future irrigation - full workflow test"
}

print(f"Creating irrigation plan for: {future_time}")
try:
    response = requests.post("http://localhost:8000/api/irrigation/plan", json=plan_data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    
    if response.status_code == 200:
        data = response.json()
        plan_id = data['data']['plan']['id']
        print(f"✅ Created plan {plan_id} for {future_time}")
    else:
        print("❌ Failed to create plan")
        
except Exception as e:
    print(f"Error: {e}")