# Migration Guide: APScheduler to Celery

This guide explains how to migrate your irrigation system from APScheduler to Celery for better reliability, scalability, and monitoring.

## 📋 What Changed

### Before (APScheduler)
- **Single-process** scheduling with persistent SQLAlchemy job storage
- **Blocking scheduler** that runs periodically every 30 seconds
- **Limited scalability** and monitoring capabilities
- **Memory leak issues** over time with complex job management

### After (Celery)
- **Distributed task queue** with Redis as message broker
- **Separate worker processes** for task execution
- **Beat scheduler** for periodic tasks (replaces APScheduler periodic checking)
- **Horizontal scaling** capability with multiple workers
- **Advanced monitoring** with Flower web interface
- **Better error handling** and retry mechanisms

## 🏗️ Architecture Changes

```
OLD: API Server + APScheduler (Single Process)
├── FastAPI Application
├── APScheduler BlockingScheduler
├── SQLAlchemy Job Store (PostgreSQL)
└── MQTT Client

NEW: Distributed Celery System
├── FastAPI Application (separate process)
├── Celery Worker(s) (task execution)
├── Celery Beat (periodic scheduler)  
├── Redis (message broker)
├── PostgreSQL (data storage)
├── Flower (monitoring)
└── MQTT Client (in workers)
```

## 📦 New Dependencies

Add to your requirements:
```bash
# Install Celery dependencies
pip install -r requirements_celery.txt
```

**New packages:**
- `celery[redis]==5.3.4` - Distributed task queue
- `redis==5.0.1` - Message broker
- `flower==2.0.1` - Web monitoring interface

## 🚀 Running the New System

### Option 1: Docker Compose (Recommended)
```bash
# Use the new Celery-based docker-compose
docker-compose -f docker-compose-celery.yml up -d

# Services started:
# - postgres (database)
# - redis (message broker)  
# - irrigation-api (FastAPI)
# - celery-worker (task execution)
# - celery-beat (periodic scheduler)
# - flower (monitoring at :5555)
```

### Option 2: Local Development 
```bash
# Linux/Mac
chmod +x run_celery_system.sh
./run_celery_system.sh

# Windows 
run_celery_system.bat
```

### Option 3: Manual Service Management
```bash
# Terminal 1: Start Redis
redis-server

# Terminal 2: Start Celery Worker
celery -A celery_config.celery_app worker --loglevel=info

# Terminal 3: Start Celery Beat  
celery -A celery_config.celery_app beat --loglevel=info

# Terminal 4: Start Flower (optional monitoring)
celery -A celery_config.celery_app flower --port=5555

# Terminal 5: Start API
python irrigation_api.py
```

## 🔄 Task Migration

### APScheduler Functions → Celery Tasks

| APScheduler Function | Celery Task | Purpose |
|---------------------|-------------|---------|
| `periodic_irrigation_check()` | `@shared_task check_due_irrigations()` | Periodic database checking |
| `execute_irrigation()` | `@shared_task execute_irrigation()` | MQTT irrigation execution |
| `update_plan_status()` | `@shared_task update_plan_status()` | Database status updates |
| - | `@shared_task schedule_irrigation_plan()` | **New**: Plan scheduling from API |
| - | `@shared_task health_check()` | **New**: Worker health monitoring |

### Key Changes in Task Execution

**Before (APScheduler):**
```python
# Direct function calls in scheduler
scheduler.add_job(
    func=periodic_irrigation_check,
    trigger='interval', 
    seconds=30
)
```

**After (Celery):**
```python
# Distributed task execution
@shared_task
def check_due_irrigations():
    # Task logic here
    pass

# Automatic scheduling via beat_schedule
beat_schedule = {
    "check-due-irrigations": {
        "task": "celery_tasks.check_due_irrigations",
        "schedule": timedelta(seconds=30),
    }
}
```

## 🔍 Monitoring & Health Checks

### Flower Dashboard
- **URL**: http://localhost:5555
- **Features**: 
  - Real-time task monitoring
  - Worker status and statistics
  - Task history and results
  - Queue lengths and throughput
  - Worker resource usage

### Celery Commands
```bash
# Check worker status
celery -A celery_config.celery_app inspect active

# Check scheduled tasks  
celery -A celery_config.celery_app inspect scheduled

# Check worker statistics
celery -A celery_config.celery_app inspect stats

# Purge all tasks
celery -A celery_config.celery_app purge
```

## 🚨 Error Handling Improvements

### APScheduler Limitations
- Limited retry mechanisms
- Hard to debug failed jobs
- No granular error tracking

### Celery Advantages  
```python
@shared_task(bind=True, autoretry_for=(Exception,), 
            retry_kwargs={'max_retries': 3, 'countdown': 60})
def execute_irrigation(self, plan_id, device, duration, description):
    try:
        # Task execution
        pass
    except Exception as e:
        # Automatic retry with exponential backoff
        raise self.retry(exc=e)
```

## 📊 Performance Benefits

| Metric | APScheduler | Celery | Improvement |
|--------|-------------|--------|-------------|
| **Scalability** | Single process | Multiple workers | ∞ horizontal scale |
| **Monitoring** | Limited logging | Flower + metrics | Real-time dashboard |
| **Reliability** | Memory leaks | Process isolation | Better fault tolerance |
| **Task Distribution** | Sequential | Parallel queues | Better throughput |
| **Development** | Blocking | Non-blocking API | Faster iteration |

## 🔧 Configuration

### Environment Variables
```bash
# Required for Celery
export CELERY_BROKER_URL="redis://localhost:6379/0"
export CELERY_RESULT_BACKEND="redis://localhost:6379/0"

# Existing database (unchanged)
export DATABASE_URL="postgresql://irrigation_user:irrigation_pass@localhost:5432/irrigation_db"
export MQTT_BROKER="192.168.8.151"
```

### Queue Configuration
- `irrigation_checks` - Periodic database checks
- `irrigation_execution` - MQTT irrigation commands  
- `irrigation_scheduling` - New plan scheduling

## 🔄 Migration Steps

1. **Install Dependencies**
   ```bash
   pip install -r requirements_celery.txt
   ```

2. **Start Redis** (new requirement)
   ```bash
   # Linux/Mac
   redis-server
   
   # Windows  
   # Download and run Redis for Windows
   ```

3. **Update Environment Variables**
   ```bash
   export CELERY_BROKER_URL="redis://localhost:6379/0"
   export CELERY_RESULT_BACKEND="redis://localhost:6379/0"  
   ```

4. **Test New System**
   ```bash
   # Start all services
   ./run_celery_system.sh  # or .bat on Windows
   ```

5. **Verify Migration**
   - Check Flower dashboard: http://localhost:5555
   - Test API endpoints: http://localhost:8000/docs
   - Monitor task execution in Flower
   - Verify irrigation plans execute correctly

## ✅ Verification Checklist

- [ ] Redis server running and accessible
- [ ] Celery worker started and connected
- [ ] Celery beat scheduler running  
- [ ] Flower monitoring accessible
- [ ] API server responding
- [ ] Database connections working
- [ ] MQTT connectivity functional
- [ ] Irrigation plans scheduling correctly
- [ ] Tasks executing and completing
- [ ] Error handling working (retry logic)

## 🆘 Troubleshooting

### Common Issues

**Redis Connection Failed**
```bash
# Check Redis status
redis-cli ping
# Should return: PONG
```

**Worker Not Processing Tasks**
```bash
# Check worker status
celery -A celery_config.celery_app inspect active
```

**Beat Scheduler Not Running**
```bash
# Restart beat scheduler
celery -A celery_config.celery_app beat --loglevel=info
```

**Database Connection Issues**
- Same connection string as before
- Ensure PostgreSQL is running
- Check firewall/network settings

## 📈 Next Steps

After migrating to Celery, you can:

1. **Scale Horizontally**: Add more Celery workers on different machines
2. **Advanced Monitoring**: Integrate with Prometheus/Grafana
3. **Load Balancing**: Distribute tasks across multiple workers
4. **Fault Tolerance**: Add Redis clustering for high availability
5. **Performance Tuning**: Optimize task routing and queue management

The new Celery-based system is more robust, scalable, and maintainable than the previous APScheduler implementation!