# 🌱 Smart Irrigation System API Documentation

A comprehensive REST API system for controlling Zigbee devices via MQTT for smart greenhouse irrigation management. Built with FastAPI and Django REST Framework, featuring automatic documentation, type hints, and async support.

## 📋 API Overview

This irrigation system provides two complementary API interfaces:

1. **FastAPI Service** (`irrigation_api.py`) - Real-time device control, sensor monitoring, and immediate irrigation operations
2. **Django Web API** (`django_webapp/`) - Irrigation planning, scheduling, and data management with web interface

Both APIs work together to provide complete smart greenhouse automation.

## 🚀 Quick Start

### Complete System Setup
```bash
# Start all services with Docker Compose
docker-compose up -d

# Or start individual services:
# 1. Start PostgreSQL database
docker-compose up -d postgres

# 2. Start MQTT broker  
docker-compose up -d mosquitto

# 3. Start Django web application
cd django_webapp
python manage.py runserver 0.0.0.0:8080

# 4. Start FastAPI service
python irrigation_api.py
```

### WSL Setup (Recommended for Development)
```bash
# In WSL2 Ubuntu
./run_api.sh           # Start FastAPI
./dev_server.sh        # Start Django web app
```

### Windows Setup
```cmd
# In Command Prompt or PowerShell
run_api.bat            # Start FastAPI
```

### Manual Installation
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/WSL
# OR
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements_django.txt

# Initialize database
python manage.py migrate

# Run the services
python irrigation_api.py    # FastAPI on port 8000
python manage.py runserver  # Django on port 8000
```

## 📡 API Endpoints

### FastAPI Service (Port 8000)

#### System Status & Health
- **GET** `/` - API home and status
- **GET** `/api/health` - Simple health check
- **GET** `/api/system/status` - Comprehensive system information
- **GET** `/api/devices` - List all configured Zigbee devices

#### Sensor Data
- **GET** `/api/sensor/temperature` - Get real-time temperature and humidity data from E6 sensor

#### Irrigation Control (Real-time)
- **POST** `/api/irrigation/control` - Turn irrigation ON/OFF immediately
  - Body: `{"action": "ON|OFF"}`
- **GET** `/api/irrigation/status` - Get current irrigation system status  
- **POST** `/api/irrigation/schedule` - Schedule immediate irrigation with automatic shutoff
  - Body: `{"duration": 30}` (seconds, max 3600)

#### Advanced Irrigation Status
- **GET** `/api/irrigation/schedule/status` - Get current schedule execution status

#### Irrigation Planning (Database)
- **GET** `/api/irrigation/plan` - Get all irrigation plans from database
- **POST** `/api/irrigation/plan` - Create new irrigation plan
  - Body: `{"scheduled_time": "2024-04-09T14:30:00", "duration": 1800, "description": "Evening watering"}`
- **PUT** `/api/irrigation/plan/{plan_id}` - Update specific irrigation plan
- **DELETE** `/api/irrigation/plan/{plan_id}` - Delete specific irrigation plan
- **PUT** `/api/irrigation/plan/{entry_id}` - Update plan entry (legacy endpoint)
- **DELETE** `/api/irrigation/plan/{entry_id}` - Delete plan entry (legacy endpoint)

### Django Web API (Port 8080)

#### Irrigation Plans Management
- **GET** `/api/plans/` - List all irrigation plans (RESTful endpoint)
  - Query parameters: `?status=pending&start_date=2024-04-01&end_date=2024-04-30`
- **POST** `/api/plans/` - Create new irrigation plan
- **GET** `/api/plans/{id}/` - Get specific irrigation plan
- **PUT** `/api/plans/{id}/` - Update irrigation plan
- **PATCH** `/api/plans/{id}/` - Partial update of irrigation plan
- **DELETE** `/api/plans/{id}/` - Delete irrigation plan

#### Django Admin Interface
- **Web UI** - `/admin/` - Django admin interface for managing plans, users, and system data
- **Web UI** - `/` - Django web interface for irrigation management

## 📖 Interactive Documentation

### FastAPI Automatic Documentation
FastAPI provides comprehensive interactive documentation:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Django REST Framework
Django provides browsable API interface:

- **API Root**: [http://localhost:8080/api/](http://localhost:8080/api/)
- **Admin Interface**: [http://localhost:8080/admin/](http://localhost:8080/admin/)
- **Web Interface**: [http://localhost:8080/](http://localhost:8080/)

These interfaces allow you to:
- Browse all endpoints with live testing
- See request/response schemas with validation
- Test API calls directly in the browser
- View detailed parameter information and examples
- Access Django's powerful admin interface for data management

## 🎯 Usage Examples

### FastAPI - Real-time Control

#### Control Irrigation
```bash
# Turn ON irrigation immediately
curl -X POST http://localhost:8000/api/irrigation/control \
  -H "Content-Type: application/json" \
  -d '{"action": "ON"}'

# Turn OFF irrigation 
curl -X POST http://localhost:8000/api/irrigation/control \
  -H "Content-Type: application/json" \
  -d '{"action": "OFF"}'
```

#### Schedule Immediate Irrigation
```bash
# Run for 30 seconds with automatic shutoff
curl -X POST http://localhost:8000/api/irrigation/schedule \
  -H "Content-Type: application/json" \
  -d '{"duration": 30}'

# Run for 15 minutes (900 seconds)
curl -X POST http://localhost:8000/api/irrigation/schedule \
  -H "Content-Type: application/json" \
  -d '{"duration": 900}'
```

#### Get Sensor Data
```bash
# Temperature and humidity data
curl http://localhost:8000/api/sensor/temperature

# System status
curl http://localhost:8000/api/system/status

# Health check
curl http://localhost:8000/api/health

# Device information
curl http://localhost:8000/api/devices
```

#### Irrigation Planning
```bash
# Create irrigation plan
curl -X POST http://localhost:8000/api/irrigation/plan \
  -H "Content-Type: application/json" \
  -d '{
    "scheduled_time": "2024-04-09T18:00:00",
    "duration": 1800,
    "description": "Evening watering - tomatoes",
    "timezone": "EEST"
  }'

# Get all plans
curl http://localhost:8000/api/irrigation/plan

# Update plan
curl -X PUT http://localhost:8000/api/irrigation/plan/plan_123 \
  -H "Content-Type: application/json" \
  -d '{
    "scheduled_time": "2024-04-09T19:00:00",
    "duration": 2400,
    "description": "Updated evening watering"
  }'

# Delete plan
curl -X DELETE http://localhost:8000/api/irrigation/plan/plan_123
```

### Django REST API - Data Management

#### Irrigation Plans CRUD
```bash
# List all plans with filtering
curl "http://localhost:8080/api/plans/?status=pending&start_date=2024-04-01"

# Create new plan
curl -X POST http://localhost:8080/api/plans/ \
  -H "Content-Type: application/json" \
  -d '{
    "scheduled_time": "2024-04-10T06:00:00+03:00",
    "duration": 1200,
    "description": "Morning watering cycle",
    "device": "0x540f57fffe890af8"
  }'

# Get specific plan
curl http://localhost:8080/api/plans/plan_1712234567_abc12345/

# Update plan (full update)
curl -X PUT http://localhost:8080/api/plans/plan_1712234567_abc12345/ \
  -H "Content-Type: application/json" \
  -d '{
    "scheduled_time": "2024-04-10T07:00:00+03:00", 
    "duration": 1500,
    "description": "Updated morning watering",
    "status": "pending"
  }'

# Partial update
curl -X PATCH http://localhost:8080/api/plans/plan_1712234567_abc12345/ \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'

# Delete plan
curl -X DELETE http://localhost:8080/api/plans/plan_1712234567_abc12345/
```

## 🧪 Testing

### Interactive Test Scripts
```bash
# FastAPI interactive testing
python test_api.py

# Django web interface testing  
python manage.py runserver
# Visit http://localhost:8080 for web interface

# MQTT communication testing
python test_mqtt_broker.py
python test_communication.py

# Full system integration testing
python test_decoupled_system.py
python test_api_timer_integration.py
```

### Automated Test Suite
```bash
# Run all tests
python -m pytest tests/

# Specific test categories
python test_irrigation.py           # Irrigation control tests
python test_temperature_dashboard.py # Temperature monitoring tests
python test_future_plan.py         # Scheduling tests
python test_immediate_status.py    # Real-time status tests
```

The interactive test script provides a menu-driven interface to:
- Test API connectivity and health across both services
- View automatic API documentation links
- Monitor sensor data in real-time
- Control irrigation system with validation
- Schedule automated watering cycles
- Test MQTT broker connectivity and message flow
- Validate database operations and plan management
```bash
python3 test_api.py
```

This provides a menu-driven interface to:
- Test API connectivity and health
- View automatic API documentation links
- Monitor sensor data in real-time
- Control irrigation system with validation
- Schedule automated watering cycles

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Smart Irrigation System                           │
└─────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────┐    ┌─────────────────┐
                    │   Web Browser   │    │   Mobile App    │
                    │   Dashboard     │    │   (Future)      │
                    └─────────────────┘    └─────────────────┘
                            │                       │
                            ▼                       ▼
                    ┌─────────────────────────────────────────┐
                    │          Django Web App                │
                    │     (Port 8080)                       │
                    │ • Web Interface                       │
                    │ • Django REST API                     │
                    │ • Admin Interface                     │
                    │ • Plan Management                     │
                    └─────────────────┬───────────────────────┘
                                     │
                    ┌─────────────────┴───────────────────────┐
                    │          PostgreSQL Database           │
                    │ • Irrigation Plans Storage            │
                    │ • User Management                     │
                    │ • Historical Data                     │
                    │ • System Configuration                │
                    └─────────────────┬───────────────────────┘
                                     │
                    ┌─────────────────┴───────────────────────┐
                    │           FastAPI Service              │
                    │         (Port 8000)                   │
                    │ • Real-time Control                   │
                    │ • Sensor Monitoring                   │
                    │ • MQTT Communication                  │
                    │ • Auto Documentation                  │
                    │ • Type Safety & Validation            │
                    └─────────────────┬───────────────────────┘
                                     │
                    ┌─────────────────┴───────────────────────┐
                    │          MQTT Broker                   │
                    │       (Mosquitto)                      │
                    │ • Message Routing                      │
                    │ • Device Management                    │
                    │ • zigbee2mqtt Integration              │
                    └─────────────────┬───────────────────────┘
                                     │
                    ┌─────────────────┴───────────────────────┐
                    │         Zigbee Network                 │
                    │                                       │
                    │ ┌─────────────┐  ┌─────────────────┐    │
                    │ │Temperature  │  │ Irrigation      │    │
                    │ │Sensor (E6)  │  │ Controller      │    │
                    │ │Nous A4C1383│  │ (R7060 Woox)    │    │
                    │ │91b14a3d1   │  │ 540f57fffe890af8│    │  
                    │ └─────────────┘  └─────────────────┘    │
                    └─────────────────────────────────────────┘
```

### Component Responsibilities

**Django Web App**: User interface, data management, authentication
**FastAPI Service**: Real-time device control, sensor data processing  
**PostgreSQL**: Persistent data storage for plans, users, history
**MQTT Broker**: Device communication hub with Zigbee network
**Zigbee Devices**: Physical sensors and actuators in greenhouse

## 📱 Device Configuration

### Zigbee Device Setup
The system is preconfigured for these specific devices:

**Temperature & Humidity Sensor**
- **Device**: E6 (Nous)
- **Zigbee ID**: `0xa4c138391b14a3d1`
- **MQTT Topic**: `zigbee2mqtt/0xa4c138391b14a3d1`
- **Functionality**: Real-time temperature, humidity, pressure monitoring

**Irrigation Controller** 
- **Device**: R7060 (Woox Smart Valve)
- **Zigbee ID**: `0x540f57fffe890af8` 
- **MQTT Topic**: `zigbee2mqtt/0x540f57fffe890af8`
- **Functionality**: Water valve control with timing and scheduling

### Network Configuration
- **MQTT Broker**: Raspberry Pi at `192.168.8.151:1883`
- **FastAPI Service**: `localhost:8000` (development) or `0.0.0.0:8000` (production)
- **Django Web App**: `localhost:8080` (development) or `0.0.0.0:8080` (production)
- **Database**: PostgreSQL at `postgres:5432` (Docker) or local instance

## 🔧 Configuration

### FastAPI Configuration
Edit `irrigation_api.py` to customize:
```python
# MQTT Configuration
MQTT_BROKER = "192.168.8.151"  # Your Raspberry Pi IP
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60

# Database Configuration
DB_URL = os.getenv("DATABASE_URL", 
    "postgresql://irrigation_user:irrigation_pass@postgres:5432/irrigation_db")

# Device Configuration
DEVICES = {
    "temperature_sensor": {
        "name": "0xa4c138391b14a3d1",
        "topic": "zigbee2mqtt/0xa4c138391b14a3d1",
        "type": "sensor"
    },
    "irrigation_controller": {
        "name": "0x540f57fffe890af8", 
        "topic": "zigbee2mqtt/0x540f57fffe890af8",
        "type": "actuator"
    }
}
```

### Django Configuration  
Edit `django_webapp/irrigation_web/settings.py`:
```python
# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'irrigation_db',
        'USER': 'irrigation_user', 
        'PASSWORD': 'irrigation_pass',
        'HOST': 'postgres',  # Docker service name
        'PORT': '5432',
    }
}

# API Configuration
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20
}
```

### Environment Variables
Create `.env` file:
```bash
# Database
DATABASE_URL=postgresql://irrigation_user:irrigation_pass@localhost:5432/irrigation_db

# MQTT
MQTT_BROKER_HOST=192.168.8.151
MQTT_BROKER_PORT=1883

# Django
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0

# FastAPI
FASTAPI_PORT=8000
FASTAPI_HOST=0.0.0.0
```

## 📊 Data Models

### FastAPI Pydantic Models

#### Irrigation Control
```python
# Immediate control request
{
  "action": "ON" | "OFF"
}

# Scheduling request  
{
  "duration": 1-3600  # seconds (max 1 hour)
}

# Planning request
{
  "scheduled_time": "2024-04-09T18:00:00",  # ISO format
  "duration": 1800,                          # seconds
  "description": "Evening watering",         # optional
  "timezone": "EEST"                         # optional, default UTC
}
```

#### API Response Structure
```python
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    "device": "0x540f57fffe890af8",
    "status": "ON",
    "timestamp": "2024-04-09T15:30:00.123Z",
    "duration": 1800
  },
  "timestamp": "2024-04-09T15:30:00.123Z"
}
```

#### Sensor Data Response
```python
{
  "temperature": 24.5,      # Celsius
  "humidity": 65.2,         # Percentage
  "pressure": 1013.25,      # hPa (if available)
  "battery": 85,            # Percentage
  "linkquality": 120,       # Signal strength
  "last_seen": "2024-04-09T15:29:45.000Z"
}
```

### Django REST Models

#### Irrigation Plan
```python
{
  "id": "plan_1712234567_abc12345",
  "scheduled_time": "2024-04-09T18:00:00+03:00", 
  "duration": 1800,
  "description": "Evening watering cycle",
  "device": "0x540f57fffe890af8",
  "status": "pending",      # pending, executing, completed, failed, cancelled
  "created_at": "2024-04-09T12:00:00+03:00",
  "updated_at": "2024-04-09T12:30:00+03:00",
  "executed_at": null,      # Set when execution starts
  "result": null,           # Execution result message
  "duration_minutes": 30,   # Computed field
  "is_overdue": false,      # Computed field
  "device_display": "Woox R7060 Irrigation Controller"
}
```

#### List Response with Pagination
```python
{
  "count": 25,
  "next": "http://localhost:8080/api/plans/?page=2",
  "previous": null,
  "results": [
    {
      "id": "plan_1712234567_abc12345",
      "scheduled_time": "2024-04-09T18:00:00+03:00",
      "duration": 1800,
      "status": "pending",
      ...
    }
  ]
}
```

### Device Status Models
```python
# Temperature Sensor Status
{
  "temperature": 24.5,
  "humidity": 65.2,
  "pressure": 1013.25,
  "battery": 85,
  "voltage": 3.1,
  "linkquality": 120,
  "last_seen": "2024-04-09T15:29:45.000Z"
}

# Irrigation Controller Status  
{
  "state": "OFF",            # ON, OFF
  "position": 0,             # 0-100 (valve position)
  "battery": 78,
  "linkquality": 95,
  "last_seen": "2024-04-09T15:29:50.000Z"
}
```

## 🛡️ Error Handling & Status Codes

### FastAPI Error Handling
FastAPI provides comprehensive error handling with detailed responses:

#### HTTP Status Codes
- `200` - Success
- `201` - Created (new irrigation plan)
- `400` - Bad Request (invalid parameters, validation errors)
- `404` - Not Found (device unavailable, plan not found)
- `422` - Unprocessable Entity (Pydantic validation failure)
- `500` - Internal Server Error (MQTT connection, database issues)
- `503` - Service Unavailable (MQTT broker offline)

#### Error Response Format
```python
{
  "success": false,
  "message": "Detailed error description",
  "data": {
    "error_type": "ValidationError",
    "error_code": "INVALID_DURATION", 
    "details": {
      "field": "duration",
      "value": 7200,
      "constraint": "Maximum 3600 seconds (1 hour)"
    }
  },
  "timestamp": "2024-04-09T15:30:00.123Z"
}
```

### Django REST Framework Error Handling

#### HTTP Status Codes  
- `200` - Success (GET, PUT, PATCH)
- `201` - Created (POST)
- `204` - No Content (DELETE)
- `400` - Bad Request (invalid data)
- `401` - Unauthorized (authentication required)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (plan doesn't exist)
- `409` - Conflict (scheduling conflict)

#### Error Response Format
```python
{
  "detail": "Not found.",
  "field_errors": {
    "scheduled_time": ["This field is required."],
    "duration": ["Ensure this value is greater than 0."]
  }
}
```

### Common Error Scenarios

#### MQTT Connection Issues
```python
# Error when MQTT broker is unavailable
{
  "success": false,
  "message": "Unable to control irrigation: MQTT broker not connected",
  "data": {
    "error_type": "ConnectionError",
    "broker": "192.168.8.151:1883",
    "last_attempt": "2024-04-09T15:30:00.123Z"
  }
}
```

#### Device Communication Errors
```python
# Error when Zigbee device doesn't respond
{
  "success": false,
  "message": "Device communication timeout",
  "data": {
    "error_type": "DeviceTimeout",
    "device_id": "0x540f57fffe890af8",
    "last_seen": "2024-04-09T14:25:00.123Z",
    "timeout_duration": "5 minutes"
  }
}
```

#### Validation Errors
```python
# Invalid duration in scheduling request
{
  "success": false,
  "message": "Validation error in request data",
  "data": {
    "error_type": "ValidationError",
    "errors": [
      {
        "field": "duration",
        "message": "Duration must be between 1 and 3600 seconds",
        "value": 7200
      }
    ]
  }
}
```

### Logging & Debugging
Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# FastAPI logs include:
# - MQTT connection status
# - Device communication attempts  
# - API request/response details
# - Database operation results
# - Scheduling system events
```

## 🚀 Performance & Features

### FastAPI Performance Features
- **Async/await support** for better concurrency and non-blocking operations
- **Automatic request/response validation** with Pydantic models
- **Built-in API versioning** and OpenAPI 3.0 compliance
- **Optimized JSON serialization** with type safety
- **Background tasks** for long-running irrigation schedules
- **WebSocket support** for real-time sensor data streaming (future feature)
- **Dependency injection** for efficient resource management

### Django Features
- **Django ORM** for robust database operations with migrations
- **Django REST Framework** for standardized API development
- **Admin interface** for system management and debugging
- **User authentication** and permission system
- **Template system** for web interface
- **Middleware support** for cross-cutting concerns
- **Built-in pagination** and filtering for large datasets

### Database Performance
- **PostgreSQL** for ACID compliance and complex queries
- **Database connection pooling** in production
- **Automated migrations** with Django
- **Indexing** on frequently queried fields (scheduled_time, status, device)
- **Query optimization** for irrigation plan retrieval

### MQTT Performance
- **Persistent connections** with automatic reconnection
- **Message queuing** for reliable device communication
- **Topic-based routing** for efficient message filtering
- **Quality of Service (QoS)** levels for guaranteed delivery

## 🧪 Development Environment

### WSL2 Development (Recommended)
Perfect for WSL2 Ubuntu development with Windows integration:

```bash
# In WSL Ubuntu terminal
cd /mnt/c/Users/[username]/repos/bakalaurs

# Start FastAPI development server
./run_api.sh
# Access from Windows: http://localhost:8000/docs

# Start Django development server  
./dev_server.sh
# Access from Windows: http://localhost:8080

# Start complete system with Docker Compose
docker-compose up -d
```

### Docker Development
```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f fastapi
docker-compose logs -f django
docker-compose logs -f postgres

# Stop all services
docker-compose down
```

### Hot Reload & Development Features
- **FastAPI**: Automatic reload on code changes with `uvicorn --reload`
- **Django**: Development server with auto-reload and debug toolbar
- **Docker**: Volume mounting for live code updates
- **Database**: Persistent volumes for development data retention

## 🚀 Deployment Guide

### Production Deployment Options

#### 1. Docker Compose Production
```bash
# Use production configuration
docker compose -f docker/docker-compose.yml up -d

# Or for Raspberry Pi deployment
docker-compose -f docker-compose.raspberry-pi.yml up -d
```

#### 2. Individual Service Deployment

**FastAPI Service**
```bash
# Install production WSGI server
pip install gunicorn uvloop httptools

# Run with Gunicorn + Uvicorn workers
gunicorn irrigation_api:app -w 4 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

**Django Web Application**
```bash
# Collect static files
python manage.py collectstatic --noinput

# Run database migrations
python manage.py migrate

# Create superuser for admin
python manage.py createsuperuser

# Run with Gunicorn
gunicorn irrigation_web.wsgi:application \
  --bind 0.0.0.0:8080 \
  --workers 3
```

#### 3. Raspberry Pi Deployment
```bash
# Use provided setup scripts
./setup_raspberry_pi.sh           # Complete system setup
./setup_server_timing.sh          # Timer service setup
./install_docker_raspberry_pi.sh  # Docker installation

# Quick deployment
./deploy_timer.sh                  # Deploy timer service only
```

### Environment-Specific Configurations

#### Production Environment Variables
```bash
# .env.production
DEBUG=False
DATABASE_URL=postgresql://user:pass@db-server:5432/irrigation_prod
MQTT_BROKER_HOST=192.168.1.100
ALLOWED_HOSTS=irrigation.yourdomain.com,192.168.1.100
SECRET_KEY=your-super-secure-production-key

# SSL/HTTPS Configuration
SECURE_SSL_REDIRECT=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
```

#### Nginx Reverse Proxy (Recommended)
```nginx
# /etc/nginx/sites-available/irrigation-api
server {
    listen 80;
    server_name your-domain.com;

    # FastAPI service
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Django web app
    location / {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Static files
    location /static/ {
        alias /path/to/irrigation/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### Security Considerations

#### Production Security Checklist
- [ ] Change default database passwords
- [ ] Set up HTTPS with SSL certificates
- [ ] Configure firewall rules (allow only necessary ports)
- [ ] Enable Django security middleware
- [ ] Set up MQTT authentication if needed
- [ ] Regular database backups
- [ ] Monitor system logs and implement log rotation
- [ ] Use environment variables for sensitive data
- [ ] Implement rate limiting on API endpoints

## 🎓 Bachelor's Thesis Integration

This smart irrigation system API provides a comprehensive foundation for the academic project:

### Technical Excellence
- **Professional-grade API architecture** with industry-standard practices
- **Comprehensive documentation** with interactive testing interfaces
- **Full-stack implementation** from hardware devices to web interfaces
- **Modular design** allowing for future enhancements and scaling
- **Modern development practices** including containerization and CI/CD readiness

### Academic Value
- **Real-world application** solving actual greenhouse management challenges
- **Integration of multiple technologies**: IoT, web development, databases, MQTT
- **Scalable architecture** demonstrating software engineering principles
- **Complete system lifecycle** from sensor data to user interfaces
- **Documentation and testing** following industry best practices

### Research Contributions
- **IoT device integration** with Zigbee and MQTT protocols
- **Real-time monitoring** and automated control systems
- **Web-based management** with RESTful API design
- **Database-driven scheduling** for agricultural automation
- **Cross-platform deployment** supporting various environments

### Future Development Opportunities
- **Machine learning integration** for intelligent irrigation scheduling
- **Weather API integration** for enhanced decision making
- **Mobile application** development using existing APIs
- **Multi-greenhouse management** with expanded device support
- **Energy optimization** and sustainability features

## 📚 Additional Documentation

### Related Documentation Files
- [`README.md`](README.md) - Project overview and academic information
- [`MQTT_GUIDE.md`](MQTT_GUIDE.md) - MQTT broker setup and configuration
- [`RASPBERRY_PI_DEPLOYMENT_GUIDE.md`](RASPBERRY_PI_DEPLOYMENT_GUIDE.md) - Raspberry Pi specific deployment
- [`TEMPERATURE_DASHBOARD_SETUP.md`](TEMPERATURE_DASHBOARD_SETUP.md) - Monitoring dashboard setup
- [`CELERY_MIGRATION.md`](CELERY_MIGRATION.md) - Task queue system migration guide
- [`NODE_RED_SETUP.md`](NODE_RED_SETUP.md) - Visual programming interface setup

### API Testing Files
- [`test_api.py`](test_api.py) - Interactive API testing script
- [`test_irrigation.py`](test_irrigation.py) - Irrigation system tests
- [`test_temperature_dashboard.py`](test_temperature_dashboard.py) - Temperature monitoring tests
- [`test_api_timer_integration.py`](test_api_timer_integration.py) - Integration tests

### Deployment Scripts
- [`setup_complete_system.ps1`](setup_complete_system.ps1) - Complete Windows setup
- [`setup_raspberry_pi.sh`](setup_raspberry_pi.sh) - Raspberry Pi deployment
- [`run_api.sh`](run_api.sh) / [`run_api.bat`](run_api.bat) - Quick API startup
- [`dev_server.sh`](dev_server.sh) - Development server startup

## 🔗 Quick Links

- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Django Admin**: [http://localhost:8080/admin/](http://localhost:8080/admin/)
- **Django Web Interface**: [http://localhost:8080/](http://localhost:8080/)
- **Django REST API**: [http://localhost:8080/api/](http://localhost:8080/api/)

## 📞 Support & Contributing

This project is part of a bachelor's thesis at Riga Technical University. For questions or contributions:

- **Author**: Jānis Sīpols
- **Institution**: RTU Faculty of Computer Science, Information Technology and Energy
- **Project**: Smart Greenhouse System for Tomato Growing

### Getting Help
1. Check the interactive documentation at `/docs` endpoints
2. Review test files for usage examples
3. Examine the setup scripts for configuration guidance
4. Use the provided test interfaces for debugging

---

*This API documentation supports the bachelor's thesis: "Smart Greenhouse System Development for Tomato Growing" - demonstrating modern software engineering practices in agricultural IoT applications.*
- **Type-safe data handling** for research accuracy
- **Comprehensive logging** for thesis analysis
- **Real-time monitoring** of irrigation systems
- **Scalable architecture** for future enhancements
- **Standards compliance** (OpenAPI, REST, JSON)

The automatic documentation at `/docs` is perfect for demonstrating your API capabilities in your thesis presentation!