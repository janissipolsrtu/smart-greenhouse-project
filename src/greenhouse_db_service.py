"""Database service for greenhouse operations."""
from typing import List, Optional
import logging
import time
import uuid
from sqlalchemy import text

from database import SessionLocal
from models import Greenhouse

logger = logging.getLogger(__name__)


class GreenhouseService:
    """Service class for greenhouse database operations."""

    @staticmethod
    def _upsert_greenhouse_config(
        db,
        *,
        greenhouse_id: Optional[str],
        name: str,
        mqtt_broker: Optional[str],
        mqtt_username: Optional[str],
        mqtt_password: Optional[str],
    ):
        db.execute(
            text(
                """
                INSERT INTO greenhouse_config (
                    name, greenhouse_id, season,
                    controller_ip, controller_username, controller_password,
                    feature_plants, feature_layout, feature_meteostation,
                    feature_watering_liters, feature_smart_suggestions,
                    created_at, updated_at
                )
                VALUES (
                    :name, :greenhouse_id, '',
                    CAST(NULLIF(:controller_ip, '') AS inet), :controller_username, :controller_password,
                    TRUE, TRUE, FALSE,
                    FALSE, FALSE,
                    NOW(), NOW()
                )
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "name": name,
                "greenhouse_id": greenhouse_id,
                "controller_ip": mqtt_broker or "",
                "controller_username": mqtt_username or "",
                "controller_password": mqtt_password or "",
            },
        )

        db.execute(
            text(
                """
                UPDATE greenhouse_config
                SET
                    greenhouse_id = COALESCE(:greenhouse_id, greenhouse_id),
                    controller_ip = COALESCE(CAST(NULLIF(:controller_ip, '') AS inet), controller_ip),
                    controller_username = CASE
                        WHEN COALESCE(:controller_username, '') <> '' THEN :controller_username
                        ELSE controller_username
                    END,
                    controller_password = CASE
                        WHEN COALESCE(:controller_password, '') <> '' THEN :controller_password
                        ELSE controller_password
                    END,
                    updated_at = NOW()
                WHERE name = :name
                """
            ),
            {
                "name": name,
                "greenhouse_id": greenhouse_id,
                "controller_ip": mqtt_broker or "",
                "controller_username": mqtt_username or "",
                "controller_password": mqtt_password or "",
            },
        )

    @staticmethod
    def _attach_mqtt_settings(db, greenhouse: Greenhouse) -> Greenhouse:
        row = db.execute(
            text(
                """
                SELECT
                    COALESCE(controller_ip::text, '') AS mqtt_broker,
                    1883 AS mqtt_port,
                    COALESCE(controller_username, '') AS mqtt_username,
                    COALESCE(controller_password, '') AS mqtt_password
                FROM greenhouse_config
                WHERE greenhouse_id = :greenhouse_id OR name = :name
                ORDER BY selected DESC, id DESC
                LIMIT 1
                """
            ),
            {"greenhouse_id": greenhouse.id, "name": greenhouse.name},
        ).mappings().first()

        if row:
            greenhouse.mqtt_broker = row["mqtt_broker"]
            greenhouse.mqtt_port = int(row["mqtt_port"])
            greenhouse.mqtt_username = row["mqtt_username"]
            greenhouse.mqtt_password = row["mqtt_password"]
        else:
            greenhouse.mqtt_broker = ""
            greenhouse.mqtt_port = 1883
            greenhouse.mqtt_username = ""
            greenhouse.mqtt_password = ""

        return greenhouse

    @staticmethod
    def _attach_mqtt_settings_bulk(db, greenhouses: List[Greenhouse]) -> List[Greenhouse]:
        for greenhouse in greenhouses:
            GreenhouseService._attach_mqtt_settings(db, greenhouse)
        return greenhouses

    @staticmethod
    def create_greenhouse(
        name: str,
        mqtt_username: str,
        mqtt_password: str,
        mqtt_broker: str = "192.168.8.151",
        mqtt_port: int = 1883,
        description: str = None,
        location: str = None,
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
            )
            db.add(greenhouse)
            db.flush()

            GreenhouseService._upsert_greenhouse_config(
                db,
                greenhouse_id=greenhouse_id,
                name=name,
                mqtt_broker=mqtt_broker,
                mqtt_username=mqtt_username,
                mqtt_password=mqtt_password,
            )

            db.commit()
            db.refresh(greenhouse)
            GreenhouseService._attach_mqtt_settings(db, greenhouse)
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
            greenhouse = db.query(Greenhouse).filter(Greenhouse.id == greenhouse_id).first()
            if greenhouse:
                GreenhouseService._attach_mqtt_settings(db, greenhouse)
            return greenhouse
        except Exception as e:
            logger.error(f"Error getting greenhouse {greenhouse_id}: {e}")
            raise
        finally:
            db.close()

    @staticmethod
    def get_all_greenhouses() -> List[Greenhouse]:
        db = SessionLocal()
        try:
            rows = db.query(Greenhouse).order_by(Greenhouse.created_at.desc()).all()
            return GreenhouseService._attach_mqtt_settings_bulk(db, rows)
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

            mqtt_broker = kwargs.pop("mqtt_broker", None)
            kwargs.pop("mqtt_port", None)  # Port is fixed at 1883 in greenhouse_config model.
            mqtt_username = kwargs.pop("mqtt_username", None)
            mqtt_password = kwargs.pop("mqtt_password", None)

            for key, value in kwargs.items():
                if hasattr(greenhouse, key):
                    setattr(greenhouse, key, value)

            GreenhouseService._upsert_greenhouse_config(
                db,
                greenhouse_id=greenhouse.id,
                name=kwargs.get("name", greenhouse.name),
                mqtt_broker=mqtt_broker,
                mqtt_username=mqtt_username,
                mqtt_password=mqtt_password,
            )

            db.commit()
            db.refresh(greenhouse)
            GreenhouseService._attach_mqtt_settings(db, greenhouse)
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

            db.delete(greenhouse)
            db.commit()
            logger.info(f"Deleted greenhouse: {greenhouse_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting greenhouse {greenhouse_id}: {e}")
            raise
        finally:
            db.close()
