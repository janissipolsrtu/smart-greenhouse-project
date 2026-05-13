#!/usr/bin/env python3
"""
Automated Irrigation System API
Controls Zigbee devices via MQTT for smart irrigation management
Built with FastAPI for high performance and automatic documentation
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import paho.mqtt.client as mqtt
import json
import threading
import time
import os
import asyncio
from datetime import datetime, timedelta, date
import logging
import uvicorn
from typing import Optional, Dict, Any, List
import uuid
from enum import Enum

# Database imports
from database import init_database, test_database_connection
from smart_greenhouse_db_service import WateringCycleService, WateringPlanService
from plant_db_service import PlantService
from greenhouse_db_service import GreenhouseService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for request/response
class WateringCommand(BaseModel):
    action: str  # "ON" or "OFF"

class WateringSchedule(BaseModel):
    duration: int  # Duration in seconds

class WateringCycle(BaseModel):
    id: str = None
    scheduled_time: datetime
    duration: int  # Duration in seconds
    description: Optional[str] = None
    device: str = "0x540f57fffe890af8"  # Correct Zigbee device ID
    created_at: datetime = datetime.utcnow()
    updated_at: Optional[datetime] = None
    status: str = "pending"  # pending, executing, completed, failed, cancelled
    executed_at: Optional[datetime] = None
    result: Optional[str] = None
    plan_id: Optional[str] = None
    
    def __init__(self, **data):
        if 'id' not in data or data['id'] is None:
            data['id'] = str(uuid.uuid4())
        super().__init__(**data)

class WateringCycleRequest(BaseModel):
    scheduled_time: str  # ISO format datetime string
    duration: int  # Duration in seconds
    description: Optional[str] = None
    timezone: Optional[str] = "UTC"  # Default to UTC, can be "EEST", "UTC+3", etc.
    plan_id: Optional[str] = None


class WateringPlanRequest(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    active: bool = True


class WateringPlanUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    active: Optional[bool] = None

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[Any, Any]] = None
    timestamp: str = datetime.utcnow().isoformat()


class GreenhouseBase(BaseModel):
    name: str
    mqtt_username: str
    mqtt_password: str
    mqtt_broker: str = "192.168.8.151"
    mqtt_port: int = 1883
    description: Optional[str] = None
    location: Optional[str] = None
    active: bool = True


class GreenhouseCreate(GreenhouseBase):
    pass


class GreenhouseUpdate(BaseModel):
    name: Optional[str] = None
    mqtt_username: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_broker: Optional[str] = None
    mqtt_port: Optional[int] = None
    description: Optional[str] = None
    location: Optional[str] = None
    active: Optional[bool] = None


class DevicePairingRequest(BaseModel):
    broker_ip: str
    port: int = 1883
    mqtt_username: str
    mqtt_password: str
    duration: int = 60


class DevicePairingStatusRequest(BaseModel):
    broker_ip: str
    port: int = 1883
    mqtt_username: str
    mqtt_password: str
    listen_seconds: int = 8

# Plant Management Pydantic Models
class PlantBase(BaseModel):
    name: str  # Plant name or variety (FR-11)
    variety: Optional[str] = None  # Specific variety if different from name
    planting_date: date  # Planting date (FR-12)
    watering_frequency: int = 1  # Times per day (FR-13)
    watering_duration: int = 300  # Seconds per watering (FR-13)
    water_amount_ml: Optional[int] = None  # Milliliters per watering (FR-13)
    harvest_date_estimate: Optional[date] = None  # Expected harvest date (FR-14)
    harvest_quantity_estimate: Optional[float] = None  # Expected quantity in kg (FR-14)
    location_row: int  # Greenhouse row number (FR-15)
    location_column: int  # Greenhouse column number (FR-15)
    location_description: Optional[str] = None  # Additional location info (FR-15)
    notes: Optional[str] = None  # General notes about the plant
    active: bool = True  # Whether plant is still active

class PlantCreate(PlantBase):
    pass

class PlantUpdate(BaseModel):
    name: Optional[str] = None
    variety: Optional[str] = None
    planting_date: Optional[date] = None
    watering_frequency: Optional[int] = None
    watering_duration: Optional[int] = None
    water_amount_ml: Optional[int] = None
    harvest_date_estimate: Optional[date] = None
    harvest_quantity_estimate: Optional[float] = None
    location_row: Optional[int] = None
    location_column: Optional[int] = None
    location_description: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None

class PlantResponse(PlantBase):
    id: str
    created_at: datetime
    updated_at: datetime
    location_coordinate: str  # Computed property like "R1C3"
    days_since_planting: int  # Computed property
    days_to_harvest: Optional[int] = None  # Computed property

    class Config:
        from_attributes = True

# Initialize FastAPI app
app = FastAPI(
    title="Automated Irrigation System API",
    description="Controls Zigbee devices via MQTT for smart irrigation management",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MQTT Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")  # Use Docker service name, fallback to mosquitto
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# Device configuration
DEVICES = {
    "temperature_sensor": {
        "name": "0xa4c138391b14a3d1",
        "topic": "zigbee2mqtt/0xa4c138391b14a3d1",
        "type": "sensor"
    },
    "irrigation_controller": {
        "name": "0x540f57fffe890af8", 
        "topic": "zigbee2mqtt/0x540f57fffe890af8",
        "type": "actuator"
    }
}

# Store latest sensor data
sensor_data = {}
device_status = {}
timer_service_status = {}  # Store timer service status

# Database configuration
DB_URL = os.getenv("DATABASE_URL", "postgresql://irrigation_user:irrigation_pass@postgres:5432/irrigation_db")

# Watering cycles storage (kept for compatibility)
watering_cycles: List[WateringCycle] = []
watering_cycle = []  # Store scheduled waterings
cycle_execution_lock = threading.Lock()

class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.connected = False
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker successfully")
            # Subscribe to all zigbee2mqtt topics
            client.subscribe("zigbee2mqtt/+")
            client.subscribe("zigbee2mqtt/+/+")
            # Subscribe to timer service status updates
            client.subscribe("smart_greenhouse/status/+")
        else:
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            
    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            # Store sensor data
            if "0xa4c138391b14a3d1" in topic:
                sensor_data['temperature'] = payload
                sensor_data['last_updated'] = datetime.now().isoformat()
                logger.info(f"Temperature sensor data: {payload}")
                
            elif "0x540f57fffe890af8" in topic:
                device_status['irrigation_controller'] = payload
                device_status['last_updated'] = datetime.now().isoformat()
                logger.info(f"Irrigation controller status: {payload}")
                
            elif "smart_greenhouse/status/" in topic:
                # Handle timer service status updates
                status_type = topic.split("/")[-1]  # e.g., "schedule"
                timer_service_status[status_type] = payload
                timer_service_status['last_updated'] = datetime.now().isoformat()
                logger.info(f"Timer service {status_type} status: {payload}")
                
                # Check if this is a completion status for a planned irrigation
                if (status_type == "schedule" and 
                    "cycle_entry_id" in payload and 
                    "status" in payload):
                    
                    cycle_entry_id = payload["cycle_entry_id"]
                    watering_status = payload["status"]  # e.g., "completed", "failed"
                    
                    # Update the watering cycle entry status
                    with cycle_execution_lock:
                        for entry in watering_cycle:
                            if entry.id == cycle_entry_id:
                                entry.status = watering_status
                                logger.info(f"Updated watering cycle entry {cycle_entry_id} status to: {watering_status}")
                                break
                
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
            
    def on_disconnect(self, client, userdata, rc):
        self.connected = False
        logger.warning("Disconnected from MQTT broker")
        
    def connect(self):
        try:
            logger.info(f"Attempting to connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            
            # Set authentication if provided (none for simple setup)
            # if MQTT_USERNAME and MQTT_PASSWORD:
            #     self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
                
            # Configure connection timeouts for better WSL networking
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            self.client.loop_start()
            
            # Wait longer for connection and verify
            import time
            for i in range(10):  # Wait up to 5 seconds
                time.sleep(0.5)
                if self.connected:
                    logger.info("MQTT connection verified")
                    return True
                    
            logger.warning("MQTT connection timeout - may still be connecting")
            return self.connected
            
        except Exception as e:
            logger.error(f"Error connecting to MQTT: {e}")
            return False
            
    def publish(self, topic, message):
        # Try to reconnect if not connected
        if not self.connected:
            logger.info("MQTT not connected, attempting reconnection...")
            if not self.connect():
                logger.error("Failed to reconnect to MQTT broker")
                return False
                
        if self.connected:
            result = self.client.publish(topic, json.dumps(message))
            if result.rc == 0:
                logger.info(f"Published to {topic}: {message}")
                return True
            else:
                logger.error(f"Failed to publish to {topic}")
                return False
        else:
            logger.error("MQTT client not connected")
            return False

# Initialize MQTT client
mqtt_client = MQTTClient()

# Database operations for irrigation plans
def load_watering_cycles():
    """Load watering cycles from PostgreSQL database"""
    global watering_cycles
    try:
        # Get cycles from database using the service
        db_cycles = WateringCycleService.get_all_cycles()
        watering_cycles = []
        
        for db_cycle in db_cycles:
            # Convert database model to WateringCycle for compatibility
            cycle_entry = WateringCycle(
                id=db_cycle.id,
                scheduled_time=db_cycle.scheduled_time,
                duration=db_cycle.duration,
                description=db_cycle.description,
                created_at=db_cycle.created_at,
                status=db_cycle.status,
                plan_id=db_cycle.plan_id,
            )
            watering_cycles.append(cycle_entry)
            
        logger.info(f"Successfully loaded {len(watering_cycles)} watering cycles from database")
        
    except Exception as e:
        logger.error(f"Error loading watering cycles from database: {e}")
        watering_cycles = []

def save_watering_cycles():
    """Save operation not needed - using database directly"""
    # This function is kept for compatibility but doesn't do anything
    # since we now save directly to database in the API endpoints
    pass

def cleanup_old_cycles():
    """Remove completed cycles older than 24 hours"""
    global watering_cycles
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    initial_count = len(watering_cycles)
    
    watering_cycles = [
        cycle for cycle in watering_cycles 
        if not (cycle.status in ["completed", "failed"] and cycle.executed_at and cycle.executed_at < cutoff_time)
    ]
    
    removed_count = initial_count - len(watering_cycles)
    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old watering cycle entries")
        save_watering_cycles()

async def execute_scheduled_watering(cycle: WateringCycle):
    """Execute a scheduled watering cycle"""
    try:
        cycle.status = "executing"
        cycle.executed_at = datetime.utcnow()
        save_watering_cycles()
        
        logger.info(f"Executing scheduled watering cycle {cycle.id}: {cycle.duration}s")
        
        # Send schedule request to MQTT timer service
        schedule_request = {
            "device": DEVICES['irrigation_controller']['name'],
            "duration": cycle.duration,
            "action": "schedule",
            "requested_by": "scheduler",
            "cycle_id": cycle.id,
            "timestamp": datetime.now().isoformat()
        }
        
        success = mqtt_client.publish("smart_greenhouse/schedule/request", schedule_request)
        
        if success:
            cycle.status = "completed"
            cycle.result = f"Successfully scheduled {cycle.duration}s watering"
            logger.info(f"Scheduled watering cycle {cycle.id} executed successfully")
        else:
            cycle.status = "failed"
            cycle.result = "Failed to send command to MQTT timer service"
            logger.error(f"Failed to execute watering cycle {cycle.id}")
            
    except Exception as e:
        cycle.status = "failed"
        cycle.result = f"Execution error: {str(e)}"
        logger.error(f"Error executing watering cycle {cycle.id}: {e}")
    
    save_watering_cycles()

async def watering_scheduler():
    """Background task to check and execute scheduled waterings"""
    logger.info("Watering scheduler started")
    
    while True:
        try:
            current_time = datetime.utcnow()
            
            # Find pending cycles that should be executed
            for cycle in watering_cycles:
                if (cycle.status == "pending" and 
                    cycle.scheduled_time <= current_time):
                    
                    await execute_scheduled_watering(cycle)
            
            # Cleanup old cycles every hour
            if current_time.minute == 0 and current_time.second < 30:
                cleanup_old_cycles()
                
        except Exception as e:
            logger.error(f"Error in watering scheduler: {e}")
        
        # Check every 30 seconds
        await asyncio.sleep(30)

@app.get("/", response_model=ApiResponse, tags=["System"])
async def root():
    """API Home - returns system status"""
    return ApiResponse(
        success=True,
        message="Automated Irrigation System API is running",
        data={
            "system": "Automated Irrigation System API",
            "mqtt_connected": mqtt_client.connected,
            "devices": list(DEVICES.keys()),
            "docs_url": "/docs",
            "api_version": "2.0.0"
        }
    )

@app.get("/api/devices", tags=["Devices"])
async def get_devices():
    """Get all configured devices and their current status"""
    return {
        "success": True,
        "data": {
            "devices": DEVICES,
            "sensor_data": sensor_data,
            "device_status": device_status
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/sensor/temperature", tags=["Sensors"])
async def get_temperature():
    """Get latest temperature and humidity data from 0xa4c138391b14a3d1 sensor"""
    if sensor_data:
        return ApiResponse(
            success=True,
            message="Temperature data retrieved successfully",
            data=sensor_data
        )
    else:
        raise HTTPException(
            status_code=404,
            detail="No temperature data available"
        )

@app.post("/api/watering/control", response_model=ApiResponse, tags=["Watering"])
async def control_watering(command: WateringCommand):
    """Control irrigation system via MQTT timer service for consistent behavior"""
    try:
        action = command.action.upper()
        
        if action not in ['ON', 'OFF']:
            raise HTTPException(
                status_code=400,
                detail="Invalid action. Use 'ON' or 'OFF'"
            )
        
        # Send control request to MQTT timer service
        control_request = {
            "device": DEVICES['irrigation_controller']['name'],
            "action": action,
            "requested_by": "fastapi",
            "timestamp": datetime.now().isoformat()
        }
        
        success = mqtt_client.publish("smart_greenhouse/control/request", control_request)
        
        if success:
            return ApiResponse(
                success=True,
                message=f"Irrigation control request sent: {action}",
                data={
                    "action": action,
                    "device": DEVICES['irrigation_controller']['name'],
                    "control_mode": "server_side",
                    "note": "Command processed by Pi timer service"
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send control request to timer service"
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in irrigation control: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/api/watering/status", tags=["Watering"])
async def get_watering_status():
    """Get current watering controller (0x540f57fffe890af8) status"""
    if 'irrigation_controller' in device_status:
        return ApiResponse(
            success=True,
            message="Irrigation status retrieved successfully",
            data=device_status['irrigation_controller']
        )
    else:
        raise HTTPException(
            status_code=404,
            detail="No irrigation status available"
        )

@app.post("/api/watering/schedule", response_model=ApiResponse, tags=["Watering"])
async def schedule_watering(schedule: WateringSchedule):
    """
    Schedule irrigation with MQTT server-side timing (no network latency issues)
    Timing is handled by the timer service running on the Raspberry Pi
    
    Note: The R7060 irrigation controller does NOT support Zigbee on_time parameter
    (tested with {"state": "ON", "on_time": 10} - device ignores the timer).
    Therefore, we use MQTT timer service for scheduling functionality.
    """
    try:
        duration = schedule.duration
        
        if duration <= 0 or duration > 3600:  # Max 1 hour
            raise HTTPException(
                status_code=400,
                detail="Duration must be between 1 and 3600 seconds"
            )
        
        # Send schedule request to MQTT timer service (on Pi)
        schedule_request = {
            "device": DEVICES['irrigation_controller']['name'],
            "duration": duration,
            "action": "schedule",
            "requested_by": "fastapi",
            "timestamp": datetime.now().isoformat()
        }
        
        success = mqtt_client.publish("smart_greenhouse/schedule/request", schedule_request)
        
        if success:
            return ApiResponse(
                success=True,
                message=f"Irrigation schedule request sent ({duration}s)",
                data={
                    "duration": duration,
                    "timing_mode": "server_side",
                    "device": DEVICES['irrigation_controller']['name'],
                    "note": "Timer runs on Raspberry Pi for precise control",
                    "expected_off_time": datetime.now().timestamp() + duration
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send schedule request to timer service"
            )
            
    except Exception as e:
        logger.error(f"Error in irrigation scheduling: {e}")
        raise HTTPException(status_code=500, detail=f"Scheduling error: {str(e)}")

@app.get("/api/watering/schedule/status", tags=["Watering"])
async def get_schedule_status():
    """Get current irrigation schedule status from timer service"""
    if timer_service_status:
        return ApiResponse(
            success=True,
            message="Timer service status retrieved successfully",
            data=timer_service_status
        )
    else:
        raise HTTPException(
            status_code=404,
            detail="No timer service status available"
        )

@app.get("/api/system/status", tags=["System"])
async def system_status():
    """Get comprehensive system status and health information"""
    return {
        "success": True,
        "data": {
            "system": {
                "status": "operational",
                "mqtt_connected": mqtt_client.connected,
                "mqtt_broker": MQTT_BROKER,
                "api_version": "2.0.0",
                "uptime": datetime.now().isoformat(),
                "timing_mode": "server_side"
            },
            "sensors": sensor_data,
            "devices": device_status,
            "timer_service": timer_service_status,
            "configuration": {
                "devices_count": len(DEVICES),
                "mqtt_port": MQTT_PORT
            }
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/health", tags=["System"])
async def health_check():
    """Simple health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "mqtt_connected": mqtt_client.connected
    }


@app.post("/api/device/pairing", response_model=ApiResponse, tags=["Devices"])
async def api_device_pairing(request: DevicePairingRequest):
    """Start Zigbee2MQTT pairing by publishing permit_join with supplied MQTT credentials."""
    try:
        if request.duration < 10 or request.duration > 254:
            raise HTTPException(status_code=400, detail="duration must be between 10 and 254 seconds")

        client = mqtt.Client(protocol=mqtt.MQTTv311)
        client.username_pw_set(request.mqtt_username, request.mqtt_password)
        client.connect(request.broker_ip, request.port, 60)
        client.loop_start()

        payload = {
            "time": request.duration,
        }
        result = client.publish("zigbee2mqtt/bridge/request/permit_join", json.dumps(payload), qos=0)

        # Give network loop a short window to flush publish.
        time.sleep(0.5)
        client.loop_stop()
        client.disconnect()

        if result.rc != 0:
            raise HTTPException(status_code=500, detail=f"Failed to publish permit_join, rc={result.rc}")

        return ApiResponse(
            success=True,
            message=f"Pairing enabled for {request.duration} seconds",
            data={
                "broker": request.broker_ip,
                "port": request.port,
                "request_topic": "zigbee2mqtt/bridge/request/permit_join",
                "request_payload": payload,
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting device pairing: {e}")
        raise HTTPException(status_code=500, detail=f"Pairing error: {str(e)}")


@app.post("/api/device/pairing-status", response_model=ApiResponse, tags=["Devices"])
async def api_device_pairing_status(request: DevicePairingStatusRequest):
    """Listen briefly on Zigbee2MQTT bridge topics and report whether pairing events were detected."""
    try:
        listen_seconds = max(1, min(request.listen_seconds, 30))
        topic = "zigbee2mqtt/bridge/event"

        events = []
        paired_detected = False
        connect_event = threading.Event()

        client = mqtt.Client(protocol=mqtt.MQTTv311)
        client.username_pw_set(request.mqtt_username, request.mqtt_password)

        def on_connect(c, userdata, flags, rc):
            if rc == 0:
                c.subscribe(topic, qos=0)
                connect_event.set()

        def on_message(c, userdata, msg):
            nonlocal paired_detected
            raw_payload = msg.payload.decode(errors="replace")
            parsed_payload = raw_payload
            event_type = None

            try:
                payload_obj = json.loads(raw_payload)
                parsed_payload = payload_obj
                if isinstance(payload_obj, dict):
                    event_type = str(payload_obj.get("type") or "").lower()
            except json.JSONDecodeError:
                pass

            if event_type == "device_joined":
                paired_detected = True

            events.append({
                "topic": msg.topic,
                "event_type": event_type,
                "payload": parsed_payload,
            })

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(request.broker_ip, request.port, 60)
        client.loop_start()

        if not connect_event.wait(timeout=5):
            client.loop_stop()
            client.disconnect()
            raise HTTPException(status_code=500, detail="Failed to connect/subscribe to broker")

        time.sleep(listen_seconds)
        client.loop_stop()
        client.disconnect()

        return ApiResponse(
            success=True,
            message="Pairing status check completed",
            data={
                "broker": request.broker_ip,
                "port": request.port,
                "topic": topic,
                "listen_seconds": listen_seconds,
                "paired_detected": paired_detected,
                "events_count": len(events),
                "events": events[:20],
                "hint": "Pairing succeeds when zigbee2mqtt/bridge/event contains type=device_joined.",
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking pairing status: {e}")
        raise HTTPException(status_code=500, detail=f"Pairing status error: {str(e)}")

# Watering Cycle API Endpoints
@app.get("/api/watering/cycle", tags=["Watering Cycle"])
async def get_watering_cycles():
    """Get all planned watering cycles (assigned and unassigned)"""
    load_watering_cycles()

    return ApiResponse(
        success=True,
        message=f"Retrieved {len(watering_cycles)} watering cycles",
        data={
            "cycles": [cycle.dict() for cycle in watering_cycles],
            "total_count": len(watering_cycles),
            "pending_count": len([c for c in watering_cycles if c.status == "pending"]),
            "completed_count": len([c for c in watering_cycles if c.status == "completed"]),
            "assigned_count": len([c for c in watering_cycles if c.plan_id]),
        }
    )


@app.get("/api/watering/cycle/{cycle_id}", tags=["Watering Cycle"])
async def get_watering_cycle(cycle_id: str):
    """Get a single watering cycle"""
    try:
        db_cycle = WateringCycleService.get_cycle(cycle_id)
        if not db_cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")

        return ApiResponse(
            success=True,
            message="Retrieved watering cycle",
            data={"cycle": WateringCycle(
                id=db_cycle.id,
                scheduled_time=db_cycle.scheduled_time,
                duration=db_cycle.duration,
                description=db_cycle.description,
                created_at=db_cycle.created_at,
                status=db_cycle.status,
                plan_id=db_cycle.plan_id,
            ).dict()}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving watering cycle: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve cycle: {str(e)}")


@app.post("/api/watering/cycle", response_model=ApiResponse, tags=["Watering Cycle"])
async def add_watering_cycle(cycle: WateringCycleRequest):
    """Create a watering cycle. Assigning it to a plan is optional."""
    try:
        try:
            if cycle.scheduled_time.endswith('Z'):
                scheduled_datetime = datetime.fromisoformat(cycle.scheduled_time.replace('Z', '+00:00'))
            elif '+' in cycle.scheduled_time or cycle.scheduled_time.endswith('00:00'):
                scheduled_datetime = datetime.fromisoformat(cycle.scheduled_time)
            else:
                local_datetime = datetime.fromisoformat(cycle.scheduled_time)
                if cycle.timezone and cycle.timezone != "UTC":
                    if cycle.timezone in ["EEST", "UTC+3", "+03:00"]:
                        scheduled_datetime = local_datetime - timedelta(hours=3)
                    elif cycle.timezone in ["EET", "UTC+2", "+02:00"]:
                        scheduled_datetime = local_datetime - timedelta(hours=2)
                    else:
                        scheduled_datetime = local_datetime
                        logger.warning(f"Unknown timezone '{cycle.timezone}', treating as UTC")
                else:
                    scheduled_datetime = local_datetime
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid datetime format. Use ISO format (e.g., '2023-12-25T10:30:00') with optional timezone"
            )

        if scheduled_datetime <= datetime.now():
            raise HTTPException(status_code=400, detail="Scheduled time must be in the future")

        if cycle.duration <= 0 or cycle.duration > 3600:
            raise HTTPException(status_code=400, detail="Duration must be between 1 and 3600 seconds")

        if cycle.plan_id:
            existing_plan = WateringPlanService.get_plan(cycle.plan_id)
            if not existing_plan:
                raise HTTPException(status_code=404, detail="Plan not found")

        db_cycle = WateringCycleService.create_cycle(
            scheduled_time=scheduled_datetime,
            duration=cycle.duration,
            description=cycle.description or f"Watering for {cycle.duration}s",
            device="0x540f57fffe890af8",
            plan_id=cycle.plan_id,
        )

        load_watering_cycles()

        return ApiResponse(
            success=True,
            message="Watering cycle added successfully",
            data={
                "cycle": {
                    "id": db_cycle.id,
                    "scheduled_time": db_cycle.scheduled_time.isoformat(),
                    "duration": db_cycle.duration,
                    "description": db_cycle.description,
                    "status": db_cycle.status,
                    "plan_id": db_cycle.plan_id,
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding watering cycle: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add cycle: {str(e)}")


@app.put("/api/watering/cycle/{cycle_id}", response_model=ApiResponse, tags=["Watering Cycle"])
async def update_watering_cycle(cycle_id: str, cycle: WateringCycleRequest):
    """Update an existing watering cycle (only if still pending)"""
    try:
        db_existing_cycle = WateringCycleService.get_cycle(cycle_id)
        if not db_existing_cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")

        if db_existing_cycle.status != "pending":
            raise HTTPException(status_code=400, detail="Can only update pending cycles")

        try:
            scheduled_datetime = datetime.fromisoformat(cycle.scheduled_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid datetime format. Use ISO format (e.g., '2023-12-25T10:30:00')"
            )

        if scheduled_datetime <= datetime.now():
            raise HTTPException(status_code=400, detail="Scheduled time must be in the future")

        if cycle.plan_id:
            existing_plan = WateringPlanService.get_plan(cycle.plan_id)
            if not existing_plan:
                raise HTTPException(status_code=404, detail="Plan not found")

        updated_cycle = WateringCycleService.update_cycle(
            cycle_id=cycle_id,
            scheduled_time=scheduled_datetime,
            duration=cycle.duration,
            description=cycle.description,
            plan_id=cycle.plan_id,
        )
        if not updated_cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")

        load_watering_cycles()

        return ApiResponse(
            success=True,
            message="Watering cycle updated successfully",
            data={"cycle": {
                "id": updated_cycle.id,
                "scheduled_time": updated_cycle.scheduled_time.isoformat(),
                "duration": updated_cycle.duration,
                "description": updated_cycle.description,
                "status": updated_cycle.status,
                "plan_id": updated_cycle.plan_id,
            }}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating watering cycle: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update cycle: {str(e)}")


@app.delete("/api/watering/cycle/{cycle_id}", response_model=ApiResponse, tags=["Watering Cycle"])
async def delete_watering_cycle(cycle_id: str):
    """Delete/cancel a watering cycle"""
    try:
        deleted = WateringCycleService.delete_cycle(cycle_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Cycle not found")

        load_watering_cycles()

        return ApiResponse(
            success=True,
            message="Watering cycle deleted successfully",
            data={"remaining_cycles": len(watering_cycles)}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting watering cycle: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete cycle: {str(e)}")


# Watering Plan API Endpoints
@app.get("/api/watering/plan", response_model=ApiResponse, tags=["Watering Plan"])
async def get_watering_plans():
    """Get watering plans (containers for planned cycles)."""
    try:
        plans = WateringPlanService.get_all_plans()
        plans_data = []
        for plan in plans:
            cycles = WateringPlanService.get_plan_cycles(plan.id)
            plan_dict = plan.to_dict()
            plan_dict["cycle_count"] = len(cycles)
            plan_dict["cycles"] = [c.to_dict() for c in cycles]
            plans_data.append(plan_dict)

        return ApiResponse(
            success=True,
            message=f"Retrieved {len(plans_data)} watering plans",
            data={"plans": plans_data, "total_count": len(plans_data)}
        )
    except Exception as e:
        logger.error(f"Error getting watering plans: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get plans: {str(e)}")


@app.get("/api/watering/plan/{plan_id}", response_model=ApiResponse, tags=["Watering Plan"])
async def get_watering_plan(plan_id: str):
    """Get one watering plan and its cycles."""
    try:
        plan = WateringPlanService.get_plan(plan_id)
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")

        cycles = WateringPlanService.get_plan_cycles(plan_id)
        plan_dict = plan.to_dict()
        plan_dict["cycle_count"] = len(cycles)
        plan_dict["cycles"] = [c.to_dict() for c in cycles]

        return ApiResponse(success=True, message="Retrieved watering plan", data={"plan": plan_dict})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting watering plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get plan: {str(e)}")


@app.post("/api/watering/plan", response_model=ApiResponse, tags=["Watering Plan"])
async def create_watering_plan(plan: WateringPlanRequest):
    """Create a watering plan container. It can start with zero cycles."""
    try:
        if plan.start_date and plan.end_date and plan.end_date < plan.start_date:
            raise HTTPException(status_code=400, detail="end_date must be after or equal to start_date")

        db_plan = WateringPlanService.create_plan(
            name=plan.name,
            description=plan.description,
            start_date=plan.start_date,
            end_date=plan.end_date,
            active=plan.active,
        )

        return ApiResponse(success=True, message="Watering plan created successfully", data={"plan": db_plan.to_dict()})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating watering plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create plan: {str(e)}")


@app.put("/api/watering/plan/{plan_id}", response_model=ApiResponse, tags=["Watering Plan"])
async def update_watering_plan(plan_id: str, plan: WateringPlanUpdateRequest):
    """Update watering plan metadata."""
    try:
        if plan.start_date and plan.end_date and plan.end_date < plan.start_date:
            raise HTTPException(status_code=400, detail="end_date must be after or equal to start_date")

        updated = WateringPlanService.update_plan(
            plan_id=plan_id,
            name=plan.name,
            description=plan.description,
            start_date=plan.start_date,
            end_date=plan.end_date,
            active=plan.active,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Plan not found")

        return ApiResponse(success=True, message="Watering plan updated successfully", data={"plan": updated.to_dict()})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating watering plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update plan: {str(e)}")


@app.delete("/api/watering/plan/{plan_id}", response_model=ApiResponse, tags=["Watering Plan"])
async def delete_watering_plan(plan_id: str):
    """Delete a watering plan. Cycles stay and become unassigned."""
    try:
        deleted = WateringPlanService.delete_plan(plan_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Plan not found")

        return ApiResponse(success=True, message="Watering plan deleted successfully", data={"deleted_plan_id": plan_id})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting watering plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {str(e)}")


@app.post("/api/watering/plan/{plan_id}/cycle/{cycle_id}", response_model=ApiResponse, tags=["Watering Plan"])
async def add_cycle_to_plan(plan_id: str, cycle_id: str):
    """Assign an existing cycle to a watering plan."""
    try:
        updated = WateringCycleService.assign_cycle_to_plan(cycle_id=cycle_id, plan_id=plan_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Plan or cycle not found")

        return ApiResponse(
            success=True,
            message="Cycle added to watering plan",
            data={"cycle_id": updated.id, "plan_id": updated.plan_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding cycle to plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add cycle to plan: {str(e)}")


@app.delete("/api/watering/plan/{plan_id}/cycle/{cycle_id}", response_model=ApiResponse, tags=["Watering Plan"])
async def remove_cycle_from_plan(plan_id: str, cycle_id: str):
    """Remove cycle from a watering plan. Cycle remains unassigned."""
    try:
        cycle = WateringCycleService.get_cycle(cycle_id)
        if not cycle:
            raise HTTPException(status_code=404, detail="Cycle not found")
        if cycle.plan_id != plan_id:
            raise HTTPException(status_code=400, detail="Cycle is not assigned to this plan")

        updated = WateringCycleService.unassign_cycle_from_plan(cycle_id)
        return ApiResponse(
            success=True,
            message="Cycle removed from watering plan",
            data={"cycle_id": updated.id, "plan_id": updated.plan_id}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing cycle from plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove cycle from plan: {str(e)}")

# =================== PLANT MANAGEMENT API ENDPOINTS ===================

# =================== GREENHOUSE MANAGEMENT API ENDPOINTS ===================

@app.post("/api/greenhouses", response_model=ApiResponse, tags=["Greenhouse Management"])
async def create_greenhouse(greenhouse: GreenhouseCreate):
    """Create greenhouse config with MQTT credentials stored in database."""
    try:
        if greenhouse.mqtt_port <= 0 or greenhouse.mqtt_port > 65535:
            raise HTTPException(status_code=400, detail="MQTT port must be between 1 and 65535")

        if not greenhouse.mqtt_username.strip():
            raise HTTPException(status_code=400, detail="MQTT username is required")

        if not greenhouse.mqtt_password.strip():
            raise HTTPException(status_code=400, detail="MQTT password is required")

        db_greenhouse = GreenhouseService.create_greenhouse(
            name=greenhouse.name,
            mqtt_username=greenhouse.mqtt_username,
            mqtt_password=greenhouse.mqtt_password,
            mqtt_broker=greenhouse.mqtt_broker,
            mqtt_port=greenhouse.mqtt_port,
            description=greenhouse.description,
            location=greenhouse.location,
            active=greenhouse.active,
        )

        return ApiResponse(
            success=True,
            message="Greenhouse created successfully",
            data={"greenhouse": db_greenhouse.to_dict()}
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating greenhouse: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create greenhouse: {str(e)}")


@app.get("/api/greenhouses", response_model=ApiResponse, tags=["Greenhouse Management"])
async def get_greenhouses(active_only: bool = False):
    """Get all greenhouses with MQTT configuration metadata."""
    try:
        greenhouses = GreenhouseService.get_all_greenhouses(active_only=active_only)
        greenhouse_data = [greenhouse.to_dict() for greenhouse in greenhouses]
        return ApiResponse(
            success=True,
            message=f"Retrieved {len(greenhouse_data)} greenhouses",
            data={
                "greenhouses": greenhouse_data,
                "count": len(greenhouse_data),
                "active_only": active_only,
            }
        )
    except Exception as e:
        logger.error(f"Error getting greenhouses: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve greenhouses: {str(e)}")


@app.get("/api/greenhouses/{greenhouse_id}", response_model=ApiResponse, tags=["Greenhouse Management"])
async def get_greenhouse(greenhouse_id: str):
    """Get one greenhouse by ID."""
    try:
        greenhouse = GreenhouseService.get_greenhouse(greenhouse_id)
        if not greenhouse:
            raise HTTPException(status_code=404, detail="Greenhouse not found")

        return ApiResponse(
            success=True,
            message="Greenhouse retrieved successfully",
            data={"greenhouse": greenhouse.to_dict()}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting greenhouse {greenhouse_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve greenhouse: {str(e)}")


@app.put("/api/greenhouses/{greenhouse_id}", response_model=ApiResponse, tags=["Greenhouse Management"])
async def update_greenhouse(greenhouse_id: str, greenhouse_update: GreenhouseUpdate):
    """Update greenhouse metadata and MQTT credentials."""
    try:
        existing = GreenhouseService.get_greenhouse(greenhouse_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Greenhouse not found")

        update_data = {}
        for field, value in greenhouse_update.dict().items():
            if value is not None:
                update_data[field] = value

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        if "mqtt_port" in update_data and (update_data["mqtt_port"] <= 0 or update_data["mqtt_port"] > 65535):
            raise HTTPException(status_code=400, detail="MQTT port must be between 1 and 65535")

        if "mqtt_username" in update_data and not update_data["mqtt_username"].strip():
            raise HTTPException(status_code=400, detail="MQTT username cannot be empty")

        if "mqtt_password" in update_data and not update_data["mqtt_password"].strip():
            raise HTTPException(status_code=400, detail="MQTT password cannot be empty")

        updated = GreenhouseService.update_greenhouse(greenhouse_id, **update_data)
        return ApiResponse(
            success=True,
            message="Greenhouse updated successfully",
            data={"greenhouse": updated.to_dict()}
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating greenhouse {greenhouse_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update greenhouse: {str(e)}")


@app.delete("/api/greenhouses/{greenhouse_id}", response_model=ApiResponse, tags=["Greenhouse Management"])
async def delete_greenhouse(greenhouse_id: str):
    """Soft-delete greenhouse by marking it inactive."""
    try:
        success = GreenhouseService.delete_greenhouse(greenhouse_id)
        if not success:
            raise HTTPException(status_code=404, detail="Greenhouse not found")

        return ApiResponse(
            success=True,
            message="Greenhouse removed successfully",
            data={
                "greenhouse_id": greenhouse_id,
                "action": "deactivated"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting greenhouse {greenhouse_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove greenhouse: {str(e)}")

# =================== END GREENHOUSE MANAGEMENT API ENDPOINTS ===================

@app.post("/api/plants", response_model=ApiResponse, tags=["Plant Management"])
async def create_plant(plant: PlantCreate):
    """Register a new plant in the greenhouse (FR-9)"""
    try:
        # Validate input data
        if plant.watering_frequency <= 0:
            raise HTTPException(status_code=400, detail="Watering frequency must be positive")
        
        if plant.watering_duration <= 0:
            raise HTTPException(status_code=400, detail="Watering duration must be positive")
        
        if plant.location_row <= 0 or plant.location_column <= 0:
            raise HTTPException(status_code=400, detail="Location coordinates must be positive")
        
        if plant.planting_date > date.today():
            raise HTTPException(status_code=400, detail="Planting date cannot be in the future")
        
        # Create plant using service
        db_plant = PlantService.create_plant(
            name=plant.name,
            variety=plant.variety,
            planting_date=plant.planting_date,
            watering_frequency=plant.watering_frequency,
            watering_duration=plant.watering_duration,
            water_amount_ml=plant.water_amount_ml,
            harvest_date_estimate=plant.harvest_date_estimate,
            harvest_quantity_estimate=plant.harvest_quantity_estimate,
            location_row=plant.location_row,
            location_column=plant.location_column,
            location_description=plant.location_description,
            notes=plant.notes,
            active=plant.active
        )
        
        return ApiResponse(
            success=True,
            message="Plant registered successfully",
            data={
                "plant": db_plant.to_dict()
            }
        )
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error creating plant: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to register plant: {str(e)}")

@app.get("/api/plants", response_model=ApiResponse, tags=["Plant Management"])
async def get_all_plants(
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0
):
    """Get all registered plants with pagination (FR-16)"""
    try:
        plants = PlantService.get_all_plants(
            active_only=active_only,
            limit=limit,
            offset=offset
        )
        
        plants_data = [plant.to_dict() for plant in plants]
        
        return ApiResponse(
            success=True,
            message=f"Retrieved {len(plants_data)} plants",
            data={
                "plants": plants_data,
                "count": len(plants_data),
                "active_only": active_only,
                "limit": limit,
                "offset": offset
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting plants: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve plants: {str(e)}")

@app.get("/api/plants/{plant_id}", response_model=ApiResponse, tags=["Plant Management"])
async def get_plant(plant_id: str):
    """Get specific plant information by ID (FR-16)"""
    try:
        plant = PlantService.get_plant(plant_id)
        
        if not plant:
            raise HTTPException(status_code=404, detail="Plant not found")
        
        return ApiResponse(
            success=True,
            message="Plant retrieved successfully",
            data={
                "plant": plant.to_dict()
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting plant {plant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve plant: {str(e)}")

@app.put("/api/plants/{plant_id}", response_model=ApiResponse, tags=["Plant Management"])
async def update_plant(plant_id: str, plant_update: PlantUpdate):
    """Update plant information (FR-16)"""
    try:
        # Check if plant exists
        existing_plant = PlantService.get_plant(plant_id)
        if not existing_plant:
            raise HTTPException(status_code=404, detail="Plant not found")
        
        # Prepare update data (only include non-None values)
        update_data = {}
        for field, value in plant_update.dict().items():
            if value is not None:
                update_data[field] = value
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Validate dates
        if 'planting_date' in update_data and update_data['planting_date'] > date.today():
            raise HTTPException(status_code=400, detail="Planting date cannot be in the future")
        
        # Update plant
        updated_plant = PlantService.update_plant(plant_id, **update_data)
        
        return ApiResponse(
            success=True,
            message="Plant updated successfully",
            data={
                "plant": updated_plant.to_dict()
            }
        )
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating plant {plant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update plant: {str(e)}")

@app.delete("/api/plants/{plant_id}", response_model=ApiResponse, tags=["Plant Management"])
async def delete_plant(plant_id: str):
    """Remove plant from greenhouse (soft delete)"""
    try:
        success = PlantService.delete_plant(plant_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Plant not found")
        
        return ApiResponse(
            success=True,
            message="Plant removed successfully",
            data={
                "plant_id": plant_id,
                "action": "deactivated"
            }
        )
        
    except Exception as e:
        logger.error(f"Error deleting plant {plant_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to remove plant: {str(e)}")

@app.get("/api/plants/location/{row}/{column}", response_model=ApiResponse, tags=["Plant Management"])
async def get_plant_at_location(row: int, column: int):
    """Get plant at specific greenhouse location (FR-15)"""
    try:
        plants = PlantService.get_plants_by_location(row=row, column=column)
        
        if not plants:
            return ApiResponse(
                success=True,
                message=f"No plant found at location R{row}C{column}",
                data={
                    "location": f"R{row}C{column}",
                    "plant": None
                }
            )
        
        # Should only be one plant per location for active plants
        plant = plants[0]
        
        return ApiResponse(
            success=True,
            message=f"Plant found at location R{row}C{column}",
            data={
                "location": f"R{row}C{column}",
                "plant": plant.to_dict()
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting plant at location R{row}C{column}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve plant at location: {str(e)}")

@app.get("/api/plants/search", response_model=ApiResponse, tags=["Plant Management"])
async def search_plants(
    name: str = None,
    variety: str = None,
    active_only: bool = True
):
    """Search plants by name or variety"""
    try:
        plants = PlantService.search_plants(
            name=name,
            variety=variety,
            active_only=active_only
        )
        
        plants_data = [plant.to_dict() for plant in plants]
        
        return ApiResponse(
            success=True,
            message=f"Found {len(plants_data)} matching plants",
            data={
                "plants": plants_data,
                "search_criteria": {
                    "name": name,
                    "variety": variety,
                    "active_only": active_only
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error searching plants: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search plants: {str(e)}")

@app.get("/api/greenhouse/layout", response_model=ApiResponse, tags=["Plant Management"])
async def get_greenhouse_layout(max_rows: int = 10, max_columns: int = 10):
    """Get complete greenhouse layout with plant positions (FR-15)"""
    try:
        layout = PlantService.get_greenhouse_layout(max_rows=max_rows, max_columns=max_columns)
        
        return ApiResponse(
            success=True,
            message="Greenhouse layout retrieved successfully",
            data={
                "layout": layout,
                "dimensions": {
                    "max_rows": max_rows,
                    "max_columns": max_columns
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting greenhouse layout: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve greenhouse layout: {str(e)}")

@app.get("/api/plants/harvest-ready", response_model=ApiResponse, tags=["Plant Management"])
async def get_plants_ready_for_harvest():
    """Get plants that are ready for harvest (FR-14)"""
    try:
        plants = PlantService.get_plants_ready_for_harvest()
        plants_data = [plant.to_dict() for plant in plants]
        
        return ApiResponse(
            success=True,
            message=f"Found {len(plants_data)} plants ready for harvest",
            data={
                "plants": plants_data,
                "count": len(plants_data)
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting harvest-ready plants: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve harvest-ready plants: {str(e)}")

# =================== END PLANT MANAGEMENT API ENDPOINTS ===================

def check_and_execute_scheduled_waterings():
    """Background task to check and execute scheduled watering cycles"""
    while True:
        try:
            current_time = datetime.now()
            
            with cycle_execution_lock:
                for entry in watering_cycle[:]:  # Create a copy to iterate safely
                    if (entry.status == "pending" and 
                        entry.scheduled_time <= current_time):
                        
                        logger.info(f"Executing scheduled watering: {entry.id}")
                        entry.status = "executing"
                        
                        # Send watering request to MQTT timer service
                        schedule_request = {
                            "device": DEVICES['irrigation_controller']['name'],
                            "duration": entry.duration,
                            "action": "schedule",
                            "requested_by": "watering_cycle",
                            "cycle_entry_id": entry.id,
                            "description": entry.description,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        success = mqtt_client.publish("smart_greenhouse/schedule/request", schedule_request)
                        
                        if success:
                            logger.info(f"Successfully sent scheduled watering command for entry {entry.id}")
                            # Note: Status will be updated to "completed" when we receive confirmation
                            # via MQTT status updates. For now, we'll mark as executing.
                        else:
                            logger.error(f"Failed to send scheduled watering command for entry {entry.id}")
                            entry.status = "failed"
            
            # Sleep for 30 seconds before checking again
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"Error in scheduled watering checker: {e}")
            time.sleep(30)  # Continue checking even if there's an error

def main():
    """Initialize and start the FastAPI server"""
    logger.info("Starting Automated Irrigation System API with PostgreSQL")
    
    # Initialize database connection
    if not test_database_connection():
        logger.error("Failed to connect to database. Please check PostgreSQL connection.")
        return
    
    if not init_database():
        logger.error("Failed to initialize database")
        return
        
    logger.info("Database connection successful")
    logger.info("Database initialized successfully")
    
    # Load existing watering cycles from database
    load_watering_cycles()
    
    # Connect to MQTT
    if mqtt_client.connect():
        logger.info("MQTT connection established")
    else:
        logger.error("Failed to connect to MQTT broker")
        
    # Wait a moment for MQTT connection
    time.sleep(2)
    
    # NOTE: Background schedulers disabled - now using Celery for task scheduling
    # # Start background task for scheduled irrigations
    # scheduler_thread = threading.Thread(target=check_and_execute_scheduled_irrigations, daemon=True)
    # scheduler_thread.start()
    # logger.info("Started irrigation schedule checker background task")
    
    # Start FastAPI server with uvicorn
    logger.info("Starting FastAPI server on http://localhost:8000")
    logger.info("API Documentation available at: http://localhost:8000/docs")
    logger.info("Alternative docs at: http://localhost:8000/redoc")
    
    # NOTE: Background scheduler disabled - now using Celery for task scheduling
    # # Start background scheduler in a separate thread
    # def start_scheduler():
    #     import asyncio
    #     loop = asyncio.new_event_loop()
    #     asyncio.set_event_loop(loop)
    #     loop.run_until_complete(watering_scheduler())
    # 
    # scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    # scheduler_thread.start()
    # logger.info("Started irrigation scheduler in background thread")
    
    # Start FastAPI server with uvicorn
    logger.info("Starting FastAPI server on http://localhost:8000")
    logger.info("API Documentation available at: http://localhost:8000/docs")
    logger.info("Alternative docs at: http://localhost:8000/redoc")
    
    uvicorn.run(
        "smart_greenhouse_api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Set to True for development
        log_level="info"
    )

if __name__ == '__main__':
    main()
