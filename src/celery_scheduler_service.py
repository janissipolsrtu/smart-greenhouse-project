#!/usr/bin/env python3
"""
Celery-based Irrigation Scheduler Service
Replaces APScheduler with Celery for better reliability and scalability
"""

import logging
import signal
import sys
import time
from datetime import datetime
from celery import Celery
from celery_config import celery_app
from database import init_database, test_database_connection

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CelerySchedulerService:
    """Celery-based scheduler service for irrigation automation"""
    
    def __init__(self):
        self.celery_app = celery_app
        self.running = False
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        sys.exit(0)
    
    def initialize_database(self):
        """Initialize database connection and tables"""
        try:
            logger.info("Initializing database connection...")
            init_database()
            
            # Test database connection
            if test_database_connection():
                logger.info("Database connection successful")
                return True
            else:
                logger.error("Database connection test failed")
                return False
                
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False
    
    def start_celery_beat(self):
        """Start Celery beat scheduler for periodic tasks"""
        try:
            logger.info("Starting Celery Beat scheduler...")
            
            # The beat scheduler is started separately with:
            # celery -A celery_config.celery_app beat --loglevel=info
            logger.info("Celery Beat should be started with: celery -A celery_config.celery_app beat --loglevel=info")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure Celery Beat: {e}")
            return False
    
    def start_celery_worker(self):
        """Start Celery worker for task execution"""
        try:
            logger.info("Starting Celery Worker...")
            
            # Start the worker programmatically
            worker = self.celery_app.Worker(
                loglevel='info',
                queues=['irrigation_checks', 'irrigation_execution', 'irrigation_scheduling']
            )
            
            logger.info("Celery Worker started successfully")
            worker.start()
            
        except Exception as e:
            logger.error(f"Failed to start Celery Worker: {e}")
            return False
    
    def check_celery_connection(self):
        """Check if Celery broker is accessible"""
        try:
            # Check broker connection
            inspect = self.celery_app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                logger.info(f"Celery broker connection successful. Workers: {len(stats)}")
                return True
            else:
                logger.warning("No Celery workers found")
                return False
                
        except Exception as e:
            logger.error(f"Celery broker connection failed: {e}")
            return False
    
    def run_service(self):
        """Main service loop"""
        logger.info("Starting Celery-based Irrigation Scheduler Service...")
        
        # Initialize database
        if not self.initialize_database():
            logger.error("Failed to initialize database. Exiting.")
            return False
        
        # Check Celery connection
        if not self.check_celery_connection():
            logger.warning("Celery broker not accessible. Tasks may not execute.")
        
        # Configure beat scheduler
        if not self.start_celery_beat():
            logger.error("Failed to configure Celery Beat. Exiting.")
            return False
        
        logger.info("=" * 60)
        logger.info("🌱 Celery Irrigation Scheduler Service Started")
        logger.info("=" * 60)
        logger.info("✅ Database initialized")
        logger.info("✅ Celery configuration loaded")
        logger.info("✅ Periodic task checking configured")
        logger.info("📋 Tasks Available:")
        logger.info("   - check_due_irrigations (every 30 seconds)")
        logger.info("   - execute_irrigation")
        logger.info("   - schedule_irrigation_plan")
        logger.info("   - update_plan_status")
        logger.info("=" * 60)
        
        self.running = True
        
        try:
            # Start worker (this will block)
            self.start_celery_worker()
            
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            logger.info("Irrigation Scheduler Service stopped")
            
        return True

def main():
    """Main entry point"""
    service = CelerySchedulerService()
    service.run_service()

if __name__ == "__main__":
    main()