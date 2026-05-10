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
        Base.metadata.create_all(bind=engine)
        # Backward-compatible schema update for existing databases.
        # create_all does not add new columns to existing tables.
        with engine.begin() as conn:
            columns = [row["column_name"] for row in conn.execute(text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'irrigation_plans'
                """
            )).mappings().all()]
            if "plan_id" not in columns:
                conn.execute(text("ALTER TABLE irrigation_plans ADD COLUMN plan_id VARCHAR"))
                logger.info("Added plan_id column to irrigation_plans")

            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_irrigation_plans_plan_id ON irrigation_plans (plan_id)"))
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