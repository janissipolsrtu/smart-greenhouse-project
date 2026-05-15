#!/usr/bin/env python3
"""
Celery Tasks for Irrigation System
Replaces APScheduler job execution with distributed task queue
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo
import paho.mqtt.client as mqtt
from celery import shared_task
from celery.exceptions import Retry, WorkerLostError
from sqlalchemy import text

# Database imports
from database import init_database
from database import SessionLocal
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

APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Europe/Riga")

# Emit explicit timezone configuration once on worker import/startup.
logger.info(
    "Celery timezone config: APP_TIMEZONE=%s, celery.timezone=%s, celery.enable_utc=%s",
    APP_TIMEZONE,
    celery_app.conf.timezone,
    celery_app.conf.enable_utc,
)


def local_now_naive() -> datetime:
    """Return current time as naive datetime in configured app timezone."""
    try:
        return datetime.now(ZoneInfo(APP_TIMEZONE)).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def resolve_cycle_greenhouse_config_id(
    cycle_id: str,
    current_greenhouse_config_id: Optional[int] = None,
) -> Optional[int]:
    """Resolve greenhouse_config_id from cycle row or linked plan, then backfill cycle when missing."""
    if current_greenhouse_config_id:
        return current_greenhouse_config_id

    db = SessionLocal()
    try:
        row = db.execute(
            text(
                """
                SELECT
                    wc.greenhouse_config_id AS cycle_greenhouse_config_id,
                    wp.greenhouse_config_id AS plan_greenhouse_config_id
                FROM watering_cycle wc
                LEFT JOIN watering_plans wp ON wc.plan_id = wp.id
                WHERE wc.id = :cycle_id
                LIMIT 1
                """
            ),
            {"cycle_id": cycle_id},
        ).mappings().first()

        if not row:
            return None

        resolved_id = row.get("cycle_greenhouse_config_id") or row.get("plan_greenhouse_config_id")

        if resolved_id and not row.get("cycle_greenhouse_config_id"):
            db.execute(
                text(
                    """
                    UPDATE watering_cycle
                    SET greenhouse_config_id = :greenhouse_config_id
                    WHERE id = :cycle_id
                    """
                ),
                {"greenhouse_config_id": resolved_id, "cycle_id": cycle_id},
            )
            db.commit()

        return resolved_id
    except Exception as e:
        logger.warning(f"Failed to resolve greenhouse_config_id for cycle {cycle_id}: {e}")
        return None
    finally:
        db.close()

def resolve_mqtt_settings(greenhouse_config_id: Optional[int]) -> Dict[str, Any]:
    """Resolve MQTT connection settings from greenhouse_config with safe fallbacks."""
    default_settings: Dict[str, Any] = {
        "broker": MQTT_BROKER,
        "port": MQTT_PORT,
        "username": "",
        "password": "",
    }

    db = SessionLocal()
    try:
        if greenhouse_config_id:
            row = db.execute(
                text(
                    """
                    SELECT
                        COALESCE(controller_ip::text, '') AS mqtt_broker,
                        COALESCE(controller_username, '') AS mqtt_username,
                        COALESCE(controller_password, '') AS mqtt_password
                    FROM greenhouse_config
                    WHERE id = :greenhouse_config_id
                    LIMIT 1
                    """
                ),
                {"greenhouse_config_id": greenhouse_config_id},
            ).mappings().first()
        else:
            row = db.execute(
                text(
                    """
                    SELECT
                        COALESCE(controller_ip::text, '') AS mqtt_broker,
                        COALESCE(controller_username, '') AS mqtt_username,
                        COALESCE(controller_password, '') AS mqtt_password
                    FROM greenhouse_config
                    ORDER BY selected DESC, id DESC
                    LIMIT 1
                    """
                )
            ).mappings().first()

        if not row:
            return default_settings

        broker_raw = (row.get("mqtt_broker") or "").strip()
        broker = (broker_raw.split("/", 1)[0] if broker_raw else "") or default_settings["broker"]
        username = (row.get("mqtt_username") or "").strip()
        password = row.get("mqtt_password") or ""

        password_looks_hashed = (
            isinstance(password, str)
            and ':' in password
            and len(password.split(':', 1)[0]) >= 16
            and len(password.split(':', 1)[1]) >= 32
        )
        if password_looks_hashed:
            logger.warning(
                "greenhouse_config password appears hashed; falling back to env/default MQTT password"
            )
            password = ""

        return {
            "broker": broker,
            "port": MQTT_PORT,
            "username": username,
            "password": password or os.getenv("MQTT_PASSWORD", ""),
        }
    except Exception as e:
        logger.warning(f"Falling back to default MQTT settings: {e}")
        return default_settings
    finally:
        db.close()

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def update_cycle_status(self, cycle_id: str, status: str, result: str = None):
    """Update the status of a watering cycle (Celery task)"""
    try:
        WateringCycleService.update_cycle_status(
            cycle_id=cycle_id,
            status=status,
            result=result,
            executed_at=local_now_naive() if status in ['executing', 'completed', 'failed'] else None
        )
        logger.info(f"Updated cycle {cycle_id} status to: {status}")
        return f"Successfully updated cycle {cycle_id} status to {status}"
    except Exception as e:
        logger.error(f"Error updating cycle status: {e}")
        raise self.retry(exc=e)

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def execute_irrigation(
    self,
    cycle_id: str,
    device: str,
    duration: int,
    description: str,
    greenhouse_config_id: Optional[int] = None,
):
    """Execute watering using MQTT"""
    logger.info(f"Executing watering cycle {cycle_id}: {duration}s - {description}")
    
    try:
        # Update cycle status to executing immediately
        try:
            WateringCycleService.update_cycle_status(
                cycle_id=cycle_id,
                status="executing",
                result=f"Started at {local_now_naive().isoformat()}",
                executed_at=local_now_naive()
            )
            logger.info(f"✅ SUCCESS: Cycle {cycle_id} marked as executing in database")
        except Exception as db_error:
            logger.error(f"❌ FAILED to mark cycle {cycle_id} as executing: {db_error}")
            # Continue with execution even if status update fails
        
        greenhouse_config_id = resolve_cycle_greenhouse_config_id(cycle_id, greenhouse_config_id)

        mqtt_settings = resolve_mqtt_settings(greenhouse_config_id)

        # Create MQTT client
        client = mqtt.Client()
        
        try:
            if mqtt_settings["username"]:
                client.username_pw_set(
                    mqtt_settings["username"],
                    mqtt_settings["password"] or None,
                )

            logger.info(
                "MQTT connect target for cycle %s: broker=%s:%s, greenhouse_config_id=%s, auth_user=%s",
                cycle_id,
                mqtt_settings["broker"],
                mqtt_settings["port"],
                greenhouse_config_id,
                mqtt_settings["username"] or "<none>",
            )

            # Connect to MQTT broker
            client.connect(mqtt_settings["broker"], mqtt_settings["port"], MQTT_KEEPALIVE)
            client.loop_start()
            
            # Send Zigbee2MQTT command directly, equivalent to:
            # mosquitto_pub -h <broker> -u <username> -P <password> -t zigbee2mqtt/<device>/set -m '{"state":"ON"}'
            topic = f"zigbee2mqtt/{device}/set"
            payload = {"state": "ON"}
            mosquitto_command = (
                f"mosquitto_pub -h {mqtt_settings['broker']} "
                f"-u {mqtt_settings['username'] or '<none>'} "
                f"-P <redacted> -t {topic} -m '{json.dumps(payload)}'"
            )

            logger.info(
                "Publishing MQTT command for cycle %s: broker=%s topic=%s payload=%s",
                cycle_id,
                mqtt_settings["broker"],
                topic,
                json.dumps(payload),
            )
            logger.info("Equivalent MQTT command for cycle %s: %s", cycle_id, mosquitto_command)

            result = client.publish(topic, json.dumps(payload), qos=0)
            
            if result.rc == 0:
                logger.info(f"Successfully sent watering command for cycle {cycle_id}")

                off_delay_seconds = max(1, int(duration))
                turn_off_irrigation.apply_async(
                    kwargs={
                        "cycle_id": cycle_id,
                        "device": device,
                        "greenhouse_config_id": greenhouse_config_id,
                    },
                    countdown=off_delay_seconds,
                    queue="irrigation_execution",
                )
                logger.info(
                    "Scheduled OFF command for cycle %s in %ss",
                    cycle_id,
                    off_delay_seconds,
                )

                # Update status immediately to ensure completion is recorded
                try:
                    WateringCycleService.update_cycle_status(
                        cycle_id=cycle_id,
                        status="completed",
                        result=f"Watering executed for {duration}s with device {device}",
                        executed_at=local_now_naive()
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
                    executed_at=local_now_naive()
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
                executed_at=local_now_naive()
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
                executed_at=local_now_naive()
            )
            logger.info(f"Cycle {cycle_id} marked as failed in database due to execution error")
        except Exception as db_error:
            logger.error(f"Failed to update database status for cycle {cycle_id}: {db_error}")
        raise self.retry(exc=e)


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 30})
def turn_off_irrigation(
    self,
    cycle_id: str,
    device: str,
    greenhouse_config_id: Optional[int] = None,
):
    """Send OFF command after planned watering duration expires."""
    greenhouse_config_id = resolve_cycle_greenhouse_config_id(cycle_id, greenhouse_config_id)
    mqtt_settings = resolve_mqtt_settings(greenhouse_config_id)

    client = mqtt.Client()

    try:
        if mqtt_settings["username"]:
            client.username_pw_set(
                mqtt_settings["username"],
                mqtt_settings["password"] or None,
            )

        topic = f"zigbee2mqtt/{device}/set"
        payload = {"state": "OFF"}
        mosquitto_command = (
            f"mosquitto_pub -h {mqtt_settings['broker']} "
            f"-u {mqtt_settings['username'] or '<none>'} "
            f"-P <redacted> -t {topic} -m '{json.dumps(payload)}'"
        )

        logger.info(
            "MQTT connect target for OFF command cycle %s: broker=%s:%s, greenhouse_config_id=%s, auth_user=%s",
            cycle_id,
            mqtt_settings["broker"],
            mqtt_settings["port"],
            greenhouse_config_id,
            mqtt_settings["username"] or "<none>",
        )
        client.connect(mqtt_settings["broker"], mqtt_settings["port"], MQTT_KEEPALIVE)
        client.loop_start()

        logger.info(
            "Publishing MQTT OFF command for cycle %s: broker=%s topic=%s payload=%s",
            cycle_id,
            mqtt_settings["broker"],
            topic,
            json.dumps(payload),
        )
        logger.info("Equivalent MQTT OFF command for cycle %s: %s", cycle_id, mosquitto_command)

        result = client.publish(topic, json.dumps(payload), qos=0)
        if result.rc != 0:
            raise Exception(f"Failed to publish OFF MQTT message for cycle {cycle_id}: {result.rc}")

        logger.info(f"Successfully sent OFF command for cycle {cycle_id}")
        return f"OFF command sent for cycle {cycle_id}"
    except Exception as e:
        logger.error(f"Error sending OFF command for cycle {cycle_id}: {e}")
        raise self.retry(exc=e)
    finally:
        client.loop_stop()
        client.disconnect()

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
        
        current_time = local_now_naive()
        executed_count = 0
        
        for cycle in cycles:
            try:
                scheduled_time = cycle.scheduled_time
                cycle_id = cycle.id
                resolved_greenhouse_config_id = resolve_cycle_greenhouse_config_id(
                    cycle_id,
                    getattr(cycle, 'greenhouse_config_id', None),
                )
                
                # Check if it's time to execute (within 1 minute window)
                time_diff = (current_time - scheduled_time).total_seconds()
                
                if time_diff >= 0 and time_diff <= 60:  # Execute if due (max 1 min late)
                    logger.info(f"Scheduling due watering cycle {cycle_id}: {cycle.description}")
                    
                    # Execute watering as separate Celery task
                    execute_irrigation.delay(
                        cycle_id=cycle_id,
                        device=cycle.device or "0x540f57fffe890af8",  # Use proper Zigbee device ID
                        duration=cycle.duration,
                        description=cycle.description or 'Scheduled watering',
                        greenhouse_config_id=resolved_greenhouse_config_id,
                    )
                    
                    executed_count += 1
                    
                elif time_diff > 60:  # More than 1 minute late
                    logger.warning(f"Cycle {cycle_id} is {time_diff/60:.1f} minutes overdue - skipping")
                    WateringCycleService.update_cycle_status(
                        cycle_id=cycle_id,
                        status="failed",
                        result="Execution window missed",
                        executed_at=local_now_naive()
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
        current_time = local_now_naive()
        scheduled_time = created_cycle.scheduled_time
        delay_seconds = (scheduled_time - current_time).total_seconds()
        
        if delay_seconds > 0:
            # Schedule task to run at the specific time
            execute_irrigation.apply_async(
                args=[
                    created_cycle.id,
                    created_cycle.device or "0x540f57fffe890af8", 
                    created_cycle.duration,
                    created_cycle.description or 'Scheduled watering',
                    created_cycle.greenhouse_config_id,
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
                created_cycle.description or 'Scheduled watering',
                created_cycle.greenhouse_config_id,
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
