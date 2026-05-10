"""Database service for watering cycle operations"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from datetime import datetime, timezone
from typing import List, Optional
import logging

from models import WateringCycle
from database import SessionLocal

logger = logging.getLogger(__name__)

class WateringCycleService:
    """Service class for watering cycle database operations"""
    
    @staticmethod
    def create_cycle(
        scheduled_time: datetime,
        duration: int,
        description: str = None,
        device: str = "0x540f57fffe890af8"  # Correct Zigbee device ID
    ) -> WateringCycle:
        """Create a new watering cycle"""
        db = SessionLocal()
        try:
            cycle = WateringCycle(
                scheduled_time=scheduled_time,
                duration=duration,
                description=description,
                device=device
            )
            db.add(cycle)
            db.commit()
            db.refresh(cycle)
            logger.info(f"Created watering cycle: {cycle.id}")
            return cycle
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating watering cycle: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def get_cycle(cycle_id: str) -> Optional[WateringCycle]:
        """Get watering cycle by ID"""
        db = SessionLocal()
        try:
            cycle = db.query(WateringCycle).filter(WateringCycle.id == cycle_id).first()
            return cycle
        finally:
            db.close()
    
    @staticmethod
    def get_all_cycles(status: str = None, limit: int = 100) -> List[WateringCycle]:
        """Get all watering cycles, optionally filtered by status"""
        db = SessionLocal()
        try:
            query = db.query(WateringCycle)
            if status:
                query = query.filter(WateringCycle.status == status)
            cycles = query.order_by(desc(WateringCycle.scheduled_time)).limit(limit).all()
            return cycles
        finally:
            db.close()
    
    @staticmethod
    def get_pending_cycles() -> List[WateringCycle]:
        """Get all pending watering cycles (including overdue ones)"""
        db = SessionLocal()
        try:
            # Don't filter by time - let the scheduler handle grace period logic
            cycles = db.query(WateringCycle).filter(
                WateringCycle.status == "pending"
            ).order_by(asc(WateringCycle.scheduled_time)).all()
            return cycles
        finally:
            db.close()
    
    @staticmethod
    def update_cycle_status(
        cycle_id: str, 
        status: str, 
        result: str = None,
        executed_at: datetime = None
    ) -> bool:
        """Update watering cycle status"""
        db = SessionLocal()
        try:
            cycle = db.query(WateringCycle).filter(WateringCycle.id == cycle_id).first()
            if not cycle:
                logger.warning(f"Cycle not found: {cycle_id}")
                return False
                
            cycle.status = status
            if result:
                cycle.result = result
            if executed_at:
                cycle.executed_at = executed_at
            elif status in ['executing', 'completed', 'failed']:
                cycle.executed_at = datetime.now(timezone.utc)
                
            db.commit()
            logger.info(f"Updated cycle {cycle_id} status to: {status}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating cycle status: {e}")
            return False
        finally:
            db.close()
    
    @staticmethod
    def delete_cycle(cycle_id: str) -> bool:
        """Delete watering cycle"""
        db = SessionLocal()
        try:
            cycle = db.query(WateringCycle).filter(WateringCycle.id == cycle_id).first()
            if not cycle:
                return False
                
            db.delete(cycle)
            db.commit()
            logger.info(f"Deleted watering cycle: {cycle_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting cycle: {e}")
            return False
        finally:
            db.close()
    
    @staticmethod
    def get_cycle_count_by_status() -> dict:
        """Get count of cycles by status"""
        db = SessionLocal()
        try:
            from sqlalchemy import func
            counts = db.query(
                WateringCycle.status,
                func.count(WateringCycle.id).label('count')
            ).group_by(WateringCycle.status).all()
            
            return {status: count for status, count in counts}
        finally:
            db.close()