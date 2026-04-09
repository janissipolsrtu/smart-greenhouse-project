import requests
import json

def test_irrigation_control():
    """Test the irrigation control API endpoint"""
    
    url = "http://localhost:8000/api/irrigation/control"
    
    # Test turning irrigation ON
    print("Testing irrigation control API...")
    
    payload = {"action": "ON"}
    
    try:
        response = requests.post(url, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ API call successful!")
            print("This should have sent MQTT command to zigbee2mqtt/0x540f57fffe890af8/set")
            print(f"MQTT payload: {json.dumps({'state': 'ON'})}")
        else:
            print("❌ API call failed")
            print("The API converts:")
            print(f"  REST Input:  {json.dumps(payload)}")
            print(f"  MQTT Output: {json.dumps({'state': payload['action']})}")
            print("This matches your mosquitto_pub command format!")
            
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to API: {e}")
        print("Make sure the FastAPI server is running on port 8000")

if __name__ == "__main__":
    test_irrigation_control()