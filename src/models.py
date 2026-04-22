"""Database models for irrigation system"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Date, Float
from sqlalchemy.sql import func
from datetime import datetime, date
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


class Plant(Base):
    """Database model for plant registration and management"""
    __tablename__ = "plants"
    
    id = Column(String, primary_key=True, default=lambda: f"plant_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}")
    name = Column(String(100), nullable=False, index=True)  # Plant name or variety (FR-11)
    variety = Column(String(100), nullable=True)  # Specific variety if different from name
    planting_date = Column(Date, nullable=False, index=True)  # Planting date (FR-12)
    watering_frequency = Column(Integer, nullable=False, default=1)  # Times per day (FR-13)
    watering_duration = Column(Integer, nullable=False, default=300)  # Seconds per watering (FR-13)
    water_amount_ml = Column(Integer, nullable=True)  # Milliliters per watering (FR-13)
    harvest_date_estimate = Column(Date, nullable=True)  # Expected harvest date (FR-14)
    harvest_quantity_estimate = Column(Float, nullable=True)  # Expected quantity in kg (FR-14)
    location_row = Column(Integer, nullable=False)  # Greenhouse row number (FR-15)
    location_column = Column(Integer, nullable=False)  # Greenhouse column number (FR-15)
    location_description = Column(String(200), nullable=True)  # Additional location info (FR-15)
    notes = Column(Text, nullable=True)  # General notes about the plant
    active = Column(Boolean, default=True, nullable=False, index=True)  # Whether plant is still active
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<Plant(id='{self.id}', name='{self.name}', location='R{self.location_row}C{self.location_column}')>"
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "variety": self.variety,
            "planting_date": self.planting_date.isoformat() if self.planting_date else None,
            "watering_frequency": self.watering_frequency,
            "watering_duration": self.watering_duration,
            "water_amount_ml": self.water_amount_ml,
            "harvest_date_estimate": self.harvest_date_estimate.isoformat() if self.harvest_date_estimate else None,
            "harvest_quantity_estimate": self.harvest_quantity_estimate,
            "location_row": self.location_row,
            "location_column": self.location_column,
            "location_description": self.location_description,
            "notes": self.notes,
            "active": self.active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def location_coordinate(self):
        """Get location as coordinate string (e.g., 'R1C3')"""
        return f"R{self.location_row}C{self.location_column}"
    
    @property
    def days_since_planting(self):
        """Calculate days since planting"""
        if self.planting_date:
            return (date.today() - self.planting_date).days
        return 0
    
    @property
    def days_to_harvest(self):
        """Calculate days until harvest"""
        if self.harvest_date_estimate:
            return (self.harvest_date_estimate - date.today()).days
        return None