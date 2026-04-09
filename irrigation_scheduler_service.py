#!/usr/bin/env python3
"""
Decoupled Irrigation Scheduler Service with PostgreSQL
Uses APScheduler for robust job scheduling independent of API
"""

import json
import logging
import time
import os
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import paho.mqtt.client as mqtt
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# Database imports
from database import init_database, test_database_connection
from irrigation_db_service import IrrigationPlanService
from models import IrrigationPlan

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
MQTT_BROKER = "192.168.8.151"
MQTT_PORT = 1883
DB_URL = os.getenv("DATABASE_URL", "postgresql://irrigation_user:irrigation_pass@postgres:5432/irrigation_db")

# Global MQTT client for job execution
mqtt_client = None
mqtt_connected = False

def initialize_mqtt():
    """Initialize global MQTT client"""
    global mqtt_client, mqtt_connected
    
    try:
        mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        mqtt_connected = True
        logger.info("Global MQTT client initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize global MQTT client: {e}")
        mqtt_connected = False
        return False

def update_plan_status(plan_id: str, status: str, result: str = None):
    """Update the status of an irrigation plan (global function for APScheduler)"""
    try:
        IrrigationPlanService.update_plan_status(
            plan_id=plan_id,
            status=status,
            result=result,
            executed_at=datetime.now(timezone.utc) if status in ['executing', 'completed', 'failed'] else None
        )
        logger.info(f"Updated plan {plan_id} status to: {status}")
    except Exception as e:
        logger.error(f"Error updating plan status: {e}")

def execute_irrigation(plan_id: str, device: str, duration: int, description: str):
    """Execute irrigation via MQTT timer service (global function for APScheduler)"""
    global mqtt_client, mqtt_connected
    
    logger.info(f"Executing irrigation {plan_id}: {duration}s - {description}")
    
    # Update plan status to executing
    update_plan_status(plan_id, "executing", f"Started at {datetime.now().isoformat()}")
    
    try:
        # Send MQTT command to timer service
        schedule_request = {
            "device": device,
            "duration": duration,
            "action": "schedule",
            "requested_by": "scheduler_service",
            "plan_id": plan_id,
            "timestamp": datetime.now().isoformat()
        }
        
        if mqtt_connected and mqtt_client:
            result = mqtt_client.publish("irrigation/schedule/request", json.dumps(schedule_request))
            if result.rc == 0:
                logger.info(f"Successfully sent irrigation command for plan {plan_id}")
                update_plan_status(plan_id, "completed", f"Irrigation executed successfully for {duration}s")
            else:
                logger.error(f"Failed to publish MQTT message for plan {plan_id}")
                update_plan_status(plan_id, "failed", "Failed to send MQTT command")
        else:
            logger.error(f"MQTT not connected - cannot execute plan {plan_id}")
            update_plan_status(plan_id, "failed", "MQTT connection not available")
            
    except Exception as e:
        logger.error(f"Error executing irrigation {plan_id}: {e}")
        update_plan_status(plan_id, "failed", f"Execution error: {e}")

def periodic_irrigation_check():
    """Periodic function to check database and execute due irrigation plans"""
    try:
        logger.info("Checking for due irrigation plans...")
        
        # Get all pending plans from database
        plans = IrrigationPlanService.get_pending_plans()
        
        if not plans:
            logger.debug("No pending irrigation plans found")
            return
            
        logger.info(f"Found {len(plans)} pending irrigation plans")
        
        current_time = datetime.now(timezone.utc)
        executed_count = 0
        
        for plan in plans:
            try:
                scheduled_time = plan.scheduled_time
                plan_id = plan.id
                
                # Check if it's time to execute (within 1 minute window)
                time_diff = (current_time - scheduled_time).total_seconds()
                
                if time_diff >= 0 and time_diff <= 60:  # Execute if due (max 1 min late)
                    logger.info(f"Executing due irrigation plan {plan_id}: {plan.description}")
                    
                    # Execute irrigation directly
                    execute_irrigation(
                        plan_id=plan_id,
                        device=plan.device or "0x540f57fffe890af8",
                        duration=plan.duration,
                        description=plan.description or 'Scheduled irrigation'
                    )
                    
                    executed_count += 1
                    
                elif time_diff > 60:  # More than 1 minute late
                    logger.warning(f"Plan {plan_id} is {time_diff/60:.1f} minutes overdue - skipping")
                    update_plan_status(plan_id, "failed", "Execution window missed")
                    
                else:
                    # Plan is in the future
                    time_until = -time_diff
                    if time_until < 300:  # Less than 5 minutes away
                        logger.info(f"Plan {plan_id} due in {time_until/60:.1f} minutes")
                        
            except Exception as e:
                logger.error(f"Error processing plan {plan.id}: {e}")
                
        if executed_count > 0:
            logger.info(f"Successfully executed {executed_count} irrigation plans")
            
    except Exception as e:
        logger.error(f"Error in periodic irrigation check: {e}")

class IrrigationSchedulerService:
    """Independent scheduler service for irrigation automation with PostgreSQL"""
    
    def __init__(self):
        # Simple APScheduler configuration - just for periodic polling
        jobstores = {
            'default': SQLAlchemyJobStore(url=DB_URL)
        }
        executors = {
            'default': ThreadPoolExecutor(5)  # Smaller pool for simple periodic tasks
        }
        job_defaults = {
            'coalesce': True,    # Merge overlapping executions
            'max_instances': 1   # Only one check at a time
        }
        
        # Initialize scheduler
        self.scheduler = BlockingScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        # Add scheduler event listeners
        self.scheduler.add_listener(self.job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.mqtt_connected = True
            logger.info("Connected to MQTT broker successfully")
        else:
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            
    def on_mqtt_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.mqtt_connected = False
        logger.warning("Disconnected from MQTT broker")
        
    def connect_mqtt(self):
        """Establish MQTT connection"""
        try:
            logger.info(f"Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            for i in range(10):
                time.sleep(0.5)
                if self.mqtt_connected:
                    return True
            
            logger.warning("MQTT connection timeout")
            return False
            
        except Exception as e:
            logger.error(f"Error connecting to MQTT: {e}")
            return False
            
    def execute_irrigation(self, plan_id: str, device: str, duration: int, description: str):
        """Execute irrigation via MQTT timer service"""
        logger.info(f"Executing irrigation {plan_id}: {duration}s - {description}")
        
        # Update plan status to executing
        self.update_plan_status(plan_id, "executing", f"Started at {datetime.now().isoformat()}")
        
        try:
            # Send MQTT command to timer service
            schedule_request = {
                "device": device,
                "duration": duration,
                "action": "schedule",
                "requested_by": "scheduler_service",
                "plan_id": plan_id,
                "timestamp": datetime.now().isoformat()
            }
            
            if self.mqtt_connected:
                result = self.mqtt_client.publish("irrigation/schedule/request", json.dumps(schedule_request))
                if result.rc == 0:
                    logger.info(f"Successfully sent irrigation command for plan {plan_id}")
                    self.update_plan_status(plan_id, "completed", f"Irrigation executed successfully for {duration}s")
                else:
                    logger.error(f"Failed to publish MQTT message for plan {plan_id}")
                    self.update_plan_status(plan_id, "failed", "Failed to send MQTT command")
            else:
                logger.error(f"MQTT not connected - cannot execute plan {plan_id}")
                self.update_plan_status(plan_id, "failed", "MQTT connection not available")
                
        except Exception as e:
            logger.error(f"Error executing irrigation {plan_id}: {e}")
            self.update_plan_status(plan_id, "failed", f"Execution error: {str(e)}")
            
    def update_plan_status(self, plan_id: str, status: str, result: str):
        """Update irrigation plan status in JSON file"""
        try:
            if not os.path.exists(PLANS_FILE):
                return
                
            with open(PLANS_FILE, 'r') as f:
                plans = json.load(f)
            
            # Find and update the specific plan
            for plan in plans:
                if plan.get('id') == plan_id:
                    plan['status'] = status
                    plan['result'] = result
                    if status in ['executing', 'completed', 'failed']:
                        plan['executed_at'] = datetime.now().isoformat()
                    break
            
            # Save updated plans
            with open(PLANS_FILE, 'w') as f:
                json.dump(plans, f, indent=2)
                
            logger.info(f"Updated plan {plan_id} status to: {status}")
            
        except Exception as e:
            logger.error(f"Error updating plan status: {e}")
            
    def load_and_schedule_plans(self):
        """Set up periodic irrigation checking - simpler approach"""
        try:
            logger.info("Setting up periodic irrigation plan checking...")
            
            # Add single periodic job to check database every 30 seconds
            self.scheduler.add_job(
                func=periodic_irrigation_check,
                trigger='interval',
                seconds=30,  # Check every 30 seconds for due plans
                id='irrigation_checker',
                name='Check Due Irrigation Plans',
                replace_existing=True
            )
            
            logger.info("Periodic irrigation checker configured (every 30 seconds)")
            
        except Exception as e:
            logger.error(f"Error setting up periodic irrigation checking: {e}")
            
        # Start the scheduler
        self.scheduler.start()
        
    def job_listener(self, event):
        """Listen to job execution events"""
        if event.exception:
            logger.error(f"Job {event.job_id} crashed: {event.exception}")
        else:
            logger.info(f"Job {event.job_id} executed successfully")
            
    def cleanup_old_jobs(self):
        """Remove completed jobs older than 24 hours"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=24)
            
            for job in self.scheduler.get_jobs():
                # Remove jobs scheduled in the past
                if hasattr(job.trigger, 'run_date') and job.trigger.run_date < cutoff_time:
                    self.scheduler.remove_job(job.id)
                    logger.info(f"Removed old job: {job.id}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {e}")
            
    def start(self):
        """Start the irrigation scheduler service"""
        logger.info("Starting Simple Irrigation Scheduler with Database Polling")
        
        # Initialize database
        if not test_database_connection():
            logger.error("Failed to connect to database")
            return False
        
        if not init_database():
            logger.error("Failed to initialize database")
            return False
            
        logger.info("Database connection established")
        
        # Initialize MQTT
        if not initialize_mqtt():
            logger.error("Failed to initialize MQTT client")
            return False
        
        # Set up periodic checking (this starts the scheduler)
        self.load_and_schedule_plans()
        
        # Add job listener
        self.scheduler.add_listener(self.job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        logger.info("Irrigation scheduler started - checking database every 30 seconds...")
        return True

if __name__ == "__main__":
    service = IrrigationSchedulerService()
    service.start()