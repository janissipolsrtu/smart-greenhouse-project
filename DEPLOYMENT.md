# Deployment Guide - Smart Greenhouse Irrigation System

## Prerequisites

- Docker and Docker Compose installed
- WSL2 (for Windows development)
- At least 4GB RAM available for containers

## System Architecture

The irrigation system consists of the following services:

- **PostgreSQL Database** - Data storage for irrigation plans and user management
- **Redis Cache** - Message broker for Celery task queue  
- **FastAPI Service** - REST API for device control and monitoring (port 8000)
- **Django Web App** - Web interface for system management (port 8080)
- **Celery Worker** - Background task processing (irrigation execution)
- **Celery Beat** - Scheduled task management (irrigation scheduling)
- **Flower** - Task monitoring interface (port 5555)
- **MQTT Broker** - Communication with IoT devices (port 1883)

## Quick Start

### 1. Start All Services
```bash
cd docker
docker compose up -d
```

### 2. Check Service Status
```bash
docker compose ps
```

### 3. View Service Logs
```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f irrigation-api
```

## Management Commands

### Start/Stop Services
```bash
# Start all services
docker compose up -d

# Stop all services  
docker compose down

# Restart all services
docker compose restart

# Start specific services
docker compose up -d postgres redis mosquitto irrigation-api
```

### Individual Service Management
```bash
# Restart specific service
docker compose restart irrigation-api

# View service status
docker compose ps irrigation-api

# Follow logs for specific service
docker compose logs -f django-webapp
```

### Database Operations
```bash
# Run Django migrations
docker compose exec django-webapp python manage.py migrate

# Create Django superuser
docker compose exec django-webapp python manage.py createsuperuser

# Access database directly
docker compose exec postgres psql -U irrigation_user -d irrigation_db
```

## Access Points

Once services are running, access the following interfaces:

| Service | URL | Description |
|---------|-----|-------------|
| FastAPI Documentation | http://localhost:8000/docs | Interactive API documentation |
| FastAPI Alternative Docs | http://localhost:8000/redoc | Alternative API documentation |
| Django Web Interface | http://localhost:8080 | Main web application |
| Django Admin | http://localhost:8080/admin | Administrative interface |
| Flower Monitoring | http://localhost:5555 | Celery task monitoring |
| MQTT Broker | localhost:1883 | IoT device communication |

## Development Workflow

### 1. Code Changes
The setup uses volume mounts for development:
- FastAPI code: `./src` → `/app`  
- Django code: `./web` → `/app`
- Automatic reload on file changes

### 2. Rebuild After Dependencies Change
```bash
# Rebuild specific service
docker compose build irrigation-api

# Rebuild all services  
docker compose build

# Rebuild and restart
docker compose up -d --build
```

### 3. Clean Restart
```bash
# Stop and remove containers
docker compose down

# Remove volumes (⚠️ deletes database data)
docker compose down -v

# Start fresh
docker compose up -d
```

## Troubleshooting

### Check Service Health
```bash
# Overall status
docker compose ps

# Check if services are responding
curl -s -o /dev/null -w 'FastAPI: %{http_code}\n' http://localhost:8000/
curl -s -o /dev/null -w 'Django: %{http_code}\n' http://localhost:8080/
curl -s -o /dev/null -w 'Flower: %{http_code}\n' http://localhost:5555/
```

### Common Issues

**Port Conflicts:**
```bash
# Check what's using ports
netstat -tulpn | grep :8000
netstat -tulpn | grep :8080
netstat -tulpn | grep :5555
```

**Database Connection Issues:**
```bash
# Check PostgreSQL logs
docker compose logs postgres

# Test database connectivity
docker compose exec postgres pg_isready -U irrigation_user
```

**Service Won't Start:**
```bash
# Check logs for errors
docker compose logs [service-name]

# Rebuild problematic service
docker compose build [service-name]
```

**Reset Everything:**
```bash
# Nuclear option - removes everything
docker compose down
docker system prune -a
docker volume prune
docker compose up -d
```

## Production Deployment

For production deployment:

1. Update environment variables in `docker-compose.yml`
2. Set `DEBUG=False` for Django 
3. Configure proper SECRET_KEY
4. Set up SSL/TLS certificates  
5. Configure proper MQTT broker settings
6. Set up monitoring and logging

## File Structure

```
docker/
├── docker-compose.yml          # Main production configuration
├── Dockerfile                  # FastAPI service
├── Dockerfile.django          # Django web app  
├── Dockerfile.celery          # Celery services
└── [other Dockerfiles...]     # Specialized services
```

## Advanced Configuration

### Environment Variables

Key environment variables that can be configured in `docker-compose.yml`:

```yaml
environment:
  - POSTGRES_DB=irrigation_db
  - POSTGRES_USER=irrigation_user
  - POSTGRES_PASSWORD=irrigation_pass
  - DJANGO_SECRET_KEY=your-secret-key
  - DEBUG=False  # Set to False for production
  - CELERY_BROKER_URL=redis://redis:6379/0
  - MQTT_BROKER=mosquitto  # Internal broker
```

### Scaling Services

Scale specific services for high load:

```bash
# Scale Celery workers
docker compose up -d --scale celery-worker=3

# Scale FastAPI instances (requires load balancer)
docker compose up -d --scale irrigation-api=2
```

### Monitoring and Logs

Monitor system resources:

```bash
# Check resource usage
docker stats

# Monitor specific service
docker stats irrigation-api

# Save logs to file
docker compose logs --no-color > system.log 2>&1
```

### Backup and Restore

Database backup:

```bash
# Create backup
docker compose exec postgres pg_dump -U irrigation_user irrigation_db > backup.sql

# Restore backup
docker compose exec -T postgres psql -U irrigation_user -d irrigation_db < backup.sql
```

### Security Considerations

For production deployment:

1. **Change default passwords** in environment variables
2. **Use secrets management** for sensitive data
3. **Enable firewall** and limit port exposure 
4. **Set up SSL/TLS** for web interfaces
5. **Configure MQTT authentication** for device communication
6. **Regular security updates** for base images
7. **Monitor logs** for suspicious activity