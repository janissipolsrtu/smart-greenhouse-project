#!/usr/bin/env python3
"""
Sensor Data Collection Service
Subscribes to MQTT sensor data from Raspberry Pi and stores in database
"""

import json
import logging
import time
import signal
import sys
from datetime import datetime
from typing import Dict, Any
import paho.mqtt.client as mqtt
import psycopg2
from psycopg2.extras import RealDictCursor
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
MQTT_BROKER = os.getenv('MQTT_BROKER', '192.168.8.151')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'zigbee2mqtt/+')  # Subscribe to all Zigbee2MQTT topics
MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', '60'))

# Database configuration
DB_HOST = os.getenv('POSTGRES_HOST', 'postgres')
DB_NAME = os.getenv('POSTGRES_DB', 'irrigation_db')
DB_USER = os.getenv('POSTGRES_USER', 'irrigation_user')
DB_PASS = os.getenv('POSTGRES_PASSWORD', 'irrigation_pass')
DB_PORT = int(os.getenv('POSTGRES_PORT', '5432'))

class SensorDataCollector:
    def __init__(self):
        self.mqtt_client = None
        self.db_connection = None
        self.running = True
        
    def setup_database(self):
        """Create sensor_data table if it doesn't exist"""
        try:
            self.db_connection = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                port=DB_PORT
            )
            
            cursor = self.db_connection.cursor()
            
            # Create sensor_data table
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS sensor_data (
                id SERIAL PRIMARY KEY,
                device_name VARCHAR(100) NOT NULL,
                temperature DECIMAL(5,2),
                humidity INTEGER,
                linkquality INTEGER,
                max_temperature DECIMAL(5,2),
                temperature_unit VARCHAR(20),
                raw_data JSONB,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_data(timestamp);
            CREATE INDEX IF NOT EXISTS idx_sensor_device ON sensor_data(device_name);
            """
            
            cursor.execute(create_table_sql)
            self.db_connection.commit()
            cursor.close()
            
            logger.info("✅ Database setup completed - sensor_data table ready")
            
        except Exception as e:
            logger.error(f"❌ Database setup failed: {e}")
            raise
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback for MQTT connection"""
        if rc == 0:
            logger.info("✅ Connected to MQTT broker successfully")
            # Subscribe to all Zigbee2MQTT device topics
            client.subscribe(MQTT_TOPIC)
            logger.info(f"📡 Subscribed to MQTT topic: {MQTT_TOPIC}")
        else:
            logger.error(f"❌ Failed to connect to MQTT broker, code: {rc}")
    
    def on_message(self, client, userdata, msg):
        """Process incoming MQTT messages with sensor data"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            # Skip non-JSON messages or system messages
            if '/bridge/' in topic or '/availability' in topic:
                return
                
            # Parse JSON data
            try:
                sensor_data = json.loads(payload)
            except json.JSONDecodeError:
                logger.debug(f"Non-JSON message on topic {topic}: {payload[:100]}")
                return
            
            # Check if message contains temperature data
            if isinstance(sensor_data, dict) and 'temperature' in sensor_data:
                device_name = topic.split('/')[-1]  # Extract device name from topic
                self.store_sensor_data(device_name, sensor_data)
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def store_sensor_data(self, device_name: str, data: Dict[Any, Any]):
        """Store sensor data in database"""
        try:
            cursor = self.db_connection.cursor()
            
            insert_sql = """
            INSERT INTO sensor_data (
                device_name, temperature, humidity, linkquality, 
                max_temperature, temperature_unit, raw_data, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # Extract sensor values
            temperature = data.get('temperature')
            humidity = data.get('humidity')
            linkquality = data.get('linkquality')
            max_temperature = data.get('max_temperature')
            temperature_unit = data.get('temperature_unit_convert', 'celsius')
            timestamp = datetime.utcnow()
            
            cursor.execute(insert_sql, (
                device_name,
                temperature,
                humidity, 
                linkquality,
                max_temperature,
                temperature_unit,
                json.dumps(data),  # Store raw JSON data
                timestamp
            ))
            
            self.db_connection.commit()
            cursor.close()
            
            logger.info(f"📊 Stored sensor data: {device_name} - {temperature}°C, {humidity}% humidity")
            
        except Exception as e:
            logger.error(f"❌ Failed to store sensor data: {e}")
            self.db_connection.rollback()
    
    def setup_mqtt(self):
        """Setup MQTT client and connections"""
        try:
            self.mqtt_client = mqtt.Client(
                client_id="sensor_data_collector", 
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
    
    def signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully"""
        logger.info("🛑 Shutdown signal received, stopping sensor data collector...")
        self.running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        if self.db_connection:
            self.db_connection.close()
            
        sys.exit(0)
    
    def run(self):
        """Main service loop"""
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("🚀 Starting Sensor Data Collection Service")
        
        # Wait for database to be ready
        max_retries = 30
        for attempt in range(max_retries):
            try:
                self.setup_database()
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Database connection attempt {attempt + 1}/{max_retries} failed, retrying in 5s...")
                    time.sleep(5)
                else:
                    logger.error("❌ Could not establish database connection, exiting")
                    return
        
        # Setup MQTT connection
        self.setup_mqtt()
        
        # Main service loop
        logger.info("📡 Sensor data collection service running...")
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    collector = SensorDataCollector()
    collector.run()