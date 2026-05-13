#!/usr/bin/env python3
"""Integration tests for FastAPI device pairing endpoints."""

import json
import requests

API_BASE_URL = "http://localhost:8000"
PAIRING_URL = f"{API_BASE_URL}/api/device/pairing"
PAIRING_STATUS_URL = f"{API_BASE_URL}/api/device/pairing-status"

# Credentials provided earlier in this workspace conversation.
MQTT_BROKER_IP = "192.168.8.151"
MQTT_PORT = 1883
MQTT_USERNAME = "mosquitto_api_user1"
MQTT_PASSWORD = "mosquitto_password$"


def _print_response(label: str, response: requests.Response) -> None:
    print(f"\n{label}")
    print(f"Status: {response.status_code}")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except Exception:
        print(response.text)


def test_api_device_pairing() -> bool:
    """Test POST /api/device/pairing with known MQTT credentials."""
    payload = {
        "broker_ip": MQTT_BROKER_IP,
        "port": MQTT_PORT,
        "mqtt_username": MQTT_USERNAME,
        "mqtt_password": MQTT_PASSWORD,
        "duration": 60,
    }

    response = requests.post(PAIRING_URL, json=payload, timeout=20)
    _print_response("[Pairing] POST /api/device/pairing", response)

    if response.status_code != 200:
        return False

    data = response.json()
    if not data.get("success"):
        return False

    response_data = data.get("data") or {}
    expected_payload = {"time": 60}

    return (
        response_data.get("request_topic") == "zigbee2mqtt/bridge/request/permit_join"
        and response_data.get("request_payload") == expected_payload
        and response_data.get("broker") == MQTT_BROKER_IP
        and response_data.get("port") == MQTT_PORT
    )


def test_api_device_pairing_status() -> bool:
    """Test POST /api/device/pairing-status listening on bridge event topic."""
    payload = {
        "broker_ip": MQTT_BROKER_IP,
        "port": MQTT_PORT,
        "mqtt_username": MQTT_USERNAME,
        "mqtt_password": MQTT_PASSWORD,
        "listen_seconds": 5,
    }

    response = requests.post(PAIRING_STATUS_URL, json=payload, timeout=30)
    _print_response("[Pairing Status] POST /api/device/pairing-status", response)

    if response.status_code != 200:
        return False

    data = response.json()
    if not data.get("success"):
        return False

    response_data = data.get("data") or {}

    return (
        response_data.get("topic") == "zigbee2mqtt/bridge/event"
        and isinstance(response_data.get("paired_detected"), bool)
        and isinstance(response_data.get("events_count"), int)
    )


def main() -> int:
    print("Device Pairing API Integration Tests")
    print("=" * 40)

    results = {
        "POST /api/device/pairing": test_api_device_pairing(),
        "POST /api/device/pairing-status": test_api_device_pairing_status(),
    }

    print("\nSummary")
    print("=" * 40)
    passed = 0
    for test_name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"{status}: {test_name}")
        if ok:
            passed += 1

    print(f"\nResult: {passed}/{len(results)} tests passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
