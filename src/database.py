"""Database configuration and connection management"""
import os
from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import logging

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://irrigation_user:irrigation_pass@localhost:5432/irrigation_db")

# SQLAlchemy setup
engine = create_engine(
    DATABASE_URL,
    poolclass=None if "sqlite" in DATABASE_URL else NullPool,
    echo=False,  # Set to True for SQL debugging
    future=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get DB session
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """Initialize database tables"""
    try:
        logger.info("Initializing database...")
        with engine.begin() as conn:
            tables = {
                row["table_name"]
                for row in conn.execute(text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_name IN ('watering_cycle', 'irrigation_plans')
                    """
                )).mappings().all()
            }

            if "watering_cycle" not in tables and "irrigation_plans" in tables:
                conn.execute(text("ALTER TABLE irrigation_plans RENAME TO watering_cycle"))
                logger.info("Renamed irrigation_plans table to watering_cycle")

                conn.execute(text(
                    "DO $$ BEGIN "
                    "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'irrigation_plans_plan_id_fk') THEN "
                    "ALTER TABLE watering_cycle RENAME CONSTRAINT irrigation_plans_plan_id_fk TO watering_cycle_plan_id_fk; "
                    "END IF; "
                    "END $$;"
                ))

                conn.execute(text(
                    "DO $$ BEGIN "
                    "IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'ix_irrigation_plans_plan_id') THEN "
                    "ALTER INDEX ix_irrigation_plans_plan_id RENAME TO ix_watering_cycle_plan_id; "
                    "END IF; "
                    "END $$;"
                ))

        Base.metadata.create_all(bind=engine)
        # Backward-compatible schema update for existing databases.
        # create_all does not add new columns to existing tables.
        with engine.begin() as conn:
            columns = [row["column_name"] for row in conn.execute(text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'watering_cycle'
                """
            )).mappings().all()]
            if "plan_id" not in columns:
                conn.execute(text("ALTER TABLE watering_cycle ADD COLUMN plan_id VARCHAR"))
                logger.info("Added plan_id column to watering_cycle")

            if "greenhouse_config_id" not in columns:
                conn.execute(text("ALTER TABLE watering_cycle ADD COLUMN greenhouse_config_id INTEGER"))
                logger.info("Added greenhouse_config_id column to watering_cycle")

            conn.execute(text(
                """
                UPDATE watering_cycle wc
                SET greenhouse_config_id = wp.greenhouse_config_id
                FROM watering_plans wp
                WHERE wc.plan_id = wp.id
                  AND wc.greenhouse_config_id IS NULL
                """
            ))

            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_watering_cycle_plan_id ON watering_cycle (plan_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_watering_cycle_greenhouse_config_id ON watering_cycle (greenhouse_config_id)"))
            conn.execute(text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'watering_cycle_greenhouse_config_id_fkey') THEN
                        ALTER TABLE watering_cycle
                        ADD CONSTRAINT watering_cycle_greenhouse_config_id_fkey
                        FOREIGN KEY (greenhouse_config_id)
                        REFERENCES greenhouse_config(id)
                        ON DELETE SET NULL;
                    END IF;
                END $$;
                """
            ))

            # Sensor data schema for time-series workloads and Grafana dashboards.
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS sensor_data (
                    id BIGSERIAL PRIMARY KEY,
                    device_name VARCHAR(100) NOT NULL,
                    topic VARCHAR(255),
                    temperature DOUBLE PRECISION,
                    humidity DOUBLE PRECISION,
                    linkquality INTEGER,
                    battery INTEGER,
                    max_temperature DOUBLE PRECISION,
                    min_temperature DOUBLE PRECISION,
                    temperature_sensitivity DOUBLE PRECISION,
                    temperature_calibration DOUBLE PRECISION,
                    temperature_sampling INTEGER,
                    temperature_unit VARCHAR(20),
                    humidity_calibration DOUBLE PRECISION,
                    soil_moisture DOUBLE PRECISION,
                    soil_calibration DOUBLE PRECISION,
                    soil_sampling INTEGER,
                    soil_warning INTEGER,
                    dry BOOLEAN,
                    raw_data JSONB,
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            ))

            # Ensure new columns exist for older deployments where sensor_data already exists.
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS topic VARCHAR(255)"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS battery INTEGER"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS min_temperature DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS temperature_sensitivity DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS temperature_calibration DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS temperature_sampling INTEGER"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS humidity_calibration DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS soil_moisture DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS soil_calibration DOUBLE PRECISION"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS soil_sampling INTEGER"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS soil_warning INTEGER"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS dry BOOLEAN"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS raw_data JSONB"))
            conn.execute(text("ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP"))

            # Normalize older timestamp type if it was created without timezone.
            conn.execute(text(
                """
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'sensor_data'
                          AND column_name = 'timestamp'
                          AND data_type = 'timestamp without time zone'
                    ) THEN
                        ALTER TABLE sensor_data
                        ALTER COLUMN timestamp TYPE TIMESTAMPTZ USING timestamp AT TIME ZONE 'UTC';
                    END IF;
                END $$;
                """
            ))

            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sensor_timestamp ON sensor_data(timestamp DESC)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sensor_device_timestamp ON sensor_data(device_name, timestamp DESC)"))

            # Seasons and plant-greenhouse linkage compatibility.
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS seasons (
                    id SERIAL PRIMARY KEY,
                    greenhouse_id VARCHAR NOT NULL,
                    name VARCHAR(120) NOT NULL,
                    start_date DATE,
                    end_date DATE,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT seasons_greenhouse_name_key UNIQUE (greenhouse_id, name)
                )
                """
            ))
            conn.execute(text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'seasons_greenhouse_id_fkey') THEN
                        ALTER TABLE seasons
                        ADD CONSTRAINT seasons_greenhouse_id_fkey
                        FOREIGN KEY (greenhouse_id)
                        REFERENCES greenhouses(id)
                        ON DELETE CASCADE;
                    END IF;
                END $$;
                """
            ))
            conn.execute(text("ALTER TABLE plants ADD COLUMN IF NOT EXISTS greenhouse_id VARCHAR"))
            conn.execute(text("ALTER TABLE plants ADD COLUMN IF NOT EXISTS season_id INTEGER"))
            conn.execute(text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'plants_greenhouse_id_fkey') THEN
                        ALTER TABLE plants
                        ADD CONSTRAINT plants_greenhouse_id_fkey
                        FOREIGN KEY (greenhouse_id)
                        REFERENCES greenhouses(id)
                        ON DELETE SET NULL;
                    END IF;
                    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'plants_season_id_fkey') THEN
                        ALTER TABLE plants
                        ADD CONSTRAINT plants_season_id_fkey
                        FOREIGN KEY (season_id)
                        REFERENCES seasons(id)
                        ON DELETE SET NULL;
                    END IF;
                END $$;
                """
            ))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_plants_greenhouse_id ON plants (greenhouse_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_plants_season_id ON plants (season_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_seasons_greenhouse_id ON seasons (greenhouse_id)"))

            # NOTE: sensor_measurements table has been consolidated into sensor_data.
            # All sensor data is now stored in sensor_data table for simplified management.
            # Legacy sensor_measurements table creation code removed 2026-05-13.
            # Historical reference: sensor_measurements was a TimescaleDB hypertable for time-series workloads.
            pass  # sensor_measurements consolidated to sensor_data
        logger.info("Database initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def test_database_connection():
    """Test database connectivity"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            logger.info("Database connection successful")
            return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False