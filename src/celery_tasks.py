#!/usr/bin/env python3
"""
Celery Tasks for Irrigation System
Replaces APScheduler job execution with distributed task queue
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import paho.mqtt.client as mqtt
from celery import shared_task
from celery.exceptions import Retry, WorkerLostError

# Database imports
from database import init_database
from smart_greenhouse_db_service import WateringCycleService
from models import WateringCycle
from celery_config import celery_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MQTT_BROKER = "192.168.8.151"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
API_BASE_URL = "http://irrigation-api:8000/api"  # FastAPI server in container

# Global MQTT client for tasks
mqtt_client = None
mqtt_connected = False

def get_mqtt_client():
    """Get or create MQTT client for task execution"""
    global mqtt_client, mqtt_connected
    
    if mqtt_client is None or not mqtt_connected:
        try:
            mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_start()
            mqtt_connected = True
            logger.info("MQTT client initialized for Celery task")
            time.sleep(1)  # Give connection time to establish
            return mqtt_client
        except Exception as e:
            logger.error(f"Failed to initialize MQTT client: {e}")
            mqtt_connected = False
            return None
    
    return mqtt_client

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def update_cycle_status(self, cycle_id: str, status: str, result: str = None):
    """Update the status of a watering cycle (Celery task)"""
    try:
        WateringCycleService.update_cycle_status(
            cycle_id=cycle_id,
            status=status,
            result=result,
            executed_at=datetime.utcnow() if status in ['executing', 'completed', 'failed'] else None
        )
        logger.info(f"Updated cycle {cycle_id} status to: {status}")
        return f"Successfully updated cycle {cycle_id} status to {status}"
    except Exception as e:
        logger.error(f"Error updating cycle status: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def execute_irrigation(self, cycle_id: str, device: str, duration: int, description: str):
    """Execute watering using MQTT"""
    logger.info(f"Executing watering cycle {cycle_id}: {duration}s - {description}")
    
    try:
        # Update cycle status to executing immediately
        try:
            WateringCycleService.update_cycle_status(
                cycle_id=cycle_id,
                status="executing",
                result=f"Started at {datetime.utcnow().isoformat()}",
                executed_at=datetime.utcnow()
            )
            logger.info(f"✅ SUCCESS: Cycle {cycle_id} marked as executing in database")
        except Exception as db_error:
            logger.error(f"❌ FAILED to mark cycle {cycle_id} as executing: {db_error}")
            # Continue with execution even if status update fails
        
        # Create MQTT client
        client = mqtt.Client()
        
        try:
            # Connect to MQTT broker
            client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            client.loop_start()
            
            # Send irrigation command
            topic = f"smart_greenhouse/{device}/command"
            payload = {
                "action": "start_irrigation",
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            result = client.publish(topic, json.dumps(payload))
            
            if result.rc == 0:
                logger.info(f"Successfully sent watering command for cycle {cycle_id}")
                # Update status immediately to ensure completion is recorded
                try:
                    WateringCycleService.update_cycle_status(
                        cycle_id=cycle_id,
                        status="completed",
                        result=f"Watering executed for {duration}s with device {device}",
                        executed_at=datetime.utcnow()
                    )
                    logger.info(f"✅ SUCCESS: Cycle {cycle_id} marked as completed in database")
                except Exception as db_error:
                    logger.error(f"❌ FAILED to mark cycle {cycle_id} as completed: {db_error}")
                    # Still return success for MQTT but log database issue
                return f"Successfully executed watering for cycle {cycle_id}"
            else:
                error_msg = f"Failed to publish MQTT message for cycle {cycle_id}: {result.rc}"
                logger.error(error_msg)
                # Update status immediately for failed execution
                WateringCycleService.update_cycle_status(
                    cycle_id=cycle_id,
                    status="failed",
                    result=error_msg,
                    executed_at=datetime.utcnow()
                )
                logger.info(f"Cycle {cycle_id} marked as failed in database")
                raise Exception(error_msg)
                
        except Exception as mqtt_error:
            error_msg = f"MQTT error for cycle {cycle_id}: {str(mqtt_error)}"
            logger.error(error_msg)
            # Update status immediately for MQTT connection errors
            WateringCycleService.update_cycle_status(
                cycle_id=cycle_id,
                status="failed",
                result=error_msg,
                executed_at=datetime.utcnow()
            )
            logger.info(f"Cycle {cycle_id} marked as failed in database due to MQTT error")
            raise Exception(error_msg)
            
        finally:
            client.loop_stop()
            client.disconnect()
            
    except Exception as e:
        logger.error(f"Error executing watering cycle {cycle_id}: {e}")
        # Update status immediately for general execution errors
        try:
            WateringCycleService.update_cycle_status(
                cycle_id=cycle_id,
                status="failed",
                result=f"Execution error: {str(e)}",
                executed_at=datetime.utcnow()
            )
            logger.info(f"Cycle {cycle_id} marked as failed in database due to execution error")
        except Exception as db_error:
            logger.error(f"Failed to update database status for cycle {cycle_id}: {db_error}")
        raise self.retry(exc=e)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 30})
def check_due_irrigations(self):
    """
    Periodic task to check database and execute due watering cycles
    Replaces the APScheduler periodic_irrigation_check function
    """
    try:
        logger.info("Checking for due watering cycles (Celery)...")
        
        # Get all pending cycles from database
        cycles = WateringCycleService.get_pending_cycles()
        
        if not cycles:
            logger.debug("No pending watering cycles found")
            return "No pending cycles"
            
        logger.info(f"Found {len(cycles)} pending watering cycles")
        
        current_time = datetime.utcnow()
        executed_count = 0
        
        for cycle in cycles:
            try:
                scheduled_time = cycle.scheduled_time
                cycle_id = cycle.id
                
                # Check if it's time to execute (within 1 minute window)
                time_diff = (current_time - scheduled_time).total_seconds()
                
                if time_diff >= 0 and time_diff <= 60:  # Execute if due (max 1 min late)
                    logger.info(f"Scheduling due watering cycle {cycle_id}: {cycle.description}")
                    
                    # Execute watering as separate Celery task
                    execute_irrigation.delay(
                        cycle_id=cycle_id,
                        device=cycle.device or "0x540f57fffe890af8",  # Use proper Zigbee device ID
                        duration=cycle.duration,
                        description=cycle.description or 'Scheduled watering'
                    )
                    
                    executed_count += 1
                    
                elif time_diff > 60:  # More than 1 minute late
                    logger.warning(f"Cycle {cycle_id} is {time_diff/60:.1f} minutes overdue - skipping")
                    WateringCycleService.update_cycle_status(
                        cycle_id=cycle_id,
                        status="failed",
                        result="Execution window missed",
                        executed_at=datetime.utcnow()
                    )
                    logger.info(f"Cycle {cycle_id} marked as failed (overdue) in database")
                    
                else:
                    # Cycle is in the future
                    time_until = -time_diff
                    if time_until < 300:  # Less than 5 minutes away
                        logger.info(f"Cycle {cycle_id} due in {time_until/60:.1f} minutes")
                        
            except Exception as e:
                logger.error(f"Error processing cycle {cycle.id}: {e}")
                
        if executed_count > 0:
            logger.info(f"Successfully scheduled {executed_count} watering tasks")
            
        return f"Processed {len(cycles)} cycles, scheduled {executed_count} tasks"
            
    except Exception as e:
        logger.error(f"Error in periodic watering check: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 120})
def schedule_irrigation_plan(self, plan_data: dict):
    """
    Schedule a new watering cycle (called from API)
    Replaces direct APScheduler job creation
    """
    try:
        logger.info(f"Scheduling new watering cycle: {plan_data}")
        
        # Create cycle in database
        cycle = WateringCycle(**plan_data)
        created_cycle = WateringCycleService.create_cycle(cycle)
        
        logger.info(f"Created watering cycle {created_cycle.id} for {created_cycle.scheduled_time}")
        
        # Calculate time until execution
        current_time = datetime.utcnow()
        scheduled_time = created_cycle.scheduled_time
        delay_seconds = (scheduled_time - current_time).total_seconds()
        
        if delay_seconds > 0:
            # Schedule task to run at the specific time
            execute_irrigation.apply_async(
                args=[
                    created_cycle.id,
                    created_cycle.device or "0x540f57fffe890af8", 
                    created_cycle.duration,
                    created_cycle.description or 'Scheduled watering'
                ],
                countdown=delay_seconds
            )
            logger.info(f"Scheduled watering task to run in {delay_seconds/3600:.2f} hours")
        else:
            # Execute immediately if scheduled time is in the past
            logger.warning(f"Cycle {created_cycle.id} scheduled in past, executing immediately")
            execute_irrigation.delay(
                created_cycle.id,
                created_cycle.device or "0x540f57fffe890af8",
                created_cycle.duration, 
                created_cycle.description or 'Scheduled watering'
            )
        
        return {
            "success": True,
            "cycle_id": created_cycle.id,
            "scheduled_for": created_cycle.scheduled_time.isoformat(),
            "delay_seconds": max(0, delay_seconds)
        }
        
    except Exception as e:
        logger.error(f"Error scheduling watering cycle: {e}")
        raise self.retry(exc=e)

# Health check task for monitoring
@shared_task
def health_check():
    """Simple health check task for monitoring Celery workers"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "worker": "irrigation_celery_worker"
    }
