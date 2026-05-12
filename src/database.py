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

            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_watering_cycle_plan_id ON watering_cycle (plan_id)"))

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

            # Dedicated time-series table for TimescaleDB/Grafana workloads.
            conn.execute(text(
                """
                CREATE TABLE IF NOT EXISTS sensor_measurements (
                    id BIGSERIAL,
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
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sensor_measurements_ts ON sensor_measurements(timestamp DESC)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sensor_measurements_device_ts ON sensor_measurements(device_name, timestamp DESC)"))
            conn.execute(text(
                """
                DO $$
                DECLARE
                    pk_name text;
                BEGIN
                    SELECT conname INTO pk_name
                    FROM pg_constraint
                    WHERE conrelid = 'sensor_measurements'::regclass
                      AND contype = 'p'
                    LIMIT 1;

                    IF pk_name IS NOT NULL THEN
                        EXECUTE format('ALTER TABLE sensor_measurements DROP CONSTRAINT %I', pk_name);
                    END IF;
                END $$;
                """
            ))

            # Convert to TimescaleDB hypertable when extension is available.
            conn.execute(text(
                """
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb') THEN
                        CREATE EXTENSION IF NOT EXISTS timescaledb;
                        PERFORM create_hypertable('sensor_measurements', by_range('timestamp'), if_not_exists => TRUE, migrate_data => TRUE);
                    END IF;
                EXCEPTION
                    WHEN OTHERS THEN
                        RAISE NOTICE 'TimescaleDB setup skipped: %', SQLERRM;
                END $$;
                """
            ))

            # Grafana-friendly view with bucketed aggregates.
            conn.execute(text(
                """
                DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'timescaledb') THEN
                        EXECUTE '
                            CREATE OR REPLACE VIEW sensor_metrics_5m AS
                            SELECT
                                time_bucket(INTERVAL ''5 minutes'', timestamp) AS bucket,
                                device_name,
                                AVG(temperature) AS avg_temperature,
                                MIN(temperature) AS min_temperature,
                                MAX(temperature) AS max_temperature,
                                AVG(humidity) AS avg_humidity,
                                AVG(soil_moisture) AS avg_soil_moisture,
                                AVG(battery) AS avg_battery,
                                COUNT(*) AS sample_count
                            FROM sensor_measurements
                            GROUP BY bucket, device_name
                            ORDER BY bucket DESC
                        ';
                    ELSE
                        EXECUTE '
                            CREATE OR REPLACE VIEW sensor_metrics_5m AS
                            SELECT
                                date_trunc(''hour'', timestamp)
                                    + (floor(date_part(''minute'', timestamp) / 5) * INTERVAL ''5 minutes'') AS bucket,
                                device_name,
                                AVG(temperature) AS avg_temperature,
                                MIN(temperature) AS min_temperature,
                                MAX(temperature) AS max_temperature,
                                AVG(humidity) AS avg_humidity,
                                AVG(soil_moisture) AS avg_soil_moisture,
                                AVG(battery) AS avg_battery,
                                COUNT(*) AS sample_count
                            FROM sensor_measurements
                            GROUP BY bucket, device_name
                            ORDER BY bucket DESC
                        ';
                    END IF;
                END $$;
                """
            ))
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