"""Database service for greenhouse operations."""
from typing import List, Optional
import logging
import time
import uuid

from database import SessionLocal
from models import Greenhouse

logger = logging.getLogger(__name__)


class GreenhouseService:
    """Service class for greenhouse database operations."""

    @staticmethod
    def create_greenhouse(
        name: str,
        mqtt_username: str,
        mqtt_password: str,
        mqtt_broker: str = "192.168.8.151",
        mqtt_port: int = 1883,
        description: str = None,
        location: str = None,
        active: bool = True,
    ) -> Greenhouse:
        db = SessionLocal()
        try:
            existing = db.query(Greenhouse).filter(Greenhouse.name == name).first()
            if existing:
                raise ValueError(f"Greenhouse with name '{name}' already exists")

            timestamp = int(time.time())
            unique_id = uuid.uuid4().hex[:8]
            greenhouse_id = f"greenhouse_{timestamp}_{unique_id}"

            greenhouse = Greenhouse(
                id=greenhouse_id,
                name=name,
                description=description,
                location=location,
                mqtt_broker=mqtt_broker,
                mqtt_port=mqtt_port,
                mqtt_username=mqtt_username,
                mqtt_password=mqtt_password,
                active=active,
            )
            db.add(greenhouse)
            db.commit()
            db.refresh(greenhouse)
            logger.info(f"Created greenhouse: {greenhouse.id} - {greenhouse.name}")
            return greenhouse
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating greenhouse: {e}")
            raise
        finally:
            db.close()

    @staticmethod
    def get_greenhouse(greenhouse_id: str) -> Optional[Greenhouse]:
        db = SessionLocal()
        try:
            return db.query(Greenhouse).filter(Greenhouse.id == greenhouse_id).first()
        except Exception as e:
            logger.error(f"Error getting greenhouse {greenhouse_id}: {e}")
            raise
        finally:
            db.close()

    @staticmethod
    def get_all_greenhouses(active_only: bool = False) -> List[Greenhouse]:
        db = SessionLocal()
        try:
            query = db.query(Greenhouse)
            if active_only:
                query = query.filter(Greenhouse.active == True)
            return query.order_by(Greenhouse.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting greenhouses: {e}")
            raise
        finally:
            db.close()

    @staticmethod
    def update_greenhouse(greenhouse_id: str, **kwargs) -> Optional[Greenhouse]:
        db = SessionLocal()
        try:
            greenhouse = db.query(Greenhouse).filter(Greenhouse.id == greenhouse_id).first()
            if not greenhouse:
                return None

            if "name" in kwargs and kwargs["name"] and kwargs["name"] != greenhouse.name:
                existing = db.query(Greenhouse).filter(Greenhouse.name == kwargs["name"]).first()
                if existing:
                    raise ValueError(f"Greenhouse with name '{kwargs['name']}' already exists")

            for key, value in kwargs.items():
                if hasattr(greenhouse, key):
                    setattr(greenhouse, key, value)

            db.commit()
            db.refresh(greenhouse)
            logger.info(f"Updated greenhouse: {greenhouse.id}")
            return greenhouse
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating greenhouse {greenhouse_id}: {e}")
            raise
        finally:
            db.close()

    @staticmethod
    def delete_greenhouse(greenhouse_id: str) -> bool:
        db = SessionLocal()
        try:
            greenhouse = db.query(Greenhouse).filter(Greenhouse.id == greenhouse_id).first()
            if not greenhouse:
                return False

            greenhouse.active = False
            db.commit()
            logger.info(f"Soft deleted greenhouse: {greenhouse_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting greenhouse {greenhouse_id}: {e}")
            raise
        finally:
            db.close()
