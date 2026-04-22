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
from irrigation_db_service import IrrigationPlanService
from plant_db_service import PlantService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic models for request/response
class IrrigationCommand(BaseModel):
    action: str  # "ON" or "OFF"

class IrrigationSchedule(BaseModel):
    duration: int  # Duration in seconds

class IrrigationPlanEntry(BaseModel):
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
    
    def __init__(self, **data):
        if 'id' not in data or data['id'] is None:
            data['id'] = str(uuid.uuid4())
        super().__init__(**data)

class IrrigationPlanRequest(BaseModel):
    scheduled_time: str  # ISO format datetime string
    duration: int  # Duration in seconds
    description: Optional[str] = None
    timezone: Optional[str] = "UTC"  # Default to UTC, can be "EEST", "UTC+3", etc.

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[Any, Any]] = None
    timestamp: str = datetime.utcnow().isoformat()

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

# Irrigation plans storage (kept for compatibility)
irrigation_plans: List[IrrigationPlanEntry] = []
irrigation_plan = []  # Store scheduled irrigations
plan_execution_lock = threading.Lock()

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
            client.subscribe("irrigation/status/+")
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
                
            elif "irrigation/status/" in topic:
                # Handle timer service status updates
                status_type = topic.split("/")[-1]  # e.g., "schedule"
                timer_service_status[status_type] = payload
                timer_service_status['last_updated'] = datetime.now().isoformat()
                logger.info(f"Timer service {status_type} status: {payload}")
                
                # Check if this is a completion status for a planned irrigation
                if (status_type == "schedule" and 
                    "plan_entry_id" in payload and 
                    "status" in payload):
                    
                    plan_entry_id = payload["plan_entry_id"]
                    irrigation_status = payload["status"]  # e.g., "completed", "failed"
                    
                    # Update the irrigation plan entry status
                    with plan_execution_lock:
                        for entry in irrigation_plan:
                            if entry.id == plan_entry_id:
                                entry.status = irrigation_status
                                logger.info(f"Updated irrigation plan entry {plan_entry_id} status to: {irrigation_status}")
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
def load_irrigation_plans():
    """Load irrigation plans from PostgreSQL database"""
    global irrigation_plans
    try:
        # Get plans from database using the service
        db_plans = IrrigationPlanService.get_all_plans()
        irrigation_plans = []
        
        for db_plan in db_plans:
            # Convert database model to IrrigationPlanEntry for compatibility
            plan_entry = IrrigationPlanEntry(
                id=db_plan.id,
                scheduled_time=db_plan.scheduled_time,
                duration=db_plan.duration,
                description=db_plan.description,
                created_at=db_plan.created_at,
                status=db_plan.status
            )
            irrigation_plans.append(plan_entry)
            
        logger.info(f"Successfully loaded {len(irrigation_plans)} irrigation plans from database")
        
    except Exception as e:
        logger.error(f"Error loading irrigation plans from database: {e}")
        irrigation_plans = []

def save_irrigation_plans():
    """Save operation not needed - using database directly"""
    # This function is kept for compatibility but doesn't do anything
    # since we now save directly to database in the API endpoints
    pass

def cleanup_old_plans():
    """Remove completed plans older than 24 hours"""
    global irrigation_plans
    cutoff_time = datetime.utcnow() - timedelta(hours=24)
    initial_count = len(irrigation_plans)
    
    irrigation_plans = [
        plan for plan in irrigation_plans 
        if not (plan.status in ["completed", "failed"] and plan.executed_at and plan.executed_at < cutoff_time)
    ]
    
    removed_count = initial_count - len(irrigation_plans)
    if removed_count > 0:
        logger.info(f"Cleaned up {removed_count} old irrigation plan entries")
        save_irrigation_plans()

async def execute_scheduled_irrigation(plan: IrrigationPlanEntry):
    """Execute a scheduled irrigation plan"""
    try:
        plan.status = "executing"
        plan.executed_at = datetime.utcnow()
        save_irrigation_plans()
        
        logger.info(f"Executing scheduled irrigation plan {plan.id}: {plan.duration}s")
        
        # Send schedule request to MQTT timer service
        schedule_request = {
            "device": DEVICES['irrigation_controller']['name'],
            "duration": plan.duration,
            "action": "schedule",
            "requested_by": "scheduler",
            "plan_id": plan.id,
            "timestamp": datetime.now().isoformat()
        }
        
        success = mqtt_client.publish("irrigation/schedule/request", schedule_request)
        
        if success:
            plan.status = "completed"
            plan.result = f"Successfully scheduled {plan.duration}s irrigation"
            logger.info(f"Scheduled irrigation plan {plan.id} executed successfully")
        else:
            plan.status = "failed"
            plan.result = "Failed to send command to MQTT timer service"
            logger.error(f"Failed to execute irrigation plan {plan.id}")
            
    except Exception as e:
        plan.status = "failed"
        plan.result = f"Execution error: {str(e)}"
        logger.error(f"Error executing irrigation plan {plan.id}: {e}")
    
    save_irrigation_plans()

async def irrigation_scheduler():
    """Background task to check and execute scheduled irrigations"""
    logger.info("Irrigation scheduler started")
    
    while True:
        try:
            current_time = datetime.utcnow()
            
            # Find pending plans that should be executed
            for plan in irrigation_plans:
                if (plan.status == "pending" and 
                    plan.scheduled_time <= current_time):
                    
                    await execute_scheduled_irrigation(plan)
            
            # Cleanup old plans every hour
            if current_time.minute == 0 and current_time.second < 30:
                cleanup_old_plans()
                
        except Exception as e:
            logger.error(f"Error in irrigation scheduler: {e}")
        
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

@app.post("/api/irrigation/control", response_model=ApiResponse, tags=["Irrigation"])
async def control_irrigation(command: IrrigationCommand):
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
        
        success = mqtt_client.publish("irrigation/control/request", control_request)
        
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

@app.get("/api/irrigation/status", tags=["Irrigation"])
async def get_irrigation_status():
    """Get current irrigation system (0x540f57fffe890af8) status"""
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

@app.post("/api/irrigation/schedule", response_model=ApiResponse, tags=["Irrigation"])
async def schedule_irrigation(schedule: IrrigationSchedule):
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
        
        success = mqtt_client.publish("irrigation/schedule/request", schedule_request)
        
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

@app.get("/api/irrigation/schedule/status", tags=["Irrigation"])
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

@app.delete("/api/irrigation/plan/{entry_id}", response_model=ApiResponse, tags=["Irrigation Planning"])
async def cancel_planned_irrigation(entry_id: str):
    """Cancel a planned irrigation entry"""
    global irrigation_plan
    
    # Find and remove the entry
    entry_found = False
    for i, entry in enumerate(irrigation_plan):
        if entry.id == entry_id:
            if entry.status == "executing":
                raise HTTPException(
                    status_code=400,
                    detail="Cannot cancel irrigation that is currently executing"
                )
            irrigation_plan[i].status = "cancelled"
            entry_found = True
            break
    
    if not entry_found:
        raise HTTPException(
            status_code=404,
            detail="Irrigation plan entry not found"
        )
    
    return ApiResponse(
        success=True,
        message=f"Irrigation plan entry {entry_id} cancelled",
        data={"cancelled_entry_id": entry_id}
    )

@app.put("/api/irrigation/plan/{entry_id}", response_model=ApiResponse, tags=["Irrigation Planning"])
async def update_planned_irrigation(entry_id: str, plan_request: IrrigationPlanRequest):
    """Update a planned irrigation entry"""
    global irrigation_plan
    
    # Find the entry
    entry_index = None
    for i, entry in enumerate(irrigation_plan):
        if entry.id == entry_id:
            if entry.status not in ["pending"]:
                raise HTTPException(
                    status_code=400,
                    detail="Can only modify pending irrigation entries"
                )
            entry_index = i
            break
    
    if entry_index is None:
        raise HTTPException(
            status_code=404,
            detail="Irrigation plan entry not found"
        )
    
    # Parse and validate new scheduled time
    try:
        scheduled_dt = datetime.fromisoformat(plan_request.scheduled_time.replace('Z', '+00:00'))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid datetime format. Use ISO format"
        )
    
    if scheduled_dt <= datetime.utcnow():
        raise HTTPException(
            status_code=400,
            detail="Scheduled time must be in the future"
        )
    
    # Validate duration
    if plan_request.duration <= 0 or plan_request.duration > 3600:
        raise HTTPException(
            status_code=400,
            detail="Duration must be between 1 and 3600 seconds"
        )
    
    # Update the entry
    irrigation_plan[entry_index].scheduled_time = scheduled_dt
    irrigation_plan[entry_index].duration = plan_request.duration
    irrigation_plan[entry_index].description = plan_request.description
    
    return ApiResponse(
        success=True,
        message="Irrigation plan entry updated successfully",
        data={"updated_entry": irrigation_plan[entry_index].dict()}
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

# Irrigation Planning API Endpoints
@app.get("/api/irrigation/plan", tags=["Irrigation Planning"])
async def get_irrigation_plans():
    """Get all scheduled irrigation plans"""
    # Reload from database to get latest data
    load_irrigation_plans()
    
    return ApiResponse(
        success=True,
        message=f"Retrieved {len(irrigation_plans)} irrigation plans",
        data={
            "plans": [plan.dict() for plan in irrigation_plans],
            "total_count": len(irrigation_plans),
            "pending_count": len([p for p in irrigation_plans if p.status == "pending"]),
            "completed_count": len([p for p in irrigation_plans if p.status == "completed"])
        }
    )

@app.post("/api/irrigation/plan", response_model=ApiResponse, tags=["Irrigation Planning"])
async def add_irrigation_plan(plan: IrrigationPlanRequest):
    """Add a new scheduled irrigation to the plan"""
    try:
        # Parse the scheduled time and handle timezone conversion
        try:
            # Parse the datetime
            if plan.scheduled_time.endswith('Z'):
                # UTC timezone specified
                scheduled_datetime = datetime.fromisoformat(plan.scheduled_time.replace('Z', '+00:00'))
            elif '+' in plan.scheduled_time or plan.scheduled_time.endswith('00:00'):
                # Timezone offset specified in the string
                scheduled_datetime = datetime.fromisoformat(plan.scheduled_time)
            else:
                # No timezone in string, use the timezone parameter
                local_datetime = datetime.fromisoformat(plan.scheduled_time)
                
                # Convert based on timezone parameter
                if plan.timezone and plan.timezone != "UTC":
                    if plan.timezone in ["EEST", "UTC+3", "+03:00"]:
                        # EEST is UTC+3, so subtract 3 hours to get UTC
                        scheduled_datetime = local_datetime - timedelta(hours=3)
                    elif plan.timezone in ["EET", "UTC+2", "+02:00"]:
                        # EET is UTC+2, so subtract 2 hours to get UTC  
                        scheduled_datetime = local_datetime - timedelta(hours=2)
                    else:
                        # Default to treating as UTC if unknown timezone
                        scheduled_datetime = local_datetime
                        logger.warning(f"Unknown timezone '{plan.timezone}', treating as UTC")
                else:
                    # Default to UTC
                    scheduled_datetime = local_datetime
                    
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid datetime format. Use ISO format (e.g., '2023-12-25T10:30:00') with optional timezone"
            )
        
        # Validate schedule time is in the future
        if scheduled_datetime <= datetime.now():
            raise HTTPException(
                status_code=400,
                detail="Scheduled time must be in the future"
            )
        
        # Validate duration
        if plan.duration <= 0 or plan.duration > 3600:
            raise HTTPException(
                status_code=400,
                detail="Duration must be between 1 and 3600 seconds"
            )
        
        # Create plan in database using service
        db_plan = IrrigationPlanService.create_plan(
            scheduled_time=scheduled_datetime,
            duration=plan.duration,
            description=plan.description or f"Irrigation for {plan.duration}s",
            device="0x540f57fffe890af8"  # Default irrigation controller
        )
        
        # Reload plans from database
        load_irrigation_plans()
        
        return ApiResponse(
            success=True,
            message="Irrigation plan added successfully",
            data={
                "plan": {
                    "id": db_plan.id,
                    "scheduled_time": db_plan.scheduled_time.isoformat(),
                    "duration": db_plan.duration,
                    "description": db_plan.description,
                    "status": db_plan.status
                },
                "total_plans": len(irrigation_plans)
            }
        )
        
    except Exception as e:
        logger.error(f"Error adding irrigation plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add plan: {str(e)}")

@app.put("/api/irrigation/plan/{plan_id}", response_model=ApiResponse, tags=["Irrigation Planning"])
async def update_irrigation_plan(plan_id: str, plan: IrrigationPlanRequest):
    """Update an existing irrigation plan (only if still pending)"""
    try:
        # Find the plan
        plan_entry = None
        for p in irrigation_plans:
            if p.id == plan_id:
                plan_entry = p
                break
        
        if not plan_entry:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        if plan_entry.status != "pending":
            raise HTTPException(
                status_code=400, 
                detail="Can only update pending plans"
            )
        
        # Parse the scheduled time
        try:
            scheduled_datetime = datetime.fromisoformat(plan.scheduled_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid datetime format. Use ISO format (e.g., '2023-12-25T10:30:00')"
            )
        
        # Validate new schedule time
        if scheduled_datetime <= datetime.now():
            raise HTTPException(
                status_code=400,
                detail="Scheduled time must be in the future"
            )
        
        # Update plan
        plan_entry.scheduled_time = scheduled_datetime
        plan_entry.duration = plan.duration
        plan_entry.description = plan.description or plan_entry.description
        
        save_irrigation_plans()
        
        return ApiResponse(
            success=True,
            message="Irrigation plan updated successfully",
            data={"plan": plan_entry.dict()}
        )
        
    except Exception as e:
        logger.error(f"Error updating irrigation plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update plan: {str(e)}")

@app.delete("/api/irrigation/plan/{plan_id}", response_model=ApiResponse, tags=["Irrigation Planning"])
async def delete_irrigation_plan(plan_id: str):
    """Delete/cancel an irrigation plan"""
    try:
        global irrigation_plans
        
        # Find and remove the plan
        original_count = len(irrigation_plans)
        irrigation_plans = [p for p in irrigation_plans if p.id != plan_id]
        
        if len(irrigation_plans) == original_count:
            raise HTTPException(status_code=404, detail="Plan not found")
        
        save_irrigation_plans()
        
        return ApiResponse(
            success=True,
            message="Irrigation plan deleted successfully",
            data={"remaining_plans": len(irrigation_plans)}
        )
        
    except Exception as e:
        logger.error(f"Error deleting irrigation plan: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {str(e)}")

# =================== PLANT MANAGEMENT API ENDPOINTS ===================

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

def check_and_execute_scheduled_irrigations():
    """Background task to check and execute scheduled irrigations"""
    while True:
        try:
            current_time = datetime.now()
            
            with plan_execution_lock:
                for entry in irrigation_plan[:]:  # Create a copy to iterate safely
                    if (entry.status == "pending" and 
                        entry.scheduled_time <= current_time):
                        
                        logger.info(f"Executing scheduled irrigation: {entry.id}")
                        entry.status = "executing"
                        
                        # Send irrigation request to MQTT timer service
                        schedule_request = {
                            "device": DEVICES['irrigation_controller']['name'],
                            "duration": entry.duration,
                            "action": "schedule",
                            "requested_by": "irrigation_plan",
                            "plan_entry_id": entry.id,
                            "description": entry.description,
                            "timestamp": datetime.now().isoformat()
                        }
                        
                        success = mqtt_client.publish("irrigation/schedule/request", schedule_request)
                        
                        if success:
                            logger.info(f"Successfully sent scheduled irrigation command for entry {entry.id}")
                            # Note: Status will be updated to "completed" when we receive confirmation
                            # via MQTT status updates. For now, we'll mark as executing.
                        else:
                            logger.error(f"Failed to send scheduled irrigation command for entry {entry.id}")
                            entry.status = "failed"
            
            # Sleep for 30 seconds before checking again
            time.sleep(30)
            
        except Exception as e:
            logger.error(f"Error in scheduled irrigation checker: {e}")
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
    
    # Load existing irrigation plans from database
    load_irrigation_plans()
    
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
    #     loop.run_until_complete(irrigation_scheduler())
    # 
    # scheduler_thread = threading.Thread(target=start_scheduler, daemon=True)
    # scheduler_thread.start()
    # logger.info("Started irrigation scheduler in background thread")
    
    # Start FastAPI server with uvicorn
    logger.info("Starting FastAPI server on http://localhost:8000")
    logger.info("API Documentation available at: http://localhost:8000/docs")
    logger.info("Alternative docs at: http://localhost:8000/redoc")
    
    uvicorn.run(
        "irrigation_api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Set to True for development
        log_level="info"
    )

if __name__ == '__main__':
    main()