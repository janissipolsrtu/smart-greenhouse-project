"""Database service for plant operations"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, asc, or_
from datetime import datetime, date
from typing import List, Optional, Dict
import logging
import uuid
import time

from models import Plant
from database import SessionLocal

logger = logging.getLogger(__name__)

class PlantService:
    """Service class for plant database operations"""
    
    @staticmethod
    def create_plant(
        name: str,
        planting_date: date,
        location_row: int,
        location_column: int,
        variety: str = None,
        watering_frequency: int = 1,
        watering_duration: int = 300,
        water_amount_ml: int = None,
        harvest_date_estimate: date = None,
        harvest_quantity_estimate: float = None,
        location_description: str = None,
        notes: str = None,
        active: bool = True
    ) -> Plant:
        """Create a new plant registration"""
        db = SessionLocal()
        try:
            # Check if location is already occupied
            existing_plant = db.query(Plant).filter(
                and_(
                    Plant.location_row == location_row,
                    Plant.location_column == location_column,
                    Plant.active == True
                )
            ).first()
            
            if existing_plant:
                raise ValueError(f"Location R{location_row}C{location_column} is already occupied by plant {existing_plant.name}")
            
            # Generate ID
            timestamp = int(time.time())
            unique_id = uuid.uuid4().hex[:8]
            plant_id = f"plant_{timestamp}_{unique_id}"
            
            plant = Plant(
                id=plant_id,
                name=name,
                variety=variety,
                planting_date=planting_date,
                watering_frequency=watering_frequency,
                watering_duration=watering_duration,
                water_amount_ml=water_amount_ml,
                harvest_date_estimate=harvest_date_estimate,
                harvest_quantity_estimate=harvest_quantity_estimate,
                location_row=location_row,
                location_column=location_column,
                location_description=location_description,
                notes=notes,
                active=active
            )
            db.add(plant)
            db.commit()
            db.refresh(plant)
            logger.info(f"Created plant registration: {plant.id} - {plant.name} at R{plant.location_row}C{plant.location_column}")
            return plant
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating plant registration: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def get_plant(plant_id: str) -> Optional[Plant]:
        """Get plant by ID"""
        db = SessionLocal()
        try:
            plant = db.query(Plant).filter(Plant.id == plant_id).first()
            return plant
        except Exception as e:
            logger.error(f"Error getting plant {plant_id}: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def get_all_plants(active_only: bool = False, limit: int = 100, offset: int = 0) -> List[Plant]:
        """Get all plants with pagination"""
        db = SessionLocal()
        try:
            query = db.query(Plant)
            
            if active_only:
                query = query.filter(Plant.active == True)
            
            query = query.order_by(desc(Plant.created_at))
            
            if limit:
                query = query.limit(limit)
            if offset:
                query = query.offset(offset)
                
            plants = query.all()
            return plants
        except Exception as e:
            logger.error(f"Error getting plants: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def get_plants_by_location(row: int = None, column: int = None) -> List[Plant]:
        """Get plants by greenhouse location"""
        db = SessionLocal()
        try:
            query = db.query(Plant).filter(Plant.active == True)
            
            if row is not None:
                query = query.filter(Plant.location_row == row)
            if column is not None:
                query = query.filter(Plant.location_column == column)
                
            plants = query.order_by(Plant.location_row, Plant.location_column).all()
            return plants
        except Exception as e:
            logger.error(f"Error getting plants by location: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def search_plants(
        name: str = None,
        variety: str = None,
        active_only: bool = True
    ) -> List[Plant]:
        """Search plants by name or variety"""
        db = SessionLocal()
        try:
            query = db.query(Plant)
            
            if active_only:
                query = query.filter(Plant.active == True)
            
            if name or variety:
                filters = []
                if name:
                    filters.append(Plant.name.ilike(f"%{name}%"))
                if variety:
                    filters.append(Plant.variety.ilike(f"%{variety}%"))
                query = query.filter(or_(*filters))
            
            plants = query.order_by(desc(Plant.created_at)).all()
            return plants
        except Exception as e:
            logger.error(f"Error searching plants: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def update_plant(plant_id: str, **kwargs) -> Optional[Plant]:
        """Update plant information"""
        db = SessionLocal()
        try:
            plant = db.query(Plant).filter(Plant.id == plant_id).first()
            if not plant:
                return None
                
            # Check location change conflicts
            if 'location_row' in kwargs or 'location_column' in kwargs:
                new_row = kwargs.get('location_row', plant.location_row)
                new_column = kwargs.get('location_column', plant.location_column)
                
                # Only check if location actually changed
                if new_row != plant.location_row or new_column != plant.location_column:
                    existing_plant = db.query(Plant).filter(
                        and_(
                            Plant.location_row == new_row,
                            Plant.location_column == new_column,
                            Plant.active == True,
                            Plant.id != plant_id  # Exclude current plant
                        )
                    ).first()
                    
                    if existing_plant:
                        raise ValueError(f"Location R{new_row}C{new_column} is already occupied by plant {existing_plant.name}")
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(plant, key):
                    setattr(plant, key, value)
            
            db.commit()
            db.refresh(plant)
            logger.info(f"Updated plant: {plant.id}")
            return plant
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating plant {plant_id}: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def delete_plant(plant_id: str) -> bool:
        """Soft delete plant (mark as inactive)"""
        db = SessionLocal()
        try:
            plant = db.query(Plant).filter(Plant.id == plant_id).first()
            if not plant:
                return False
                
            plant.active = False
            db.commit()
            logger.info(f"Soft deleted plant: {plant_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting plant {plant_id}: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def get_greenhouse_layout(max_rows: int = 10, max_columns: int = 10) -> Dict:
        """Get greenhouse layout with plant positions"""
        db = SessionLocal()
        try:
            plants = db.query(Plant).filter(Plant.active == True).all()
            
            layout = {}
            for row in range(1, max_rows + 1):
                layout[row] = {}
                for col in range(1, max_columns + 1):
                    layout[row][col] = None
            
            for plant in plants:
                if plant.location_row <= max_rows and plant.location_column <= max_columns:
                    layout[plant.location_row][plant.location_column] = {
                        'id': plant.id,
                        'name': plant.name,
                        'variety': plant.variety,
                        'planting_date': plant.planting_date.isoformat() if plant.planting_date else None,
                        'days_since_planting': (date.today() - plant.planting_date).days if plant.planting_date else 0
                    }
            
            return layout
        except Exception as e:
            logger.error(f"Error getting greenhouse layout: {e}")
            raise
        finally:
            db.close()
    
    @staticmethod
    def get_plants_ready_for_harvest() -> List[Plant]:
        """Get plants that are ready for harvest"""
        db = SessionLocal()
        try:
            today = date.today()
            plants = db.query(Plant).filter(
                and_(
                    Plant.active == True,
                    Plant.harvest_date_estimate <= today
                )
            ).order_by(Plant.harvest_date_estimate).all()
            return plants
        except Exception as e:
            logger.error(f"Error getting plants ready for harvest: {e}")
            raise
        finally:
            db.close()