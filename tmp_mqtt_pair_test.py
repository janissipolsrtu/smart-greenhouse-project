import json
import time
import threading
import paho.mqtt.client as mqtt

broker = "192.168.8.151"
port = 1883
username = "mosquitto_api_user1"
password = "mosquitto_password$"
sub_topic = "zigbee2mqtt-bridge-event"
pub_topic = "zigbee2mqtt/bridge/request/permit_join"

received = []
received_event = threading.Event()

client = mqtt.Client(protocol=mqtt.MQTTv311)
client.username_pw_set(username, password)

def on_connect(c, u, f, rc):
    print(f"connect_rc={rc}")
    c.subscribe(sub_topic, qos=0)

def on_message(c, u, msg):
    payload = msg.payload.decode(errors="replace")
    print(f"event topic={msg.topic} payload={payload}")
    received.append((msg.topic, payload))
    received_event.set()

client.on_connect = on_connect
client.on_message = on_message

client.connect(broker, port, 60)
client.loop_start()
time.sleep(1)

payload = json.dumps({"value": True, "time": 60})
result = client.publish(pub_topic, payload, qos=0)
print(f"publish_rc={result.rc} topic={pub_topic} payload={payload}")

received_event.wait(12)

client.loop_stop()
client.disconnect()
print(f"events_received={len(received)}")
