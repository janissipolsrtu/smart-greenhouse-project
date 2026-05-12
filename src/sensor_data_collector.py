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
MQTT_USERNAME = os.getenv('MQTT_USERNAME', 'mosquitto_api_user1')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD', 'mosquitto_password$')

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
        """Create sensor_measurements table if it doesn't exist"""
        try:
            self.db_connection = psycopg2.connect(
                host=DB_HOST,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASS,
                port=DB_PORT
            )
            
            cursor = self.db_connection.cursor()
            
            # Create sensor_measurements table aligned with time-series analytics use-cases.
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS sensor_measurements (
                id BIGSERIAL,
                device_name VARCHAR(100) NOT NULL,
                topic VARCHAR(255),
                temperature DOUBLE PRECISION,
                humidity DOUBLE PRECISION,
                linkquality INTEGER,
                battery INTEGER,
                max_temperature DOUBLE PRECISION,
                min_temperature DOUBLE PRECISION,
                temperature_sensitivity DOUBLE PRECISION,
                temperature_calibration DOUBLE PRECISION,
                temperature_sampling INTEGER,
                temperature_unit VARCHAR(20),
                humidity_calibration DOUBLE PRECISION,
                soil_moisture DOUBLE PRECISION,
                soil_calibration DOUBLE PRECISION,
                soil_sampling INTEGER,
                soil_warning INTEGER,
                dry BOOLEAN,
                raw_data JSONB,
                timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_sensor_measurements_ts ON sensor_measurements(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_sensor_measurements_device_ts ON sensor_measurements(device_name, timestamp DESC);
            """
            
            cursor.execute(create_table_sql)
            self.db_connection.commit()
            cursor.close()
            
            logger.info("Database setup completed - sensor_measurements table ready")
            
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
            rc_codes = {
                1: "incorrect protocol version",
                2: "invalid client identifier",
                3: "server unavailable",
                4: "bad username or password",
                5: "not authorised"
            }
            reason = rc_codes.get(rc, f"unknown code {rc}")
            logger.error(f"❌ Failed to connect to MQTT broker: {reason} (rc={rc})")
    
    def on_disconnect(self, client, userdata, rc):
        """Callback for MQTT disconnection"""
        if rc == 0:
            logger.info("🔌 Disconnected from MQTT broker cleanly")
        else:
            logger.warning(f"⚠️ Unexpected disconnect from MQTT broker (rc={rc}), will auto-reconnect...")
    
    def on_message(self, client, userdata, msg):
        """Process incoming MQTT messages with sensor data"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logger.info(f"📨 MQTT message received | topic={topic} | payload={payload[:500]}")
            
            # Skip non-JSON messages or system messages
            if '/bridge/' in topic or '/availability' in topic:
                logger.debug(f"⏭ Skipping system topic: {topic}")
                return
                
            # Parse JSON data
            try:
                sensor_data = json.loads(payload)
            except json.JSONDecodeError:
                logger.warning(f"⚠️ Non-JSON message on topic {topic}: {payload[:200]}")
                return
            
            logger.info(f"📊 Parsed JSON from {topic}: keys={list(sensor_data.keys()) if isinstance(sensor_data, dict) else type(sensor_data).__name__}")
            
            # Check if message contains temperature data
            if isinstance(sensor_data, dict) and 'temperature' in sensor_data:
                device_name = topic.split('/')[-1]  # Extract device name from topic
                self.store_sensor_data(topic, device_name, sensor_data)
            else:
                logger.info(f"ℹ️ Message on {topic} has no 'temperature' field - skipping storage")
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    def store_sensor_data(self, topic: str, device_name: str, data: Dict[Any, Any]):
        """Store sensor data in database"""
        try:
            cursor = self.db_connection.cursor()
            
            insert_sql = """
            INSERT INTO sensor_measurements (
                device_name, topic, temperature, humidity, linkquality,
                battery, max_temperature, min_temperature, temperature_sensitivity,
                temperature_calibration, temperature_sampling, temperature_unit,
                humidity_calibration, soil_moisture, soil_calibration, soil_sampling,
                soil_warning, dry, raw_data, timestamp
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # Missing keys intentionally map to None so DB reflects real payload shape.
            temperature = data.get('temperature', None)
            humidity = data.get('humidity', None)
            linkquality = data.get('linkquality', None)
            battery = data.get('battery', None)
            max_temperature = data.get('max_temperature', None)
            min_temperature = data.get('min_temperature', None)
            temperature_sensitivity = data.get('temperature_sensitivity', None)
            temperature_calibration = data.get('temperature_calibration', None)
            temperature_sampling = data.get('temperature_sampling', None)
            temperature_unit = data.get('temperature_unit_convert', data.get('temperature_unit', None))
            humidity_calibration = data.get('humidity_calibration', None)
            soil_moisture = data.get('soil_moisture', None)
            soil_calibration = data.get('soil_calibration', None)
            soil_sampling = data.get('soil_sampling', None)
            soil_warning = data.get('soil_warning', None)
            dry = data.get('dry', None)
            timestamp = datetime.utcnow()

            expected_payload_keys = [
                'temperature', 'humidity', 'linkquality', 'battery',
                'max_temperature', 'min_temperature', 'temperature_sensitivity',
                'temperature_calibration', 'temperature_sampling',
                'temperature_unit', 'temperature_unit_convert',
                'humidity_calibration', 'soil_moisture', 'soil_calibration',
                'soil_sampling', 'soil_warning', 'dry'
            ]
            missing_keys = [key for key in expected_payload_keys if key not in data]
            if missing_keys:
                logger.info(
                    f"🧩 Payload key audit: device={device_name} missing_keys={missing_keys}"
                )
            
            cursor.execute(insert_sql, (
                device_name,
                topic,
                temperature,
                humidity, 
                linkquality,
                battery,
                max_temperature,
                min_temperature,
                temperature_sensitivity,
                temperature_calibration,
                temperature_sampling,
                temperature_unit,
                humidity_calibration,
                soil_moisture,
                soil_calibration,
                soil_sampling,
                soil_warning,
                dry,
                json.dumps(data),  # Store raw JSON data
                timestamp
            ))
            
            self.db_connection.commit()
            cursor.close()
            
            logger.info(
                f"Stored sensor data: device={device_name} temp={temperature} humidity={humidity} soil={soil_moisture} battery={battery}"
            )
            
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
            self.mqtt_client.on_disconnect = self.on_disconnect
            
            # Set username and password for MQTT broker authentication
            self.mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            
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