#!/usr/bin/env python3
"""
Local Sensor Data Collector (Container Version)
Connects to containerized MQTT broker and sends data to local backend
"""

import json
import logging
import time
import signal
import sys
import os
import requests
from datetime import datetime, timezone
from typing import Dict, Any, List
import paho.mqtt.client as mqtt
from collections import defaultdict
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
MQTT_BROKER = os.getenv('MQTT_BROKER', 'mosquitto')  # Container name
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'sensor/+')  # Sensor data topics
MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', '60'))

# Backend server configuration (internal container network)
BACKEND_SERVER = os.getenv('BACKEND_SERVER', 'http://django-webapp:8080')
API_ENDPOINT = f"{BACKEND_SERVER}/api/sensor-data/bulk/"
API_TOKEN = os.getenv('API_TOKEN', '')

# Data batching configuration
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '25'))
BATCH_INTERVAL = int(os.getenv('BATCH_INTERVAL', '180'))  # 3 minutes
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '30'))

class LocalSensorCollector:
    def __init__(self):
        self.mqtt_client = None
        self.running = True
        self.sensor_buffer = defaultdict(list)
        self.buffer_lock = threading.Lock()
        self.last_send_time = datetime.utcnow()
        
    def on_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection"""
        if rc == 0:
            logger.info("✅ Connected to MQTT broker successfully")
            client.subscribe(MQTT_TOPIC)
            logger.info(f"📡 Subscribed to MQTT topic: {MQTT_TOPIC}")
        else:
            logger.error(f"❌ Failed to connect to MQTT broker, code: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Process incoming MQTT messages with sensor data"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Parse JSON data
            try:
                sensor_data = json.loads(payload)
            except json.JSONDecodeError:
                logger.debug(f"Non-JSON message on topic {topic}: {payload[:100]}")
                return
            
            # Process sensor data based on topic structure
            self.process_sensor_message(topic, sensor_data)
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def process_sensor_message(self, topic: str, data: Dict[Any, Any]):
        """Process different types of sensor messages"""
        if not isinstance(data, dict):
            return
            
        # Extract device name from topic (last part)
        device_name = topic.split('/')[-1]
        
        # Check for temperature/humidity data
        has_sensor_data = any(key in data for key in ['temperature', 'humidity', 'pressure'])
        
        if has_sensor_data:
            self.buffer_sensor_data(device_name, data)
    
    def buffer_sensor_data(self, device_name: str, data: Dict[Any, Any]):
        """Buffer sensor data for batch sending"""
        try:
            with self.buffer_lock:
                # Create sensor reading record
                reading = {
                    'device_name': device_name,
                    'temperature': data.get('temperature'),
                    'humidity': data.get('humidity'),
                    'pressure': data.get('pressure'),
                    'linkquality': data.get('linkquality'),
                    'max_temperature': data.get('max_temperature'),
                    'temperature_unit': data.get('temperature_unit_convert', data.get('temperature_unit', 'celsius')),
                    'raw_data': data,
                    'timestamp': datetime.utcnow().isoformat() + 'Z'
                }
                
                self.sensor_buffer[device_name].append(reading)
                
                total_readings = sum(len(readings) for readings in self.sensor_buffer.values())
                logger.info(f"📊 Buffered reading from {device_name}: " +
                          f"T={data.get('temperature', '?')}°C, " +
                          f"H={data.get('humidity', '?')}% " +
                          f"(Buffer: {total_readings})")
                
                # Check if we should send data
                self.check_send_conditions()
                
        except Exception as e:
            logger.error(f"❌ Failed to buffer sensor data: {e}")
    
    def check_send_conditions(self):
        """Check if we should send buffered data to backend"""
        total_readings = sum(len(readings) for readings in self.sensor_buffer.values())
        time_since_last_send = (datetime.utcnow() - self.last_send_time).total_seconds()
        
        should_send = (
            total_readings >= BATCH_SIZE or 
            time_since_last_send >= BATCH_INTERVAL
        )
        
        if should_send and total_readings > 0:
            threading.Thread(target=self.send_buffered_data, daemon=True).start()
    
    def send_buffered_data(self):
        """Send buffered sensor data to backend server"""
        try:
            with self.buffer_lock:
                if not any(self.sensor_buffer.values()):
                    return
                
                # Collect all readings
                all_readings = []
                for device_readings in self.sensor_buffer.values():
                    all_readings.extend(device_readings)
                
                # Clear buffer
                buffer_copy = dict(self.sensor_buffer)
                self.sensor_buffer.clear()
                self.last_send_time = datetime.utcnow()
            
            if not all_readings:
                return
            
            # Prepare API request
            headers = {'Content-Type': 'application/json'}
            if API_TOKEN:
                headers['Authorization'] = f'Bearer {API_TOKEN}'
            
            payload = {
                'readings': all_readings,
                'source': 'local_sensor_collector',
                'collected_at': datetime.utcnow().isoformat() + 'Z'
            }
            
            # Send to backend with retries
            for attempt in range(MAX_RETRIES):
                try:
                    logger.info(f"📤 Sending {len(all_readings)} readings to backend (attempt {attempt + 1})")
                    
                    response = requests.post(
                        API_ENDPOINT,
                        json=payload,
                        headers=headers,
                        timeout=30
                    )
                    
                    if response.status_code in [200, 201]:
                        logger.info(f"✅ Successfully sent {len(all_readings)} readings to backend")
                        return
                    else:
                        logger.warning(f"⚠️ Backend returned status {response.status_code}: {response.text}")
                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"⚠️ Failed to send data (attempt {attempt + 1}): {e}")
                
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
            
            # If all retries failed, put data back in buffer
            logger.error(f"❌ Failed to send data after {MAX_RETRIES} attempts")
            with self.buffer_lock:
                for device_name, readings in buffer_copy.items():
                    self.sensor_buffer[device_name].extend(readings)
                    
        except Exception as e:
            logger.error(f"❌ Error sending buffered data: {e}")
    
    def setup_mqtt(self):
        """Setup MQTT client and connections"""
        try:
            self.mqtt_client = mqtt.Client(
                client_id="local_sensor_collector", 
                protocol=mqtt.MQTTv311
            )
            
            # Set callbacks
            self.mqtt_client.on_connect = self.on_connect
            self.mqtt_client.on_message = self.on_message
            
            # Connect to MQTT broker
            logger.info(f"🔌 Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            
            # Start network loop
            self.mqtt_client.loop_start()
            
        except Exception as e:
            logger.error(f"❌ MQTT setup failed: {e}")
            raise
    
    def periodic_sender(self):
        """Periodic sender thread"""
        while self.running:
            try:
                time.sleep(BATCH_INTERVAL)
                with self.buffer_lock:
                    total_readings = sum(len(readings) for readings in self.sensor_buffer.values())
                    
                if total_readings > 0:
                    logger.info(f"⏰ Periodic send triggered with {total_readings} buffered readings")
                    threading.Thread(target=self.send_buffered_data, daemon=True).start()
                    
            except Exception as e:
                logger.error(f"Error in periodic sender: {e}")
    
    def signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully"""
        logger.info("🛑 Shutdown signal received")
        self.running = False
        
        # Send any remaining data
        with self.buffer_lock:
            total_readings = sum(len(readings) for readings in self.sensor_buffer.values())
            if total_readings > 0:
                logger.info(f"📤 Sending {total_readings} final buffered readings")
                self.send_buffered_data()
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        sys.exit(0)
    
    def test_backend_connection(self):
        """Test connection to backend server"""
        try:
            health_url = f"{BACKEND_SERVER}/api/health/"
            response = requests.get(health_url, timeout=10)
            if response.status_code == 200:
                logger.info(f"✅ Backend server connection successful")
                return True
            else:
                logger.warning(f"⚠️ Backend server returned status {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ Cannot reach backend server: {e}")
            return False
    
    def run(self):
        """Main service loop"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("🚀 Starting Local Sensor Data Collector")
        logger.info(f"   MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        logger.info(f"   Backend Server: {BACKEND_SERVER}")
        logger.info(f"   Topic Pattern: {MQTT_TOPIC}")
        logger.info(f"   Batch Settings: {BATCH_SIZE} readings / {BATCH_INTERVAL}s")
        
        # Test backend
        self.test_backend_connection()
        
        # Setup MQTT
        self.setup_mqtt()
        
        # Start periodic sender
        sender_thread = threading.Thread(target=self.periodic_sender, daemon=True)
        sender_thread.start()
        
        logger.info("📡 Local sensor collector running...")
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    collector = LocalSensorCollector()
    collector.run()