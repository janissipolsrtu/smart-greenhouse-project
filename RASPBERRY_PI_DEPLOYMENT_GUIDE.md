# 🌡️ Raspberry Pi + Backend Temperature Monitoring System

## Architecture Overview

The system is now split into two parts for better reliability and scalability:

```
┌─────────────────┐    📡 HTTP API    ┌─────────────────┐
│  Raspberry Pi   │ ◄─────────────► │  Main Server    │
│                 │                  │                 │
│ • MQTT Broker   │                  │ • Django Web    │
│ • Zigbee2MQTT   │                  │ • PostgreSQL    │
│ • Sensor        │                  │ • Redis/Celery  │
│   Collector     │                  │ • API Endpoints │
└─────────────────┘                  └─────────────────┘
```

### Benefits of this architecture:
- **Reduced network traffic** - only sends batched data every few minutes
- **Better reliability** - continues working even if network connection is temporarily lost
- **Local MQTT processing** - sensor collector runs close to the sensors
- **Scalable** - easy to add multiple Raspberry Pi locations
- **Fault tolerant** - automatic retries and buffering

---

## 🚀 Quick Setup

### 1. Main Server Deployment

**On your main server (Windows/Linux):**

```powershell
# Windows PowerShell
.\setup_main_server.ps1
```

```bash
# Linux/WSL
./setup_main_server.sh
```

This will start:
- PostgreSQL database
- Django web application (port 8080)
- API endpoints for receiving sensor data
- Optional: Celery workers and FastAPI

### 2. Raspberry Pi Deployment

**Copy these files to your Raspberry Pi:**
- `raspberry_pi_sensor_collector.py`
- `Dockerfile.raspberry_pi`
- `docker-compose.raspberry-pi.yml`
- `setup_raspberry_pi.sh`

**Then run on Raspberry Pi:**
```bash
chmod +x setup_raspberry_pi.sh
./setup_raspberry_pi.sh
```

---

## 📋 Detailed Setup Instructions

### Main Server Setup

#### Prerequisites
- Docker installed
- 8GB+ RAM recommended
- Network access from Raspberry Pi

#### Manual Container Setup

If you don't have Docker Compose:

```powershell
# 1. Create network
docker network create irrigation_network

# 2. Start PostgreSQL
docker run -d --name irrigation-postgres `
  --network irrigation_network `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -p 5432:5432 `
  postgres:15-alpine

# 3. Start Redis
docker run -d --name irrigation-redis `
  --network irrigation_network `
  -p 6379:6379 `
  redis:7-alpine

# 4. Build and start Django
docker build -f Dockerfile.django -t irrigation-django .

# Wait 15 seconds for DB to initialize
Start-Sleep -Seconds 15

# Run migrations
docker run --rm --network irrigation_network `
  -e POSTGRES_HOST=irrigation-postgres `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  irrigation-django python manage.py migrate

# Start Django webapp
docker run -d --name irrigation-django-webapp `
  --network irrigation_network `
  -p 8080:8080 `
  -e POSTGRES_HOST=irrigation-postgres `
  -e POSTGRES_DB=irrigation_db `
  -e POSTGRES_USER=irrigation_user `
  -e POSTGRES_PASSWORD=irrigation_pass `
  -e REDIS_HOST=irrigation-redis `
  -e DJANGO_SECRET_KEY=your-secret-key `
  irrigation-django
```

### Raspberry Pi Setup

#### Prerequisites
- Raspberry Pi with Docker
- Zigbee2MQTT running locally
- Network access to main server

#### Configuration

Edit `docker-compose.raspberry-pi.yml`:

```yaml
environment:
  - BACKEND_SERVER=http://192.168.8.100:8080  # Your server IP
  - BATCH_SIZE=25          # Send every 25 readings
  - BATCH_INTERVAL=180     # Or every 3 minutes
  - MQTT_BROKER=localhost  # Local Zigbee2MQTT
```

#### Manual Docker Setup

```bash
# Build container
docker build -f Dockerfile.raspberry_pi -t raspberry-sensor-collector .

# Run collector
docker run -d --name raspberry-pi-sensor-collector \
  --network host \
  -e MQTT_BROKER=localhost \
  -e BACKEND_SERVER=http://192.168.8.100:8080 \
  -e BATCH_SIZE=25 \
  -e BATCH_INTERVAL=180 \
  raspberry-sensor-collector
```

---

## 🔧 Configuration Options

### Sensor Collector Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MQTT_BROKER` | `localhost` | MQTT broker address |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `MQTT_TOPIC` | `zigbee2mqtt/+` | MQTT topic pattern |
| `BACKEND_SERVER` | Required | Main server URL |
| `BATCH_SIZE` | `50` | Readings per batch |
| `BATCH_INTERVAL` | `300` | Max seconds between sends |
| `MAX_RETRIES` | `3` | Failed send retries |
| `RETRY_DELAY` | `30` | Seconds between retries |

### Backend API Configuration

The main server provides these endpoints:

- `GET /api/health/` - Health check for Raspberry Pi
- `POST /api/sensor-data/bulk/` - Receive batched sensor data
- `GET /api/sensor-data/` - Query sensor data
- `GET /temperature/` - Temperature dashboard

---

## 📊 Monitoring & Troubleshooting

### Check Raspberry Pi Status

```bash
# View collector logs
docker logs raspberry-pi-sensor-collector -f

# Check if sending data
docker logs raspberry-pi-sensor-collector | grep "Successfully sent"

# Test backend connectivity
curl http://your-server:8080/api/health/
```

### Check Main Server Status

```powershell
# View Django logs
docker logs irrigation-django-webapp -f

# Check received data
docker logs irrigation-django-webapp | grep "bulk_sensor_data"

# Test API endpoint
Invoke-RestMethod -Uri "http://localhost:8080/api/health/"
```

### Common Issues

**Problem: Raspberry Pi can't reach backend**
```bash
# Test connectivity
ping 192.168.8.100
curl -v http://192.168.8.100:8080/api/health/

# Check firewall on main server
```

**Problem: No sensor data appearing**
```bash
# Check MQTT broker
mosquitto_sub -h localhost -t "zigbee2mqtt/+"

# Check collector logs
docker logs raspberry-pi-sensor-collector | grep "Buffered reading"
```

**Problem: Backend not receiving data**
```bash
# Check Django logs
docker logs irrigation-django-webapp | grep "POST.*sensor-data"

# Verify database connection
docker exec irrigation-postgres psql -U irrigation_user -d irrigation_db -c "SELECT COUNT(*) FROM sensor_data;"
```

---

## 🌐 Data Flow

1. **Sensors** → Zigbee2MQTT → **MQTT Broker** (on Raspberry Pi)
2. **Sensor Collector** subscribes to MQTT topics
3. **Collector** buffers readings (25 readings or 3 minutes)
4. **Collector** sends HTTP POST to `/api/sensor-data/bulk/`
5. **Backend** stores data in PostgreSQL
6. **Dashboard** displays real-time charts and statistics

---

## 🔮 Advanced Features

### Multiple Raspberry Pi Locations

Deploy collectors on multiple Raspberry Pis:

```yaml
# On each Pi, update docker-compose.raspberry-pi.yml
environment:
  - BACKEND_SERVER=http://main-server:8080
  - LOCATION_ID=greenhouse_1  # Unique identifier
```

### Authentication (Optional)

Add API token authentication:

```yaml
# Raspberry Pi
environment:
  - API_TOKEN=your-secure-token

# Backend: Add token validation in views.py
```

### Data Export

Export historical data:

```bash
# Via API
curl "http://localhost:8080/api/sensor-data/?device=sensor1&hours=24"

# Via database
docker exec irrigation-postgres pg_dump -U irrigation_user irrigation_db > backup.sql
```

---

## 📈 Performance Notes

### Expected Performance
- **Data collection**: 50-100 readings/hour per sensor
- **Network usage**: ~1KB per batch (25 readings)
- **Storage**: ~100MB per million readings
- **Dashboard response**: <2 seconds with 10,000+ readings

### Optimization Tips
- Increase `BATCH_SIZE` for slower networks
- Decrease `BATCH_INTERVAL` for more real-time updates  
- Use `MAX_RETRIES=1` on reliable networks
- Enable database indexing for large datasets

---

## 🆘 Support & Maintenance

### Backup Strategy
```bash
# Database backup
docker exec irrigation-postgres pg_dump -U irrigation_user irrigation_db > sensor_backup.sql

# Configuration backup
cp docker-compose*.yml /backup/location/
```

### Updates
```bash
# Update Raspberry Pi collector
docker pull your-registry/raspberry-sensor:latest
docker-compose -f docker-compose.raspberry-pi.yml up -d

# Update main server
docker-compose -f docker-compose-celery.yml pull
docker-compose -f docker-compose-celery.yml up -d
```

This distributed architecture provides a robust, scalable solution for your IoT sensor monitoring needs! 🎉