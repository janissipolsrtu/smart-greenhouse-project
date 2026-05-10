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