#!/usr/bin/env python3
"""Quick MQTT connection test"""
import paho.mqtt.client as mqtt

BROKER = '192.168.8.151'
PORT = 1883
USERNAME = 'mosquitto_api_user1'
PASSWORD = 'mosquitto_password$'

def on_connect(client, userdata, flags, rc):
    codes = {
        0: 'SUCCESS: Connected!',
        1: 'FAILED: Incorrect protocol version',
        2: 'FAILED: Invalid client identifier',
        3: 'FAILED: Server unavailable',
        4: 'FAILED: Bad username or password',
        5: 'FAILED: Not authorised',
    }
    print(codes.get(rc, f'FAILED: Unknown code {rc}'))
    client.disconnect()

c = mqtt.Client(client_id='test_conn', protocol=mqtt.MQTTv311)
c.on_connect = on_connect
c.username_pw_set(USERNAME, PASSWORD)

print(f'Connecting to {BROKER}:{PORT} as {USERNAME}...')
try:
    c.connect(BROKER, PORT, 10)
    c.loop_forever()
except Exception as e:
    print(f'ERROR: {e}')
