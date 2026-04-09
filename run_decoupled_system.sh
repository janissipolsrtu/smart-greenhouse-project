#!/bin/bash
# run_decoupled_system.sh - Start both API and Scheduler services

echo "🚀 Starting Decoupled Irrigation System"

# Option 1: Using Docker Compose (Recommended)
if command -v docker-compose &> /dev/null; then
    echo "📦 Starting with Docker Compose..."
    docker-compose up -d
    echo "✅ Services started:"
    echo "   - API: http://localhost:8000"
    echo "   - Scheduler: Running in background"
    echo "   - Shared storage: irrigation_data volume"
    
# Option 2: Using separate terminals (Development)
else
    echo "🔧 Development mode - start each service in separate terminals:"
    echo ""
    echo "Terminal 1 - Install dependencies and start API:"
    echo "  pip install -r requirements.txt"
    echo "  python irrigation_api_crud.py"
    echo ""
    echo "Terminal 2 - Install scheduler dependencies and start scheduler:"
    echo "  pip install -r requirements_scheduler.txt" 
    echo "  python irrigation_scheduler_service.py"
    echo ""
    echo "Both services will share the irrigation_plans.json file"
fi

echo ""
echo "📋 System Architecture:"
echo "  ┌─────────────────┐    ┌─────────────────┐"
echo "  │   FastAPI       │    │   Scheduler     │" 
echo "  │   (CRUD Only)   │◄──►│   Service       │"
echo "  │   Port 8000     │    │   (APScheduler) │"
echo "  └─────────────────┘    └─────────────────┘"
echo "           │                        │"
echo "           └────────┬───────────────┘"
echo "                    ▼"
echo "         ┌─────────────────┐"
echo "         │ irrigation_     │"
echo "         │ plans.json      │"
echo "         └─────────────────┘"
echo ""
echo "✨ Benefits of decoupled architecture:"
echo "  ✅ API focuses on CRUD operations only"
echo "  ✅ Scheduler runs independently" 
echo "  ✅ Better reliability and maintainability"
echo "  ✅ Services can be scaled separately"
echo "  ✅ Persistent job storage with APScheduler"