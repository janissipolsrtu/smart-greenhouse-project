"""Database models for irrigation system"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Date, Float, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime, date
from database import Base
import uuid


class WateringPlan(Base):
    """Database model for watering plans (container for zero or many cycles)"""
    __tablename__ = "watering_plans"

    id = Column(String, primary_key=True, default=lambda: f"plan_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}")
    name = Column(String(120), nullable=False, index=True)
    description = Column(Text, nullable=True)
    greenhouse_config_id = Column(Integer, ForeignKey("greenhouse_config.id", ondelete="SET NULL"), nullable=True, index=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    active = Column(Boolean, default=True, nullable=False, index=True)

    def __repr__(self):
        return f"<WateringPlan(id='{self.id}', name='{self.name}', active='{self.active}')>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "greenhouse_config_id": self.greenhouse_config_id,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "active": self.active,
        }

class WateringCycle(Base):
    """Database model for watering cycles"""
    __tablename__ = "watering_cycle"
    
    id = Column(String, primary_key=True, default=lambda: f"cycle_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}")
    scheduled_time = Column(DateTime, nullable=False, index=True)  # Naive UTC datetime
    duration = Column(Integer, nullable=False)  # Duration in seconds
    description = Column(Text, nullable=True)
    device = Column(String, default="0x540f57fffe890af8", nullable=False)  # Correct Zigbee device ID
    created_at = Column(DateTime, server_default=func.now(), nullable=False)  # Naive UTC datetime
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())  # Naive UTC datetime
    status = Column(String, default="pending", nullable=False, index=True)  # pending, executing, completed, failed, cancelled
    executed_at = Column(DateTime, nullable=True)  # Naive UTC datetime
    result = Column(Text, nullable=True)
    plan_id = Column(String, ForeignKey("watering_plans.id", ondelete="SET NULL"), nullable=True, index=True)
    greenhouse_config_id = Column(Integer, ForeignKey("greenhouse_config.id", ondelete="SET NULL"), nullable=True, index=True)
    
    def __repr__(self):
        return f"<WateringCycle(id='{self.id}', scheduled_time='{self.scheduled_time}', status='{self.status}')>"
    
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
            "result": self.result,
            "plan_id": self.plan_id,
            "greenhouse_config_id": self.greenhouse_config_id,
        }


class GreenhouseConfig(Base):
    """Minimal mapping for greenhouse_config table to satisfy FK resolution."""
    __tablename__ = "greenhouse_config"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=True)


class Greenhouse(Base):
    """Database model for greenhouse metadata; MQTT auth lives in greenhouse_config."""
    __tablename__ = "greenhouses"

    id = Column(String, primary_key=True, default=lambda: f"greenhouse_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}")
    name = Column(String(120), nullable=False, index=True)
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Greenhouse(id='{self.id}', name='{self.name}')>"

    def to_dict(self, include_sensitive: bool = False):
        mqtt_broker = getattr(self, "mqtt_broker", None)
        mqtt_port = getattr(self, "mqtt_port", 1883)
        mqtt_username = getattr(self, "mqtt_username", None)
        mqtt_password = getattr(self, "mqtt_password", None)

        payload = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "location": self.location,
            "mqtt_broker": mqtt_broker,
            "mqtt_port": mqtt_port,
            "mqtt_username": mqtt_username,
            "has_mqtt_password": bool(mqtt_password),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_sensitive:
            payload["mqtt_password"] = mqtt_password
        return payload


class Season(Base):
    """Database model for greenhouse seasons."""
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    greenhouse_id = Column(String, ForeignKey("greenhouses.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "greenhouse_id": self.greenhouse_id,
            "name": self.name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
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
    greenhouse_id = Column(String, ForeignKey("greenhouses.id", ondelete="SET NULL"), nullable=True, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id", ondelete="SET NULL"), nullable=True, index=True)
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
            "greenhouse_id": self.greenhouse_id,
            "season_id": self.season_id,
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