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
from irrigation_db_service import IrrigationPlanService
from models import IrrigationPlan
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
def update_plan_status(self, plan_id: str, status: str, result: str = None):
    """Update the status of an irrigation plan (Celery task)"""
    try:
        IrrigationPlanService.update_plan_status(
            plan_id=plan_id,
            status=status,
            result=result,
            executed_at=datetime.utcnow() if status in ['executing', 'completed', 'failed'] else None
        )
        logger.info(f"Updated plan {plan_id} status to: {status}")
        return f"Successfully updated plan {plan_id} status to {status}"
    except Exception as e:
        logger.error(f"Error updating plan status: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def execute_irrigation(self, plan_id: str, device: str, duration: int, description: str):
    """Execute irrigation using MQTT"""
    logger.info(f"Executing irrigation {plan_id}: {duration}s - {description}")
    
    try:
        # Update plan status to executing immediately
        try:
            IrrigationPlanService.update_plan_status(
                plan_id=plan_id,
                status="executing",
                result=f"Started at {datetime.utcnow().isoformat()}",
                executed_at=datetime.utcnow()
            )
            logger.info(f"✅ SUCCESS: Plan {plan_id} marked as executing in database")
        except Exception as db_error:
            logger.error(f"❌ FAILED to mark plan {plan_id} as executing: {db_error}")
            # Continue with execution even if status update fails
        
        # Create MQTT client
        client = mqtt.Client()
        
        try:
            # Connect to MQTT broker
            client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            client.loop_start()
            
            # Send irrigation command
            topic = f"irrigation/{device}/command"
            payload = {
                "action": "start_irrigation",
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            result = client.publish(topic, json.dumps(payload))
            
            if result.rc == 0:
                logger.info(f"Successfully sent irrigation command for plan {plan_id}")
                # Update status immediately to ensure completion is recorded
                try:
                    IrrigationPlanService.update_plan_status(
                        plan_id=plan_id,
                        status="completed",
                        result=f"Irrigation executed for {duration}s with device {device}",
                        executed_at=datetime.utcnow()
                    )
                    logger.info(f"✅ SUCCESS: Plan {plan_id} marked as completed in database")
                except Exception as db_error:
                    logger.error(f"❌ FAILED to mark plan {plan_id} as completed: {db_error}")
                    # Still return success for MQTT but log database issue
                return f"Successfully executed irrigation for plan {plan_id}"
            else:
                error_msg = f"Failed to publish MQTT message for plan {plan_id}: {result.rc}"
                logger.error(error_msg)
                # Update status immediately for failed execution
                IrrigationPlanService.update_plan_status(
                    plan_id=plan_id,
                    status="failed",
                    result=error_msg,
                    executed_at=datetime.utcnow()
                )
                logger.info(f"Plan {plan_id} marked as failed in database")
                raise Exception(error_msg)
                
        except Exception as mqtt_error:
            error_msg = f"MQTT error for plan {plan_id}: {str(mqtt_error)}"
            logger.error(error_msg)
            # Update status immediately for MQTT connection errors
            IrrigationPlanService.update_plan_status(
                plan_id=plan_id,
                status="failed",
                result=error_msg,
                executed_at=datetime.utcnow()
            )
            logger.info(f"Plan {plan_id} marked as failed in database due to MQTT error")
            raise Exception(error_msg)
            
        finally:
            client.loop_stop()
            client.disconnect()
            
    except Exception as e:
        logger.error(f"Error executing irrigation {plan_id}: {e}")
        # Update status immediately for general execution errors
        try:
            IrrigationPlanService.update_plan_status(
                plan_id=plan_id,
                status="failed",
                result=f"Execution error: {str(e)}",
                executed_at=datetime.utcnow()
            )
            logger.info(f"Plan {plan_id} marked as failed in database due to execution error")
        except Exception as db_error:
            logger.error(f"Failed to update database status for plan {plan_id}: {db_error}")
        raise self.retry(exc=e)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 2, 'countdown': 30})
def check_due_irrigations(self):
    """
    Periodic task to check database and execute due irrigation plans
    Replaces the APScheduler periodic_irrigation_check function
    """
    try:
        logger.info("Checking for due irrigation plans (Celery)...")
        
        # Get all pending plans from database
        plans = IrrigationPlanService.get_pending_plans()
        
        if not plans:
            logger.debug("No pending irrigation plans found")
            return "No pending plans"
            
        logger.info(f"Found {len(plans)} pending irrigation plans")
        
        current_time = datetime.utcnow()
        executed_count = 0
        
        for plan in plans:
            try:
                scheduled_time = plan.scheduled_time
                plan_id = plan.id
                
                # Check if it's time to execute (within 1 minute window)
                time_diff = (current_time - scheduled_time).total_seconds()
                
                if time_diff >= 0 and time_diff <= 60:  # Execute if due (max 1 min late)
                    logger.info(f"Scheduling due irrigation plan {plan_id}: {plan.description}")
                    
                    # Execute irrigation as separate Celery task
                    execute_irrigation.delay(
                        plan_id=plan_id,
                        device=plan.device or "0x540f57fffe890af8",  # Use proper Zigbee device ID
                        duration=plan.duration,
                        description=plan.description or 'Scheduled irrigation'
                    )
                    
                    executed_count += 1
                    
                elif time_diff > 60:  # More than 1 minute late
                    logger.warning(f"Plan {plan_id} is {time_diff/60:.1f} minutes overdue - skipping")
                    IrrigationPlanService.update_plan_status(
                        plan_id=plan_id,
                        status="failed",
                        result="Execution window missed",
                        executed_at=datetime.utcnow()
                    )
                    logger.info(f"Plan {plan_id} marked as failed (overdue) in database")
                    
                else:
                    # Plan is in the future
                    time_until = -time_diff
                    if time_until < 300:  # Less than 5 minutes away
                        logger.info(f"Plan {plan_id} due in {time_until/60:.1f} minutes")
                        
            except Exception as e:
                logger.error(f"Error processing plan {plan.id}: {e}")
                
        if executed_count > 0:
            logger.info(f"Successfully scheduled {executed_count} irrigation tasks")
            
        return f"Processed {len(plans)} plans, scheduled {executed_count} tasks"
            
    except Exception as e:
        logger.error(f"Error in periodic irrigation check: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 120})
def schedule_irrigation_plan(self, plan_data: dict):
    """
    Schedule a new irrigation plan (called from API)
    Replaces direct APScheduler job creation
    """
    try:
        logger.info(f"Scheduling new irrigation plan: {plan_data}")
        
        # Create plan in database
        plan = IrrigationPlan(**plan_data)
        created_plan = IrrigationPlanService.create_plan(plan)
        
        logger.info(f"Created irrigation plan {created_plan.id} for {created_plan.scheduled_time}")
        
        # Calculate time until execution
        current_time = datetime.utcnow()
        scheduled_time = created_plan.scheduled_time
        delay_seconds = (scheduled_time - current_time).total_seconds()
        
        if delay_seconds > 0:
            # Schedule task to run at the specific time
            execute_irrigation.apply_async(
                args=[
                    created_plan.id,
                    created_plan.device or "0x540f57fffe890af8", 
                    created_plan.duration,
                    created_plan.description or 'Scheduled irrigation'
                ],
                countdown=delay_seconds
            )
            logger.info(f"Scheduled irrigation task to run in {delay_seconds/3600:.2f} hours")
        else:
            # Execute immediately if scheduled time is in the past
            logger.warning(f"Plan {created_plan.id} scheduled in past, executing immediately")
            execute_irrigation.delay(
                created_plan.id,
                created_plan.device or "0x540f57fffe890af8",
                created_plan.duration, 
                created_plan.description or 'Scheduled irrigation'
            )
        
        return {
            "success": True,
            "plan_id": created_plan.id,
            "scheduled_for": created_plan.scheduled_time.isoformat(),
            "delay_seconds": max(0, delay_seconds)
        }
        
    except Exception as e:
        logger.error(f"Error scheduling irrigation plan: {e}")
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