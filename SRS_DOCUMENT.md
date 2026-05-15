# Software Requirements Specification (SRS)
## Smart Greenhouse Irrigation System

**Document Version:** 1.0  
**Last Updated:** May 14, 2026  
**Project:** Bachelor Thesis - RTU Smart Greenhouse Automation  
**Author:** Development Team  
**Status:** Active Development

---

## Table of Contents
1. [Introduction](#introduction)
2. [Overall Description](#overall-description)
3. [System Features & Functional Requirements](#system-features--functional-requirements)
4. [Non-Functional Requirements](#non-functional-requirements)
5. [External Interface Requirements](#external-interface-requirements)
6. [System Architecture](#system-architecture)
7. [Deployment Requirements](#deployment-requirements)
8. [Data Requirements](#data-requirements)

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements for the **Smart Greenhouse Irrigation System** - an IoT-enabled automated irrigation management platform designed for tomato greenhouse cultivation. The system provides intelligent monitoring, scheduling, and control of irrigation devices with real-time sensor data collection and visualization.

### 1.2 Document Scope
This SRS covers all features, functionalities, and constraints of the Smart Greenhouse Irrigation System, including:
- Web and API interfaces
- Irrigation scheduling and execution
- Sensor monitoring
- Device management
- Multi-greenhouse support
- Real-time monitoring and visualization

### 1.3 Project Context
- **Target Users:** Greenhouse operators, agricultural technicians, farm managers
- **Deployment Environments:** Docker containers, Raspberry Pi, WSL2 development
- **Primary Language:** English
- **Development Status:** MVP with active feature development

---

## 2. Overall Description

### 2.1 System Purpose
The Smart Greenhouse Irrigation System automates irrigation management in greenhouses by:
- Collecting real-time environmental data from IoT sensors
- Scheduling and executing irrigation tasks based on predefined plans
- Providing manual control capabilities for immediate interventions
- Visualizing sensor data and system status through dashboards
- Managing multiple greenhouse facilities from a unified interface

### 2.2 User Classes & Characteristics

| User Class | Description | Primary Tasks |
|-----------|-------------|---------------|
| **Greenhouse Operator** | Daily greenhouse management personnel | Monitor sensors, execute manual irrigation, view dashboards |
| **Farm Manager** | Senior management overseeing multiple greenhouses | Create watering plans, manage greenhouse configurations, review schedules |
| **Agricultural Technician** | Technical personnel for system maintenance | Device pairing, sensor configuration, troubleshooting |
| **System Administrator** | IT personnel managing infrastructure | Deployment, backups, user access control, system monitoring |

### 2.3 Operating Environment
```
Production:
- Docker Compose (8+ containerized services)
- PostgreSQL 15 + TimescaleDB
- Redis for message broker
- Mosquitto MQTT broker (typically Raspberry Pi)
- Zigbee2MQTT bridge for device communication

Development:
- WSL2 on Windows
- Local Python virtual environments (FastAPI, Django)
- Docker Compose for full stack testing
```

### 2.4 Key Constraints & Assumptions

| Item | Description |
|------|-------------|
| **Connectivity** | MQTT broker must be accessible from all services; assumes stable network |
| **Device Availability** | Zigbee devices must be within range of Raspberry Pi bridge (typical 100m range) |
| **Data Persistence** | PostgreSQL must be available; Redis optional but recommended for production |
| **Time Accuracy** | System clock synchronization required for scheduling accuracy |
| **User Knowledge** | Users assumed to have basic understanding of greenhouse operations |

---

## 3. System Features & Functional Requirements

### 3.1 Irrigation Management Feature

#### 3.1.1 Watering Plans
**FR-IR-01: Create Watering Plan**
- User shall be able to create a new watering plan with name, description, and target greenhouse
- Each plan shall serve as a container for multiple watering cycles
- Plan creation shall be available via web interface and REST API
- Status: ACTIVE/INACTIVE switchable

**FR-IR-02: View Watering Plans**
- User shall be able to list all watering plans for accessible greenhouses
- Each plan shall display total associated cycles, status, and creation date
- Plans shall be sortable and filterable by greenhouse and status

**FR-IR-03: Update Watering Plan**
- User shall be able to modify plan name, description, and status
- Changes shall take effect for future cycle executions
- Plan modifications shall be audited with timestamp

**FR-IR-04: Delete Watering Plan**
- User shall be able to delete plans (cascading to cycles if specified)
- System shall warn about dependent cycles before deletion
- Deleted plans shall be archived in audit logs

#### 3.1.2 Watering Cycles
**FR-IR-05: Create Watering Cycle**
- User shall create watering cycles within a plan
- Each cycle requires: name, execution time (HH:MM format), duration (minutes), description, target device
- Cycles shall support multiple devices for grouped irrigation
- System shall validate no scheduling conflicts

**FR-IR-06: View Watering Cycles**
- User shall view all cycles in a plan with status (PENDING, EXECUTING, COMPLETED, FAILED, CANCELLED)
- Display shall show cycle schedule, last execution time, next execution time
- Cycles shall be grouped by schedule frequency

**FR-IR-07: Update Watering Cycle**
- User shall modify cycle timing, duration, device target, and description
- Modifications shall take effect from next scheduled execution
- Current active cycle execution shall not be interrupted

**FR-IR-08: Delete Watering Cycle**
- User shall delete individual cycles from a plan
- System shall confirm deletion if cycle is scheduled within 24 hours
- Deletion shall not affect past execution records

**FR-IR-09: Monitor Cycle Execution**
- System shall track cycle execution status in real-time
- Display shall show: start time, end time, success/failure status, error messages
- User shall see estimated time of next cycle execution
- System shall log execution duration and water usage metrics

**FR-IR-10: Execute Watering Cycle**
- Celery Beat scheduler shall check for due cycles every 30 seconds
- Due cycles shall be queued to irrigation_execution task queue
- Celery workers shall execute queued tasks asynchronously
- System shall send MQTT command to irrigation device with duration parameter

#### 3.1.3 Manual Irrigation Control
**FR-IR-11: Immediate Device Control**
- User shall send immediate ON/OFF commands to irrigation devices
- User shall specify duration (in seconds or minutes) for ON commands
- System shall immediately publish MQTT command to device
- User shall receive confirmation of command transmission status

**FR-IR-12: Manual Control Audit Trail**
- Each manual operation shall be logged with: user, timestamp, device, command, status
- User shall view history of manual controls in dashboard
- Audit logs shall be retained for compliance purposes

#### 3.1.4 Detailed REQ List (Irrigation Management)

The following list refines irrigation requirements into implementation-ready REQ items.

| REQ ID | Area | Requirement Statement | Priority | Acceptance Criteria |
|--------|------|-----------------------|----------|---------------------|
| REQ-IR-PLAN-001 | Plans | System shall require `name` and `greenhouse_id` when creating a watering plan. | Must | API/Web rejects missing fields with validation error; valid payload creates plan. |
| REQ-IR-PLAN-002 | Plans | System shall enforce unique plan names per greenhouse (case-insensitive). | Must | Duplicate name in same greenhouse returns conflict; same name in different greenhouse is allowed. |
| REQ-IR-PLAN-003 | Plans | Plan status shall support `ACTIVE` and `INACTIVE` only. | Must | Invalid status values are rejected with clear error message. |
| REQ-IR-PLAN-004 | Plans | System shall prevent activation of a plan with zero active cycles. | Should | Activation attempt returns business-rule error unless at least one active cycle exists. |
| REQ-IR-PLAN-005 | Plans | System shall support soft delete for plans and retain audit metadata. | Must | Deleted plan not shown in default list, but recoverable in admin/audit view. |
| REQ-IR-PLAN-006 | Plans | Plan list shall be filterable by greenhouse, status, and text search on plan name. | Should | API and UI filters produce consistent result sets. |
| REQ-IR-PLAN-007 | Plans | System shall expose plan summary fields: total cycles, active cycles, next run time, last run status. | Should | Summary fields visible in API response and dashboard. |
| REQ-IR-CYCLE-001 | Cycles | System shall require `plan_id`, `name`, `start_time`, `duration_seconds`, and `device_ids` for cycle creation. | Must | Missing any required field returns validation error. |
| REQ-IR-CYCLE-002 | Cycles | System shall validate cycle `start_time` as `HH:MM` 24-hour format in greenhouse local timezone. | Must | Invalid format rejected; stored value normalized. |
| REQ-IR-CYCLE-003 | Cycles | System shall enforce duration bounds: minimum 10 seconds, maximum 3600 seconds. | Must | Values outside bounds are rejected. |
| REQ-IR-CYCLE-004 | Cycles | System shall support multi-device cycles where all selected devices are irrigation-capable and online-configured. | Must | Non-irrigation device inclusion fails validation. |
| REQ-IR-CYCLE-005 | Cycles | System shall detect overlapping cycles per device and block conflicts unless override flag is explicitly allowed for admin role. | Must | Conflict returns details of conflicting cycle(s). |
| REQ-IR-CYCLE-006 | Cycles | System shall allow cycle frequency modes: `DAILY`, `WEEKLY`, `CUSTOM_DAYS`. | Must | Invalid frequency values rejected; schedule preview generated for valid input. |
| REQ-IR-CYCLE-007 | Cycles | For `WEEKLY` and `CUSTOM_DAYS`, at least one weekday shall be selected. | Must | Save is blocked when weekday set is empty. |
| REQ-IR-CYCLE-008 | Cycles | System shall allow temporary cycle pause without deleting definition. | Should | Paused cycle excluded from execution checks and marked in UI/API. |
| REQ-IR-CYCLE-009 | Cycles | Updating cycle schedule shall apply only to future executions; in-progress run shall continue unchanged. | Must | Edit during execution does not alter currently running command duration. |
| REQ-IR-CYCLE-010 | Cycles | Deleting a cycle shall retain historical execution records linked to cycle ID. | Must | Past logs remain queryable after cycle deletion. |
| REQ-IR-CYCLE-011 | Cycles | System shall provide `next_run_at` computation for each active cycle. | Must | `next_run_at` updates after every execution and after schedule edits. |
| REQ-IR-CYCLE-012 | Cycles | System shall support optional `max_runs_per_day` safety cap per cycle. | Should | Scheduler skips executions exceeding cap and records reason. |
| REQ-IR-CYCLE-013 | Cycles | System shall support optional weather/sensor guard conditions (for example soil moisture threshold) when enabled by greenhouse features. | Could | Guard-enabled cycle executes only when condition evaluates true. |
| REQ-IR-EXEC-001 | Execution | Scheduler shall scan for due cycles every 30 seconds (+/- 5 seconds tolerance). | Must | Monitoring logs show periodic checks within tolerance. |
| REQ-IR-EXEC-002 | Execution | Due cycle shall transition through statuses: `PENDING -> QUEUED -> EXECUTING -> COMPLETED/FAILED/CANCELLED`. | Must | Status transitions recorded and visible in execution timeline. |
| REQ-IR-EXEC-003 | Execution | Execution worker shall publish MQTT `ON` command and then ensure `OFF` command is sent at end of duration. | Must | Both commands present in message logs for successful run. |
| REQ-IR-EXEC-004 | Execution | If `ON` publish succeeds but `OFF` publish fails, system shall retry `OFF` up to 3 times and raise critical alert. | Must | Retry attempts and final outcome stored in execution record. |
| REQ-IR-EXEC-005 | Execution | System shall enforce idempotency for execution dispatch to avoid duplicate run for the same cycle window. | Must | Duplicate scheduler triggers do not produce duplicate irrigation action. |
| REQ-IR-EXEC-006 | Execution | Execution task shall timeout if device acknowledgment is not received within configured threshold. | Should | Timeout marks run as failed with reason `ack_timeout`. |
| REQ-IR-EXEC-007 | Execution | Failed executions shall be retried according to retry policy (max 3, exponential backoff) only if failure reason is transient. | Must | Permanent validation errors are not retried; transient transport errors are retried. |
| REQ-IR-EXEC-008 | Execution | System shall capture per-run telemetry: start/end timestamps, duration, device list, MQTT topic, result code, error text. | Must | Execution detail endpoint returns all telemetry fields. |
| REQ-IR-EXEC-009 | Execution | System shall expose run history filtered by plan, cycle, device, date range, and status. | Should | Filters combine correctly and pagination is stable. |
| REQ-IR-EXEC-010 | Execution | Concurrency control shall prevent same device from being commanded by two runs simultaneously. | Must | Second conflicting run is queued or rejected based on policy. |
| REQ-IR-MAN-001 | Manual Control | System shall provide manual `ON`, `OFF`, and `PULSE(duration)` operations per irrigation device. | Must | API/UI offers all three actions with proper input validation. |
| REQ-IR-MAN-002 | Manual Control | Manual operations shall require explicit greenhouse context and operator authorization. | Must | Unauthorized requests return 403 and are audited. |
| REQ-IR-MAN-003 | Manual Control | Manual `ON` and `PULSE` shall require duration with bounds identical to scheduled cycle duration limits. | Must | Out-of-range duration values are rejected. |
| REQ-IR-MAN-004 | Manual Control | Manual `OFF` shall be allowed even when no active run exists (idempotent safe-stop). | Must | Command accepted and logged as no-op when already off. |
| REQ-IR-MAN-005 | Manual Control | Manual command shall be blocked by default when a scheduled run is actively controlling the same device, unless user has override permission. | Must | Conflict response indicates active run ID and override requirements. |
| REQ-IR-MAN-006 | Manual Control | Emergency stop action shall stop all active irrigation devices in selected greenhouse within 5 seconds. | Must | Test scenario confirms stop command dispatch to all active devices within SLA. |
| REQ-IR-MAN-007 | Manual Control | Every manual command shall include user ID, request source (API/UI), and correlation ID for traceability. | Should | Audit record contains required metadata fields. |
| REQ-IR-MAN-008 | Manual Control | Manual control history shall be searchable by user, device, action type, and time range. | Should | Query endpoint returns consistent filtered history. |
| REQ-IR-OBS-001 | Observability | System shall emit structured logs for schedule checks, dispatch decisions, MQTT publish results, and retries. | Must | Logs contain event type, timestamps, IDs, and outcome status. |
| REQ-IR-OBS-002 | Observability | System shall expose metrics: due cycles, success rate, failed runs, average duration, command latency. | Should | Metrics endpoint/dashboard shows real-time and historical values. |
| REQ-IR-OBS-003 | Observability | Critical failures (for example repeated OFF command failures) shall generate operator alert events. | Must | Alert event appears in UI and alert stream with severity `CRITICAL`. |
| REQ-IR-AUD-001 | Audit | Plan, cycle, and manual-control changes shall be audit-logged with before/after values. | Must | Audit entry stores entity type, entity ID, actor, diff, and timestamp. |
| REQ-IR-AUD-002 | Audit | Audit records shall be immutable to non-admin roles. | Must | Non-admin update/delete attempts are denied and logged. |
| REQ-IR-AUD-003 | Audit | Audit retention for irrigation operations shall be minimum 24 months. | Should | Retention job preserves records for configured window. |
| REQ-IR-SEC-001 | Security | All irrigation-modifying operations shall require authenticated user and CSRF protection for web forms. | Must | Unauthenticated requests are rejected; CSRF failures blocked. |
| REQ-IR-SEC-002 | Security | System shall apply role-based permissions: operator (execute), manager (configure plans/cycles), admin (override/conflict bypass). | Must | Permission matrix enforced consistently across API and UI. |
| REQ-IR-SEC-003 | Security | Sensitive connection details used during execution (MQTT credentials) shall never appear in API responses or logs. | Must | Security test verifies redaction in logs and responses. |
| REQ-IR-DATA-001 | Data Integrity | Deleting greenhouse shall be blocked if active irrigation runs exist. | Must | Attempt fails with explanatory dependency error. |
| REQ-IR-DATA-002 | Data Integrity | System shall ensure referential integrity between plan, cycle, device mapping, and execution logs. | Must | Integrity constraints prevent orphan records in normal operations. |
| REQ-IR-DATA-003 | Data Integrity | System clock drift larger than configurable threshold shall suspend new cycle dispatch and raise warning. | Could | Drift detection event logged; execution resumes after clock healthy. |

#### 3.1.5 Irrigation Requirement Traceability Seeds

| Source Requirement | Implementation Anchor |
|--------------------|-----------------------|
| REQ-IR-EXEC-001 | Celery Beat schedule interval configuration |
| REQ-IR-EXEC-003 | MQTT command publisher and device command topic schema |
| REQ-IR-EXEC-007 | Celery retry policy and error classification |
| REQ-IR-MAN-006 | Emergency stop endpoint and bulk device command service |
| REQ-IR-AUD-001 | Audit log model and middleware/service hook |

---

### 3.2 Plant Management Feature

#### 3.2.1 Plant Registration
**FR-PM-01: Register Plant**
- User shall register plants with: name, variety, planting date, estimated harvest date
- Plants shall be associated with a greenhouse and growing season
- Plant location shall be recorded as row/column grid position
- System shall track watering frequency preference and duration

**FR-PM-02: View Plant Inventory**
- User shall view all plants in a greenhouse, filtered by season
- Display shall show: plant name, location, status (healthy/concern), next watering, last sensor reading
- Plants shall be searchable by name and location

**FR-PM-03: Update Plant Information**
- User shall modify plant name, location, watering preferences, variety
- Updates shall be effective immediately for future watering operations
- Historical plant data shall be preserved for analytics

**FR-PM-04: Link Plants to Watering Cycles**
- System shall associate plants with irrigation devices
- User shall specify which cycles water which plants
- System shall prevent orphaned plants from receiving no irrigation

**FR-PM-05: Delete Plant**
- User shall remove plants from greenhouse
- System shall ask user to reassign dependent watering cycles
- Plant data shall be archived for historical analysis

---

### 3.3 Greenhouse Management Feature

#### 3.3.1 Greenhouse Configuration
**FR-GM-01: Create Greenhouse**
- System administrator shall create new greenhouse with: name, location, area (m²)
- Each greenhouse shall have unique MQTT broker configuration
- MQTT settings shall include: broker address, port, username, password
- Greenhouse shall track associated seasons, plants, and devices

**FR-GM-02: Configure MQTT Broker**
- User shall set MQTT connection details per greenhouse
- Settings shall include: broker hostname/IP, port (default 1883), authentication credentials
- System shall validate MQTT connection on configuration save
- Connection status shall be displayed in greenhouse settings

**FR-GM-03: Manage Greenhouse Features**
- System shall support feature flags for: plant layout, meteo stations, smart suggestions
- User shall enable/disable features per greenhouse
- Feature availability shall control UI visibility and API endpoint activation

**FR-GM-04: View Greenhouse Status**
- User shall see greenhouse overview: total plants, active devices, last sensor reading
- Status display shall include: MQTT connection status, active cycles, sensor health
- Alerts shall appear for connectivity or device issues

**FR-GM-05: Multiple Greenhouse Support**
- System shall manage unlimited greenhouses
- User shall switch context between greenhouses
- All data shall be properly scoped to active greenhouse
- Reports shall support cross-greenhouse comparison

---

### 3.4 Device Management Feature

#### 3.4.1 Device Registration & Pairing
**FR-DM-01: Discover Devices**
- System shall list all available Zigbee devices from MQTT broker
- Device discovery shall show: device ID, name, device type, signal quality
- User shall perform device pairing from discovery interface

**FR-DM-02: Pair Device**
- User shall add discovered devices to greenhouse configuration
- Pairing shall capture: device ID, user-friendly name, device type (irrigation/sensor)
- System shall store device MQTT topic mapping
- Paired device shall appear in device list

**FR-DM-03: Unpair Device**
- User shall remove devices from greenhouse
- Unpairing shall prevent further commands to device
- System shall warn about dependent cycles before unpairing
- Historical device data shall be preserved

**FR-DM-04: View Device List**
- User shall see all devices in greenhouse with: name, type, status (online/offline), signal quality
- Devices shall be filterable by type (irrigation/sensor)
- Last activity timestamp shall be displayed

**FR-DM-05: Device Configuration**
- User shall update device name and settings
- For irrigation devices: ON/OFF capability, pulse duration configuration
- For sensor devices: measurement type, calibration offset
- Configuration changes shall take immediate effect

---

### 3.5 Sensor Monitoring Feature

#### 3.5.1 Real-time Sensor Data
**FR-SM-01: Collect Sensor Data**
- System shall subscribe to MQTT sensor topics from all paired sensors
- Data types shall include: temperature (°C), humidity (%), signal quality (dBm)
- Data shall be collected with timestamps for audit trail
- System shall handle missed readings gracefully

**FR-SM-02: Store Sensor Readings**
- All sensor readings shall be persisted to PostgreSQL/TimescaleDB
- Storage shall optimize for time-series queries
- Retention policy: minimum 1 year of raw data, aggregated data indefinitely
- Data shall be indexed by device, timestamp, and sensor type

**FR-SM-03: View Sensor Data**
- User shall see current readings for all sensors in dashboard
- Current values shall update in real-time (WebSocket if available, polling otherwise)
- Sensor data cards shall show: current value, last reading time, status (normal/alert)
- Alert thresholds shall be configurable (default: temp <10°C or >35°C)

**FR-SM-04: Historical Sensor Data**
- User shall query historical sensor data for configurable date ranges
- Data shall be viewable in table format with download as CSV
- System shall provide aggregated views (hourly, daily, weekly averages)
- Trend analysis shall show temperature and humidity changes over time

**FR-SM-05: Sensor Health Monitoring**
- System shall detect and report sensor failures (no data for 1 hour)
- System shall track signal quality trends
- User shall receive alerts for disconnected or low-signal sensors
- Sensor status history shall be maintained

---

### 3.6 API & Integration Feature

#### 3.6.1 REST API Endpoints
**FR-API-01: Device Management Endpoints**
- GET /api/devices - List all devices in active greenhouse
- POST /api/devices/pair - Register new device
- DELETE /api/devices/{id} - Unpair device
- GET /api/devices/{id}/status - Get device status
- PUT /api/devices/{id} - Update device configuration

**FR-API-02: Watering Management Endpoints**
- GET /api/watering-plans - List all plans
- POST /api/watering-plans - Create new plan
- GET /api/watering-plans/{id}/cycles - List cycles in plan
- POST /api/watering-plans/{id}/cycles - Create cycle
- POST /api/irrigate/{device_id}/on - Immediate irrigation
- POST /api/irrigate/{device_id}/off - Stop irrigation

**FR-API-03: Sensor Data Endpoints**
- GET /api/sensors - List all sensors
- GET /api/sensors/{id}/readings - Get sensor data (with date range)
- GET /api/sensors/{id}/current - Get latest reading
- GET /api/sensors/{id}/stats - Get aggregated statistics

**FR-API-04: Greenhouse Management Endpoints**
- GET /api/greenhouses - List all greenhouses
- POST /api/greenhouses - Create greenhouse
- PUT /api/greenhouses/{id} - Update configuration
- GET /api/greenhouses/{id}/status - Get greenhouse status

**FR-API-05: Authentication & Authorization**
- All endpoints shall require authentication (token-based)
- User permissions shall be validated per greenhouse
- API responses shall include proper HTTP status codes
- Error responses shall include descriptive messages

#### 3.6.2 API Documentation
**FR-API-06: Interactive API Documentation**
- System shall provide Swagger UI at /docs
- System shall provide ReDoc at /redoc
- Documentation shall be auto-generated from code annotations
- Documentation shall include request/response examples

---

### 3.7 Web Interface Feature

#### 3.7.1 Dashboard
**FR-WEB-01: Main Dashboard**
- User shall see greenhouse overview: plant count, device status, last sensor reading
- Dashboard shall display active cycles and next scheduled events
- Real-time alerts shall appear for critical conditions
- User shall see weather integration if meteo station configured

**FR-WEB-02: Greenhouse Selection**
- User shall switch between greenhouses from dropdown/navigation
- Selection shall persist during session
- All views shall update when greenhouse changes

#### 3.7.2 Management Interfaces
**FR-WEB-03: Watering Plan Management UI**
- User shall create, view, edit, delete watering plans via form interface
- Plan list shall be paginated for performance
- Cycle creation wizard shall guide users through cycle setup

**FR-WEB-04: Plant Inventory UI**
- User shall manage plant registry with searchable table
- Plant location shall be visualizable on greenhouse map (if layout enabled)
- Plant-to-cycle mapping shall be configurable from plant detail view

**FR-WEB-05: Device Management UI**
- User shall see all devices in table with real-time status
- Device pairing wizard shall guide discovery and registration
- Quick actions shall allow immediate ON/OFF control

**FR-WEB-06: Sensor Monitoring Dashboard**
- Current readings shall display in card/tile layout
- User shall select date range for historical data
- Charts shall visualize temperature/humidity trends
- Export to CSV shall be available

---

### 3.8 Admin Interface Feature

#### 3.8.1 Django Admin
**FR-ADMIN-01: User Management**
- System shall provide user creation, modification, deletion in admin
- User permissions shall be assignable per greenhouse
- Admin shall track user login history

**FR-ADMIN-02: Data Management**
- Admin shall view and edit all system entities
- Admin shall delete records with cascade confirmation
- Admin shall export data in multiple formats (CSV, JSON)

**FR-ADMIN-03: System Monitoring**
- Admin shall view application logs
- Admin shall monitor database disk usage
- Admin shall see active user sessions

---

### 3.9 Scheduling & Task Execution Feature

#### 3.9.1 Celery Task Queue
**FR-SCHED-01: Scheduled Task Execution**
- Celery Beat shall check for due watering cycles every 30 seconds
- Due cycles shall be published to irrigation_checks task queue
- Cycles shall be verified for conditions before execution

**FR-SCHED-02: Task Queues**
- System shall maintain separate queues: irrigation_checks, irrigation_execution, irrigation_scheduling
- Task distribution shall allow horizontal scaling of workers
- Failed tasks shall retry with exponential backoff (up to 3 attempts)

**FR-SCHED-03: Task Monitoring**
- System shall track task status in Flower monitoring interface
- User shall see active tasks and execution history
- Failed tasks shall generate alerts with error messages

**FR-SCHED-04: Execution Logging**
- Each task execution shall log: start time, end time, status, MQTT commands sent
- Logs shall be queryable by device, date range, and status
- Task result shall include water usage estimates

---

## 4. Non-Functional Requirements

### 4.1 Performance Requirements

| Requirement | Target | Justification |
|-------------|--------|----------------|
| **API Response Time** | < 500ms (95th percentile) | User experience, web responsiveness |
| **Sensor Data Latency** | < 5 seconds | Real-time monitoring capability |
| **Irrigation Command Latency** | < 2 seconds (from API call to MQTT publish) | Safety and responsiveness |
| **Database Query Time** | < 1 second | Dashboard loading, API response time |
| **Concurrent Users** | 50+ simultaneous | Small to medium greenhouse operations |
| **Data Throughput** | 100+ sensor readings/second | Multi-device scaling |

### 4.2 Reliability & Availability

| Requirement | Target | Rationale |
|-------------|--------|-----------|
| **System Availability** | 99.5% uptime | Mission-critical irrigation operations |
| **MTBF (Mean Time Between Failure)** | > 720 hours | Stable production operation |
| **MTTR (Mean Time To Recover)** | < 30 minutes | Rapid restoration after failure |
| **Scheduled Cycle Success Rate** | > 99% | Consistent irrigation delivery |
| **Data Durability** | 99.99% | PostgreSQL replication, backups |

### 4.3 Scalability Requirements

| Requirement | Details |
|-------------|---------|
| **Greenhouses** | Support 10+ greenhouses in single deployment |
| **Devices per Greenhouse** | Support 100+ devices (irrigation + sensor) |
| **Sensors** | Handle 10,000+ sensor readings per day |
| **Concurrent Cycles** | Execute 50+ simultaneous watering cycles |
| **Storage** | Support 1+ year of sensor data (auto-archive older data) |
| **Horizontal Scaling** | Add Celery workers to scale task execution |

### 4.4 Security Requirements

| Requirement | Implementation |
|-------------|----------------|
| **Authentication** | Token-based (JWT recommended) for API and web |
| **Authorization** | Role-based access control (RBAC) per greenhouse |
| **Data Encryption** | MQTT connections (TLS), database passwords (hashed) |
| **HTTPS** | Required for production deployments |
| **API Key Management** | Keys rotated every 90 days minimum |
| **Audit Logging** | All user actions logged with IP address and timestamp |
| **SQL Injection Prevention** | ORM parameterized queries, no string concatenation |
| **Input Validation** | All inputs validated server-side, type checking |
| **Password Policy** | Minimum 12 characters, complexity requirements |
| **Session Management** | Token expiration after 24 hours of inactivity |

### 4.5 Maintainability & Code Quality

| Requirement | Standard |
|-------------|----------|
| **Code Comments** | 70%+ function-level documentation |
| **Test Coverage** | > 70% for critical functions (irrigation, sensor collection) |
| **API Documentation** | Auto-generated from code, 100% endpoint coverage |
| **Deployment Documentation** | Step-by-step guides for Docker and Raspberry Pi |
| **Error Handling** | Structured error responses with codes and messages |
| **Logging** | Structured logging with DEBUG, INFO, WARN, ERROR levels |
| **Configuration Management** | Environment variables for all environment-specific settings |

### 4.6 Compatibility Requirements

| Component | Requirement |
|-----------|-------------|
| **Database** | PostgreSQL 13+, TimescaleDB 1.7+ |
| **Message Broker** | MQTT 3.1.1, Mosquitto 2.0+ |
| **IoT Devices** | Zigbee 3.0 compatible, Z2M bridge compatible |
| **Python Version** | Python 3.10+ |
| **Docker** | Docker 20.10+, Docker Compose 2.0+ |
| **Browsers** | Chrome/Edge 90+, Firefox 88+ (responsive design) |
| **Operating Systems** | Linux (primary), Windows WSL2, Raspberry Pi OS |

---

## 5. External Interface Requirements

### 5.1 User Interfaces

#### 5.1.1 Web Application (Django)
- **Technology:** Django 4.2+, HTML5, CSS3, JavaScript
- **Responsive Design:** Mobile-friendly interface (breakpoints: 320px, 768px, 1200px)
- **Accessibility:** WCAG 2.1 Level AA compliance
- **Supported Browsers:** Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **Key Pages:**
  - Dashboard (overview, real-time data)
  - Watering Plans (CRUD operations)
  - Plant Inventory (management and mapping)
  - Device Management (pairing, status, control)
  - Sensor Monitoring (real-time and historical data)
  - Reports (irrigation history, water usage)
  - Admin Interface (user, data, system management)

#### 5.1.2 API Documentation (Swagger/ReDoc)
- **Location:** FastAPI instance, /docs (Swagger), /redoc (ReDoc)
- **Format:** OpenAPI 3.0 specification
- **Interactivity:** Try-it-out endpoint testing with authentication

### 5.2 Hardware Interfaces

#### 5.2.1 MQTT Communication
- **Protocol:** MQTT 3.1.1
- **Broker:** Mosquitto (typical port 1883)
- **Devices:** Zigbee devices via Zigbee2MQTT bridge
- **Command Topic:** `greenhouse/{id}/devices/{device_id}/command`
- **Data Topic:** `greenhouse/{id}/sensors/{sensor_id}/data`
- **Message Format:** JSON with required fields (timestamp, value, unit)

#### 5.2.2 Raspberry Pi Integration
- **OS:** Raspberry Pi OS (formerly Raspbian)
- **Python:** 3.10+
- **Services Deployed:**
  - Mosquitto MQTT broker
  - Zigbee2MQTT bridge
  - Sensor data collector (Python service)
  - Optional: Celery worker, local API
- **Network:** Static IP recommended (192.168.x.x)
- **Storage:** Minimum 16GB SD card (32GB recommended)

### 5.3 Software Interfaces

#### 5.3.1 Database Interface
- **System:** PostgreSQL 15+
- **Extensions:** TimescaleDB 1.7+
- **Connection:** psycopg2 adapter via SQLAlchemy ORM
- **Schema:** Auto-migrated using Alembic/Django migrations
- **Backup:** Daily automated backups, retention 30 days

#### 5.3.2 Message Broker Interface
- **System:** Redis 6.0+
- **Role:** Message broker for Celery, optional cache layer
- **Connection:** redis-py adapter
- **Data Structure:** Task queues, message storage, optional caching

#### 5.3.3 Monitoring & Visualization
- **Flower:** Web interface for Celery task monitoring (port 5555)
- **Grafana:** Dashboards for sensor data visualization (port 3000)
- **Data Source:** TimescaleDB for time-series visualization

### 5.4 Communication Interfaces

#### 5.4.1 REST API
- **Protocol:** HTTP/HTTPS
- **Port:** 8000 (FastAPI), 8080 (Django)
- **Format:** JSON request/response
- **Authentication:** Bearer token in Authorization header
- **Rate Limiting:** 100 requests per minute per user (configurable)
- **CORS:** Configurable allowed origins

#### 5.4.2 WebSocket (Optional Enhancement)
- **Purpose:** Real-time sensor data push to web clients
- **Fallback:** Polling if WebSocket unavailable
- **Frequency:** Data updates every 5-10 seconds

---

## 6. System Architecture

### 6.1 Microservices Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  User Interface Layer                    │
├──────────────────────────┬──────────────────────────────┤
│  Django Web App (8080)   │  FastAPI API (8000)         │
│  + Web UI                │  + REST Endpoints            │
│  + Admin Panel           │  + Swagger/ReDoc             │
└──────────────────────────┴──────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│             Application Services Layer                  │
├──────────────────────────┬──────────────────────────────┤
│  FastAPI Service         │  Django Application         │
│  - Device control        │  - ORM models               │
│  - MQTT client           │  - Business logic           │
│  - Immediate operations  │  - Admin interface          │
├──────────────────────────┼──────────────────────────────┤
│  Celery Worker Pool      │  Celery Beat Scheduler      │
│  - irrigation_checks     │  - 30s cycle checks         │
│  - irrigation_execution  │  - Task publishing          │
│  - irrigation_scheduling │  - Schedule management      │
└──────────────────────────┴──────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│          Data & Communication Infrastructure            │
├──────────────────────────┬──────────────────────────────┤
│  PostgreSQL (5432)       │  Redis (6379)               │
│  + TimescaleDB           │  - Task Queue               │
│  - Core data             │  - Message Broker           │
│  - Time-series data      │  - Optional Caching         │
├──────────────────────────┼──────────────────────────────┤
│  Mosquitto MQTT (1883)   │  Sensor Collector Service   │
│  - Device communication  │  - MQTT subscriber          │
│  - Bridge to Zigbee      │  - Data persistence         │
│  - Pub/Sub routing       │  - Time-series insertion    │
└──────────────────────────┴──────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│           Monitoring & Visualization Layer              │
├──────────────────────────┬──────────────────────────────┤
│  Flower (5555)           │  Grafana (3000)             │
│  - Task monitoring       │  - Sensor dashboards        │
│  - Worker health         │  - Trend analysis           │
│  - Queue status          │  - Alert configuration      │
└──────────────────────────┴──────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              IoT Devices & Sensors                      │
├─────────────────────────────────────────────────────────┤
│  Raspberry Pi (MQTT Broker & Zigbee2MQTT Bridge)       │
│  ├─ Zigbee Irrigation Devices (R7060 controllers)      │
│  ├─ Temperature/Humidity Sensors (E6)                  │
│  └─ Additional Zigbee Devices (expandable)             │
└─────────────────────────────────────────────────────────┘
```

### 6.2 Component Responsibilities

| Component | Responsibility |
|-----------|-----------------|
| **FastAPI Service** | HTTP API gateway, device control, real-time operations |
| **Django App** | Web interface, admin panel, ORM data management |
| **Celery Worker** | Async task execution (irrigation commands) |
| **Celery Beat** | Schedule monitoring and task publishing |
| **PostgreSQL** | Primary data store (plans, cycles, plants, devices, users) |
| **TimescaleDB** | Time-series sensor data optimization |
| **Redis** | Message queue, task queue, optional caching |
| **Mosquitto** | MQTT message broker and device gateway |
| **Sensor Collector** | MQTT subscription, data ingestion to database |
| **Flower** | Task queue monitoring and debugging |
| **Grafana** | Real-time visualization of sensor data |

### 6.3 Data Flow

**Scheduled Irrigation Execution:**
1. Celery Beat checks for due cycles (every 30 seconds)
2. Beat publishes task to `irrigation_checks` queue
3. Worker validates conditions, queues to `irrigation_execution`
4. Worker publishes MQTT command to device
5. Device executes irrigation for specified duration
6. Completion logged to PostgreSQL

**Sensor Data Collection:**
1. Zigbee device transmits measurement
2. Zigbee2MQTT bridge receives and publishes to MQTT
3. Sensor Collector subscribes and receives
4. Data stored in PostgreSQL with timestamp
5. TimescaleDB indexes for fast time-series queries
6. Grafana visualizes from TimescaleDB

**Manual Irrigation:**
1. User submits request via Web/API
2. FastAPI validates request and authentication
3. FastAPI publishes MQTT ON command
4. Device executes immediately
5. Operation logged to audit table

---

## 7. Deployment Requirements

### 7.1 Docker Deployment

#### 7.1.1 Services Composition
```yaml
Services:
- PostgreSQL (postgres:15-alpine)
- Redis (redis:7-alpine)
- FastAPI Service (custom image: app_fastapi)
- Django App (custom image: app_django)
- Celery Worker (custom image: app_celery)
- Celery Beat (custom image: app_scheduler)
- Mosquitto (eclipse-mosquitto:latest)
- Flower (mher/flower:latest)
- Grafana (grafana/grafana:latest)
- Sensor Collector (custom image: app_sensor_collector)
```

#### 7.1.2 Deployment Commands
```bash
docker-compose -f docker-compose.yml up -d          # Full stack
docker-compose -f docker-compose.yml logs -f        # View logs
docker-compose -f docker-compose.yml down           # Shutdown
```

#### 7.1.3 Environment Configuration
- `.env` file required with variables:
  - Database credentials
  - Redis connection
  - MQTT settings
  - API keys
  - Debug mode
  - Log levels

### 7.2 Raspberry Pi Deployment

#### 7.2.1 Requirements
- Raspberry Pi 3B+ or newer (4GB+ RAM)
- 32GB SD card minimum
- Network connectivity (Ethernet or WiFi)
- Static IP assignment

#### 7.2.2 Services Deployed
1. Mosquitto MQTT broker
2. Zigbee2MQTT bridge
3. Sensor data collector service
4. Optional: Celery worker
5. Optional: FastAPI/Django instances

#### 7.2.3 Setup Commands
```bash
./scripts/setup_raspberry_pi.sh              # Initial setup
./scripts/setup_mosquitto_wsl.sh             # MQTT configuration
./scripts/install_docker_raspberry_pi.sh     # Docker installation
```

### 7.3 WSL2 Development Setup

#### 7.3.1 Requirements
- Windows 10/11 with WSL2
- 8GB+ RAM allocated to WSL
- 50GB+ disk space

#### 7.3.2 Setup
```bash
./scripts/setup_complete_system.ps1    # PowerShell setup script
./scripts/run_api.sh                   # Start services
```

---

## 8. Data Requirements

### 8.1 Database Schema

#### 8.1.1 Core Entities

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| **Greenhouse** | Facility configuration | id, name, location, mqtt_broker, mqtt_port, created_at |
| **Plant** | Plant registry | id, greenhouse_id, name, variety, planting_date, location_row, location_col, harvest_date, watering_frequency |
| **Season** | Growing season | id, greenhouse_id, name, start_date, end_date, status |
| **WateringPlan** | Irrigation plan container | id, greenhouse_id, name, description, status, created_at |
| **WateringCycle** | Individual watering event | id, plan_id, name, schedule_time, duration_minutes, device_id, status, description |
| **Device** | Zigbee device | id, greenhouse_id, device_id (Zigbee), device_type (irrigation/sensor), name, mqtt_topic, online_status |
| **SensorData** | Time-series readings | id, device_id, timestamp, value, unit, sensor_type (temperature/humidity/signal) |
| **CycleExecution** | Execution history | id, cycle_id, start_time, end_time, status (success/failure/cancelled), error_message |
| **User** | System users | id, username, email, password_hash, is_active, created_at |
| **UserGreenhouse** | User permissions | user_id, greenhouse_id, role (operator/manager/admin) |

### 8.2 Data Retention Policies

| Data Type | Retention | Archival |
|-----------|-----------|----------|
| **Raw Sensor Data** | 1 year | Monthly archive to cold storage |
| **Cycle Execution Logs** | 2 years | Annual archive |
| **Audit Logs (User Actions)** | 2 years | Annual archive |
| **MQTT Messages** | 30 days | No archival |
| **Error Logs** | 90 days | 6-month summary kept |

### 8.3 Backup & Recovery

| Requirement | Implementation |
|-------------|----------------|
| **Backup Frequency** | Daily at 02:00 UTC |
| **Backup Location** | External storage, cloud (S3 compatible) |
| **Retention** | 30 days of daily backups, 1 year of weekly backups |
| **Recovery RTO** | < 1 hour |
| **Recovery RPO** | < 24 hours |
| **Test Restores** | Monthly validation of backup integrity |

### 8.4 Data Export/Import

| Scenario | Capability |
|----------|-----------|
| **Export Watering Plans** | JSON format with all cycles and device mappings |
| **Export Sensor Data** | CSV with timestamp, device, value, unit columns |
| **Import Plans** | Upload JSON to batch-create watering cycles |
| **Database Backups** | PostgreSQL dump (pg_dump) and restore |

---

## 9. Standards & Compliance

### 9.1 Industry Standards
- **MQTT:** MQ Telemetry Transport 3.1.1 (ISO/IEC 20922)
- **Zigbee:** Zigbee 3.0 for wireless communication
- **HTTP:** REST API following RFC 7231
- **JSON:** RFC 8259 for data interchange

### 9.2 Code Standards
- **Python:** PEP 8 style guide
- **Documentation:** Docstrings for all public functions (PEP 257)
- **Version Control:** Git with semantic versioning (semver.org)

### 9.3 Accessibility
- **WCAG 2.1** Level AA compliance for web interface
- **Color Contrast:** Minimum 4.5:1 for text
- **Keyboard Navigation:** All features accessible via keyboard

---

## 10. Future Enhancements & Extensibility

### 10.1 Planned Features
- [ ] SMS/Email alerts for critical events
- [ ] Machine learning-based irrigation optimization
- [ ] Weather integration (API-based precipitation, temperature)
- [ ] Mobile app (iOS/Android)
- [ ] Plant disease detection (image analysis)
- [ ] Water usage analytics and cost tracking
- [ ] Multi-language support (i18n)
- [ ] SSO integration (LDAP, OAuth2)

### 10.2 Extensibility Points
- **Custom Device Drivers:** Plugin architecture for new device types
- **Calculation Engines:** Custom irrigation algorithms
- **Notification Channels:** SMS, email, push notifications
- **Data Export:** Multiple format support (JSON, CSV, XML)
- **Dashboard Widgets:** Custom visualization components

---

## Glossary

| Term | Definition |
|------|-----------|
| **MQTT** | Message Queuing Telemetry Transport - lightweight IoT messaging protocol |
| **Zigbee** | Short-range wireless communication protocol for IoT devices |
| **Celery** | Distributed task queue for asynchronous job execution |
| **TimescaleDB** | PostgreSQL extension optimizing time-series data storage and queries |
| **RTO** | Recovery Time Objective - time to restore service after failure |
| **RPO** | Recovery Point Objective - amount of data loss tolerance |
| **MTBF** | Mean Time Between Failures - reliability metric |
| **MTTR** | Mean Time To Repair - average time to fix failures |
| **WCAG** | Web Content Accessibility Guidelines |
| **ORM** | Object-Relational Mapping - database abstraction layer |
| **JWT** | JSON Web Token - stateless authentication method |
| **RBAC** | Role-Based Access Control - permission model |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | May 14, 2026 | Development Team | Initial SRS document creation |

---

**Document Classification:** Internal - Technical Specification  
**Distribution:** Development Team, Project Stakeholders, Operations  
**Next Review Date:** August 14, 2026
