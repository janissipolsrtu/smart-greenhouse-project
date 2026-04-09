"""Database models for irrigation system"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from datetime import datetime
from database import Base
import uuid

class IrrigationPlan(Base):
    """Database model for irrigation plans"""
    __tablename__ = "irrigation_plans"
    
    id = Column(String, primary_key=True, default=lambda: f"plan_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}")
    scheduled_time = Column(DateTime, nullable=False, index=True)  # Naive UTC datetime
    duration = Column(Integer, nullable=False)  # Duration in seconds
    description = Column(Text, nullable=True)
    device = Column(String, default="0x540f57fffe890af8", nullable=False)  # Correct Zigbee device ID
    created_at = Column(DateTime, server_default=func.now(), nullable=False)  # Naive UTC datetime
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())  # Naive UTC datetime
    status = Column(String, default="pending", nullable=False, index=True)  # pending, executing, completed, failed, cancelled
    executed_at = Column(DateTime, nullable=True)  # Naive UTC datetime
    result = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<IrrigationPlan(id='{self.id}', scheduled_time='{self.scheduled_time}', status='{self.status}')>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "scheduled_time": self.scheduled_time.isoformat() if self.scheduled_time else None,
            "duration": self.duration,
            "description": self.description,
            "device": self.device,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "result": self.result
        }