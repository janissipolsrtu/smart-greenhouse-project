from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.views.generic import ListView
from django.http import JsonResponse
from django.db.models import Avg, Max, Min, Count
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import IrrigationPlan, SensorData
import uuid
import time
import json
from datetime import datetime


class IrrigationPlanListView(ListView):
    model = IrrigationPlan
    template_name = 'irrigation/plan_list.html'
    context_object_name = 'plans'
    paginate_by = 10
    
    def get_queryset(self):
        return IrrigationPlan.objects.all().order_by('-scheduled_time')


def dashboard_view(request):
    """Main dashboard view with overview"""
    now = timezone.now()
    
    # Get statistics
    total_plans = IrrigationPlan.objects.count()
    pending_plans = IrrigationPlan.objects.filter(status='pending').count()
    completed_plans = IrrigationPlan.objects.filter(status='completed').count()
    failed_plans = IrrigationPlan.objects.filter(status='failed').count()
    
    # Get upcoming plans (next 24 hours)
    upcoming_plans = IrrigationPlan.objects.filter(
        scheduled_time__gte=now,
        scheduled_time__lte=now + timezone.timedelta(days=1),
        status='pending'
    ).order_by('scheduled_time')[:5]
    
    # Get recent completed plans
    recent_completed = IrrigationPlan.objects.filter(
        status__in=['completed', 'failed']
    ).order_by('-executed_at')[:5]
    
    # Get overdue plans
    overdue_plans = IrrigationPlan.objects.filter(
        scheduled_time__lt=now,
        status='pending'
    ).count()
    
    context = {
        'total_plans': total_plans,
        'pending_plans': pending_plans,
        'completed_plans': completed_plans, 
        'failed_plans': failed_plans,
        'overdue_plans': overdue_plans,
        'upcoming_plans': upcoming_plans,
        'recent_completed': recent_completed,
    }
    
    return render(request, 'irrigation/dashboard.html', context)


def create_plan_view(request):
    """Create a new irrigation plan"""
    if request.method == 'POST':
        try:
            scheduled_time = request.POST.get('scheduled_time')
            duration = int(request.POST.get('duration'))
            device = request.POST.get('device', '0x540f57fffe890af8')
            description = request.POST.get('description', '')
            
            # Parse the datetime
            scheduled_datetime = timezone.datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
            if timezone.is_aware(scheduled_datetime):
                scheduled_datetime = timezone.make_naive(scheduled_datetime, timezone.utc)
            
            # Generate unique plan ID
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            plan_id = f"plan_{timestamp}_{unique_id}"
            
            # Create the plan
            plan = IrrigationPlan.objects.create(
                id=plan_id,
                scheduled_time=scheduled_datetime,
                duration=duration,
                device=device,
                description=description,
                status='pending'
            )
            
            messages.success(request, f'Irrigation plan {plan_id} created successfully!')
            return redirect('irrigation:dashboard')
            
        except Exception as e:
            messages.error(request, f'Error creating plan: {str(e)}')
    
    return render(request, 'irrigation/create_plan.html')


def plan_detail_view(request, plan_id):
    """View details of a specific irrigation plan"""
    plan = get_object_or_404(IrrigationPlan, id=plan_id)
    return render(request, 'irrigation/plan_detail.html', {'plan': plan})


def delete_plan_view(request, plan_id):
    """Delete an irrigation plan"""
    plan = get_object_or_404(IrrigationPlan, id=plan_id)
    
    if request.method == 'POST':
        plan.delete()
        messages.success(request, f'Plan {plan_id} deleted successfully!')
        return redirect('irrigation:dashboard')
    
    return render(request, 'irrigation/confirm_delete.html', {'plan': plan})


def system_status_view(request):
    """System status and monitoring"""
    context = {
        'current_time': timezone.now(),
        'system_status': 'operational',  # TODO: Add real system checks
    }
    return render(request, 'irrigation/system_status.html', context)


def temperature_dashboard_view(request):
    """Temperature sensor dashboard view"""
    now = timezone.now()
    
    # Get the latest sensor data for each device
    latest_readings = []
    device_names = SensorData.objects.values_list('device_name', flat=True).distinct()
    
    for device_name in device_names:
        latest = SensorData.objects.filter(device_name=device_name).order_by('-timestamp').first()
        if latest:
            latest_readings.append(latest)
    
    # Get statistics for the last 24 hours
    twenty_four_hours_ago = now - timezone.timedelta(hours=24)
    recent_data = SensorData.objects.filter(timestamp__gte=twenty_four_hours_ago)
    
    stats = recent_data.aggregate(
        avg_temperature=Avg('temperature'),
        max_temperature=Max('temperature'),
        min_temperature=Min('temperature'),
        avg_humidity=Avg('humidity'),
        total_readings=Count('id')
    )
    
    # Get hourly averages for the last 24 hours for charting
    hourly_data = []
    for hour in range(24):
        hour_start = now - timezone.timedelta(hours=hour+1)
        hour_end = now - timezone.timedelta(hours=hour)
        
        hour_avg = SensorData.objects.filter(
            timestamp__gte=hour_start,
            timestamp__lt=hour_end
        ).aggregate(
            avg_temp=Avg('temperature'),
            avg_humidity=Avg('humidity')
        )
        
        hourly_data.append({
            'hour': hour_start.strftime('%H:%M'),
            'temperature': hour_avg['avg_temp'] or 0,
            'humidity': hour_avg['avg_humidity'] or 0
        })
    
    # Reverse to show chronological order
    hourly_data.reverse()
    
    context = {
        'latest_readings': latest_readings,
        'stats': stats,
        'hourly_data': hourly_data,
        'current_time': now,
        'device_count': len(latest_readings)
    }
    
    return render(request, 'irrigation/temperature_dashboard.html', context)


def sensor_data_api(request):
    """API endpoint for sensor data (for real-time updates)"""
    device_name = request.GET.get('device')
    hours = int(request.GET.get('hours', 6))
    
    # Get data for the specified time period
    time_threshold = timezone.now() - timezone.timedelta(hours=hours)
    
    query = SensorData.objects.filter(timestamp__gte=time_threshold)
    if device_name:
        query = query.filter(device_name=device_name)
    
    data = []
    for reading in query.order_by('timestamp'):
        data.append({
            'timestamp': reading.timestamp.isoformat(),
            'temperature': float(reading.temperature) if reading.temperature else None,
            'humidity': reading.humidity,
            'device_name': reading.device_name,
            'linkquality': reading.linkquality
        })
    
    return JsonResponse({'data': data})


def sensor_detail_view(request, device_name):
    """Detailed view for a specific sensor device"""
    # Get latest reading
    latest_reading = SensorData.objects.filter(device_name=device_name).order_by('-timestamp').first()
    
    if not latest_reading:
        messages.error(request, f'No data found for device: {device_name}')
        return redirect('irrigation:temperature_dashboard')
    
    # Get readings for the last 7 days
    week_ago = timezone.now() - timezone.timedelta(days=7)
    readings = SensorData.objects.filter(
        device_name=device_name,
        timestamp__gte=week_ago
    ).order_by('-timestamp')[:100]  # Limit to 100 most recent
    
    # Calculate statistics
    stats = SensorData.objects.filter(
        device_name=device_name,
        timestamp__gte=week_ago
    ).aggregate(
        avg_temperature=Avg('temperature'),
        max_temperature=Max('temperature'),
        min_temperature=Min('temperature'),
        avg_humidity=Avg('humidity'),
        max_humidity=Max('humidity'),
        min_humidity=Min('humidity'),
        total_readings=Count('id')
    )
    
    context = {
        'device_name': device_name,
        'latest_reading': latest_reading,
        'recent_readings': readings,
        'stats': stats,
    }
    
    return render(request, 'irrigation/sensor_detail.html', context)


@csrf_exempt
@require_http_methods(["POST"])
def bulk_sensor_data_api(request):
    """API endpoint to receive bulk sensor data from Raspberry Pi"""
    try:
        # Parse JSON data
        data = json.loads(request.body)
        readings = data.get('readings', [])
        source = data.get('source', 'unknown')
        collected_at = data.get('collected_at')
        
        if not readings:
            return JsonResponse({'error': 'No readings provided'}, status=400)
        
        # Process and save readings
        saved_count = 0
        errors = []
        
        for reading_data in readings:
            try:
                # Parse timestamp
                timestamp_str = reading_data.get('timestamp')
                if timestamp_str:
                    # Handle ISO format with Z suffix
                    if timestamp_str.endswith('Z'):
                        timestamp_str = timestamp_str[:-1] + '+00:00'
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timezone.is_aware(timestamp):
                        timestamp = timezone.make_naive(timestamp, timezone.utc)
                else:
                    timestamp = timezone.now()
                
                # Create sensor data record
                sensor_reading = SensorData.objects.create(
                    device_name=reading_data.get('device_name'),
                    temperature=reading_data.get('temperature'),
                    humidity=reading_data.get('humidity'),
                    linkquality=reading_data.get('linkquality'),
                    max_temperature=reading_data.get('max_temperature'),
                    temperature_unit=reading_data.get('temperature_unit', 'celsius'),
                    raw_data=reading_data.get('raw_data'),
                    timestamp=timestamp
                )
                
                saved_count += 1
                
            except Exception as e:
                errors.append(f"Error processing reading: {str(e)}")
                continue
        
        response_data = {
            'status': 'success',
            'saved_count': saved_count,
            'total_received': len(readings),
            'source': source,
            'errors': errors[:10]  # Limit error messages
        }
        
        if errors:
            response_data['status'] = 'partial_success'
        
        return JsonResponse(response_data, status=201 if saved_count > 0 else 400)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Server error: {str(e)}'}, status=500)


@require_http_methods(["GET"])
def health_check_api(request):
    """Health check endpoint for Raspberry Pi to test connectivity"""
    try:
        # Test database connection
        sensor_count = SensorData.objects.count()
        recent_readings = SensorData.objects.filter(
            timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
        ).count()
        
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'database': 'connected',
            'total_sensor_records': sensor_count,
            'recent_readings_24h': recent_readings,
            'version': '1.0.0'
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }, status=503)