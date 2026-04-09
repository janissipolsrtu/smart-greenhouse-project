# Temperature Dashboard - Manual Deployment Guide

## Prerequisites

Your system needs Docker Compose to run the containerized temperature dashboard. 

### Option 1: Install Docker Compose (Recommended)

1. **Install Docker Desktop** (includes Docker Compose):
   - Download from: https://www.docker.com/products/docker-desktop/
   - This includes both Docker and Docker Compose

2. **Or install Docker Compose separately**:
   ```powershell
   # Using Chocolatey (if you have it)
   choco install docker-compose
   
   # Or download from GitHub releases
   # https://github.com/docker/compose/releases
   ```

### Option 2: Alternative Deployment (Manual Container Setup)

If you can't install Docker Compose, you can run each service manually:

#### 1. Create a Docker network
```powershell
docker network create irrigation_network
```

#### 2. Start PostgreSQL Database
```powershell
docker run -d --name irrigation-postgres `
  --network irrigation_network `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -p 5432:5432 `
  postgres:15-alpine
```

#### 3. Start Redis
```powershell
docker run -d --name irrigation-redis `
  --network irrigation_network `
  -p 6379:6379 `
  redis:7-alpine
```

#### 4. Build Django application
```powershell
docker build -f Dockerfile.django -t irrigation-django .
```

#### 5. Run Django migrations
```powershell
docker run --rm --network irrigation_network `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -e POSTGRES_HOST=irrigation-postgres `
  irrigation-django python manage.py makemigrations irrigation

docker run --rm --network irrigation_network `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -e POSTGRES_HOST=irrigation-postgres `
  irrigation-django python manage.py migrate
```

#### 6. Start Django Web App
```powershell
docker run -d --name irrigation-django-webapp `
  --network irrigation_network `
  -p 8080:8080 `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -e POSTGRES_HOST=irrigation-postgres `
  -e POSTGRES_PORT=5432 `
  -e REDIS_HOST=irrigation-redis `
  -e DJANGO_SECRET_KEY=django-secret-key-change-me `
  -e DEBUG=True `
  irrigation-django
```

#### 7. Build and start sensor data collector
```powershell
# Build sensor service
docker build -f Dockerfile.sensor -t irrigation-sensor .

# Start sensor data collector
docker run -d --name irrigation-sensor-collector `
  --network irrigation_network `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -e POSTGRES_HOST=irrigation-postgres `
  -e POSTGRES_PORT=5432 `
  -e MQTT_BROKER=192.168.8.151 `
  -e MQTT_PORT=1883 `
  -e MQTT_TOPIC=zigbee2mqtt/+ `
  irrigation-sensor
```

#### 8. Build and start other services (optional)
```powershell
# Build celery services
docker build -f Dockerfile.celery -t irrigation-celery .

# Start Celery worker
docker run -d --name irrigation-celery-worker `
  --network irrigation_network `
  -e DATABASE_URL=postgresql://irrigation_user:irrigation_pass@irrigation-postgres:5432/irrigation_db `
  -e CELERY_BROKER_URL=redis://irrigation-redis:6379/0 `
  -e CELERY_RESULT_BACKEND=redis://irrigation-redis:6379/0 `
  -e MQTT_BROKER=192.168.8.151 `
  irrigation-celery celery -A celery_config.celery_app worker --loglevel=info

# Start FastAPI
docker build -f Dockerfile -t irrigation-api .
docker run -d --name irrigation-api `
  --network irrigation_network `
  -p 8000:8000 `
  -e DATABASE_URL=postgresql://irrigation_user:irrigation_pass@irrigation-postgres:5432/irrigation_db `
  irrigation-api
```

## Verification

After deployment, check that services are running:

```powershell
# Check container status
docker ps

# Check logs
docker logs irrigation-sensor-collector
docker logs irrigation-django-webapp

# Test the application
# Open browser to: http://localhost:8080
# Navigate to: http://localhost:8080/temperature/
```

## Using the Temperature Dashboard

1. **Web Interface**: http://localhost:8080
2. **Temperature Dashboard**: http://localhost:8080/temperature/
3. **API Documentation**: http://localhost:8000/docs (if FastAPI is running)

### Features:
- **Real-time sensor monitoring** - View current temperature and humidity from MQTT sensors
- **24-hour trends** - Interactive charts showing temperature and humidity over time
- **Device details** - Detailed view for each sensor with historical data
- **Auto-refresh** - Dashboard automatically updates with new sensor data
- **Mobile responsive** - Works on desktop and mobile devices

### Sensor Data Collection:
The sensor service automatically:
- Connects to your Raspberry Pi MQTT broker (192.168.8.151)
- Subscribes to Zigbee2MQTT sensor topics (`zigbee2mqtt/+`)
- Stores temperature, humidity, and signal quality data
- Updates the dashboard in real-time

## Troubleshooting

### If sensor data isn't appearing:
1. Check sensor collector logs: `docker logs irrigation-sensor-collector`
2. Verify MQTT broker is accessible: `ping 192.168.8.151`
3. Check if sensors are publishing data to Zigbee2MQTT
4. Verify database permissions: `docker logs irrigation-postgres`

### If Django app won't start:
1. Check database connection: `docker logs irrigation-django-webapp`
2. Verify all environment variables are set correctly
3. Ensure migrations ran successfully

### If containers won't communicate:
1. Verify all containers are on the same network: `docker network ls`
2. Check container connectivity: `docker exec -it irrigation-django-webapp ping irrigation-postgres`

## Next Steps

Once the temperature dashboard is working:
1. **Add more sensors** - The system automatically detects new Zigbee2MQTT devices
2. **Configure alerts** - Set up temperature/humidity thresholds (future feature)
3. **Export data** - Use the API endpoints to export historical data
4. **Integrate with irrigation** - Use sensor data to trigger automated irrigation plans