"""Database service for irrigation plan operations"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc
from datetime import datetime, timezone
from typing import List, Optional
import logging

from models import IrrigationPlan
from database import SessionLocal

logger = logging.getLogger(__name__)

class IrrigationPlanService:
    """Service class for irrigation plan database operations"""
    
    @staticmethod
    def create_plan(
        scheduled_time: datetime,
        duration: int,
        description: str = None,
        device: str = "0x540f57fffe890af8"  # Correct Zigbee device ID
    ) -> IrrigationPlan:
        """Create a new irrigation plan"""
        db = SessionLocal()
        try:
            plan = IrrigationPlan(
                scheduled_time=scheduled_time,
                duration=duration,
                description=description,
                device=device
            )
            db.add(plan)
            db.commit()
            db.refresh(plan)
            logger.info(f"Created irrigation plan: {plan.id}")
            return plan
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating irrigation plan: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def get_plan(plan_id: str) -> Optional[IrrigationPlan]:
        """Get irrigation plan by ID"""
        db = SessionLocal()
        try:
            plan = db.query(IrrigationPlan).filter(IrrigationPlan.id == plan_id).first()
            return plan
        finally:
            db.close()
    
    @staticmethod
    def get_all_plans(status: str = None, limit: int = 100) -> List[IrrigationPlan]:
        """Get all irrigation plans, optionally filtered by status"""
        db = SessionLocal()
        try:
            query = db.query(IrrigationPlan)
            if status:
                query = query.filter(IrrigationPlan.status == status)
            plans = query.order_by(desc(IrrigationPlan.scheduled_time)).limit(limit).all()
            return plans
        finally:
            db.close()
    
    @staticmethod
    def get_pending_plans() -> List[IrrigationPlan]:
        """Get all pending irrigation plans (including overdue ones)"""
        db = SessionLocal()
        try:
            # Don't filter by time - let the scheduler handle grace period logic
            plans = db.query(IrrigationPlan).filter(
                IrrigationPlan.status == "pending"
            ).order_by(asc(IrrigationPlan.scheduled_time)).all()
            return plans
        finally:
            db.close()
    
    @staticmethod
    def update_plan_status(
        plan_id: str, 
        status: str, 
        result: str = None,
        executed_at: datetime = None
    ) -> bool:
        """Update irrigation plan status"""
        db = SessionLocal()
        try:
            plan = db.query(IrrigationPlan).filter(IrrigationPlan.id == plan_id).first()
            if not plan:
                logger.warning(f"Plan not found: {plan_id}")
                return False
                
            plan.status = status
            if result:
                plan.result = result
            if executed_at:
                plan.executed_at = executed_at
            elif status in ['executing', 'completed', 'failed']:
                plan.executed_at = datetime.now(timezone.utc)
                
            db.commit()
            logger.info(f"Updated plan {plan_id} status to: {status}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating plan status: {e}")
            return False
        finally:
            db.close()
    
    @staticmethod
    def delete_plan(plan_id: str) -> bool:
        """Delete irrigation plan"""
        db = SessionLocal()
        try:
            plan = db.query(IrrigationPlan).filter(IrrigationPlan.id == plan_id).first()
            if not plan:
                return False
                
            db.delete(plan)
            db.commit()
            logger.info(f"Deleted irrigation plan: {plan_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting plan: {e}")
            return False
        finally:
            db.close()
    
    @staticmethod
    def get_plan_count_by_status() -> dict:
        """Get count of plans by status"""
        db = SessionLocal()
        try:
            from sqlalchemy import func
            counts = db.query(
                IrrigationPlan.status,
                func.count(IrrigationPlan.id).label('count')
            ).group_by(IrrigationPlan.status).all()
            
            return {status: count for status, count in counts}
        finally:
            db.close()