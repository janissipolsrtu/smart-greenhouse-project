# Modified FastAPI endpoints for server-side timing

@app.post("/api/irrigation/schedule", response_model=ApiResponse, tags=["Irrigation"])
async def schedule_irrigation(schedule: IrrigationSchedule):
    """
    Schedule irrigation with MQTT server-side timing (no network latency issues)
    Timing is handled by the timer service running on the Raspberry Pi
    """
    try:
        duration = schedule.duration
        
        if duration <= 0 or duration > 3600:  # Max 1 hour
            raise HTTPException(
                status_code=400,
                detail="Duration must be between 1 and 3600 seconds"
            )
        
        # Send schedule request to MQTT timer service (on Pi)
        schedule_request = {
            "device": DEVICES['irrigation_controller']['name'],
            "duration": duration,
            "action": "schedule",
            "requested_by": "fastapi",
            "timestamp": datetime.now().isoformat()
        }
        
        success = mqtt_client.publish("irrigation/schedule/request", schedule_request)
        
        if success:
            return ApiResponse(
                success=True,
                message=f"Irrigation schedule request sent ({duration}s)",
                data={
                    "duration": duration,
                    "timing_mode": "server_side",
                    "device": DEVICES['irrigation_controller']['name'],
                    "note": "Timer runs on Raspberry Pi for precise control"
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send schedule request to timer service"
            )
            
    except Exception as e:
        logger.error(f"Error in irrigation scheduling: {e}")
        raise HTTPException(status_code=500, detail=f"Scheduling error: {str(e)}")

@app.post("/api/irrigation/control", response_model=ApiResponse, tags=["Irrigation"])
async def control_irrigation(command: IrrigationCommand):
    """Control irrigation via MQTT timer service for consistent behavior"""
    try:
        action = command.action.upper()
        
        if action not in ['ON', 'OFF']:
            raise HTTPException(
                status_code=400,
                detail="Invalid action. Use 'ON' or 'OFF'"
            )
        
        # Send control request to MQTT timer service
        control_request = {
            "device": DEVICES['irrigation_controller']['name'],
            "action": action,
            "requested_by": "fastapi",
            "timestamp": datetime.now().isoformat()
        }
        
        success = mqtt_client.publish("irrigation/control/request", control_request)
        
        if success:
            return ApiResponse(
                success=True,
                message=f"Irrigation control request sent: {action}",
                data={
                    "action": action,
                    "device": DEVICES['irrigation_controller']['name'],
                    "control_mode": "server_side"
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to send control request to timer service"
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in irrigation control: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@app.get("/api/irrigation/schedule/status", tags=["Irrigation"])
async def get_schedule_status():
    """Get current irrigation schedule status from timer service"""
    # You would subscribe to "irrigation/status/schedule" and store the data
    # This is just a placeholder showing the concept
    return {
        "success": True,
        "message": "Schedule status (implement MQTT subscription to irrigation/status/schedule)",
        "data": {
            "note": "Timer service publishes status updates to irrigation/status/schedule"
        }
    }