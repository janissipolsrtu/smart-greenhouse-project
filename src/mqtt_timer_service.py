#!/usr/bin/env python3
"""
MQTT Timer Service for Irrigation Control
Runs on Raspberry Pi (192.168.8.151) to provide server-side timing
"""

import paho.mqtt.client as mqtt
import json
import threading
import time
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MQTTTimerService:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.active_timers = {}  # Track running timers
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Timer Service connected to MQTT broker")
            # Subscribe to schedule requests from API
            client.subscribe("irrigation/schedule/+")
            client.subscribe("irrigation/control/+")
        else:
            logger.error(f"Failed to connect. Return code: {rc}")
            
    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if "schedule" in topic:
                self.handle_schedule_request(payload)
            elif "control" in topic:
                self.handle_control_request(payload)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def handle_schedule_request(self, payload):
        """Handle irrigation scheduling requests"""
        try:
            device_id = payload.get("device", "0x540f57fffe890af8")
            duration = payload.get("duration", 0)
            
            if duration <= 0 or duration > 3600:
                logger.error(f"Invalid duration: {duration}")
                return
                
            # Cancel any existing timer for this device
            self.cancel_timer(device_id)
            
            logger.info(f"Starting irrigation schedule: {duration}s for {device_id}")
            
            # Turn ON immediately
            self.send_device_command(device_id, "ON")
            
            # Publish schedule status
            self.publish_schedule_status(device_id, "started", duration)
            
            # Schedule automatic OFF
            timer = threading.Timer(duration, self.auto_turnoff, [device_id, duration])
            timer.daemon = True
            timer.start()
            
            # Track the timer
            self.active_timers[device_id] = {
                "timer": timer,
                "started_at": datetime.now().isoformat(),
                "duration": duration,
                "auto_off_at": datetime.now().timestamp() + duration
            }
            
        except Exception as e:
            logger.error(f"Error in schedule handling: {e}")
    
    def handle_control_request(self, payload):
        """Handle direct control requests"""
        try:
            device_id = payload.get("device", "0x540f57fffe890af8")
            action = payload.get("action", "").upper()
            
            if action in ["ON", "OFF"]:
                # Cancel any running timer if turning OFF manually
                if action == "OFF":
                    self.cancel_timer(device_id)
                    
                self.send_device_command(device_id, action)
                logger.info(f"Manual control: {device_id} -> {action}")
                
        except Exception as e:
            logger.error(f"Error in control handling: {e}")
    
    def auto_turnoff(self, device_id, duration):
        """Automatically turn off device after duration"""
        try:
            self.send_device_command(device_id, "OFF")
            logger.info(f"Auto-turned OFF {device_id} after {duration}s")
            
            # Clean up timer tracking
            if device_id in self.active_timers:
                del self.active_timers[device_id]
                
            # Publish completion status
            self.publish_schedule_status(device_id, "completed", duration)
            
        except Exception as e:
            logger.error(f"Error in auto turnoff: {e}")
    
    def cancel_timer(self, device_id):
        """Cancel active timer for device"""
        if device_id in self.active_timers:
            timer_info = self.active_timers[device_id]
            timer_info["timer"].cancel()
            del self.active_timers[device_id]
            logger.info(f"Cancelled active timer for {device_id}")
    
    def send_device_command(self, device_id, action):
        """Send ON/OFF command to Zigbee device"""
        topic = f"zigbee2mqtt/{device_id}/set"
        message = {"state": action}
        
        result = self.client.publish(topic, json.dumps(message))
        if result.rc == 0:
            logger.info(f"Sent {action} command to {device_id}")
        else:
            logger.error(f"Failed to send command to {device_id}")
    
    def publish_schedule_status(self, device_id, status, duration):
        """Publish schedule status updates"""
        status_data = {
            "device": device_id,
            "status": status,
            "duration": duration,
            "timestamp": datetime.now().isoformat()
        }
        
        if device_id in self.active_timers:
            status_data.update(self.active_timers[device_id])
            # Remove the timer object for JSON serialization
            if "timer" in status_data:
                del status_data["timer"]
        
        self.client.publish("irrigation/status/schedule", json.dumps(status_data))
    
    def start(self):
        """Start the timer service"""
        try:
            logger.info("Starting MQTT Timer Service...")
            self.client.connect("localhost", 1883, 60)
            self.client.loop_forever()
        except Exception as e:
            logger.error(f"Error starting service: {e}")

if __name__ == "__main__":
    service = MQTTTimerService()
    service.start()