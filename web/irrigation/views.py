from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.views.generic import ListView
from django.http import JsonResponse
from django.db.models import Avg, Max, Min, Count, Q
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .models import IrrigationPlan, SensorData, Plant
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

# =================== PLANT MANAGEMENT VIEWS ===================

class PlantListView(ListView):
    """List all plants with pagination"""
    model = Plant
    template_name = 'irrigation/plant_list.html'
    context_object_name = 'plants'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = Plant.objects.filter(active=True).order_by('-created_at')
        
        # Add search functionality
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(variety__icontains=search_query) |
                Q(notes__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['total_plants'] = Plant.objects.filter(active=True).count()
        return context


def plant_dashboard_view(request):
    """Plant management dashboard with overview (FR-16)"""
    now = timezone.now()
    today = now.date()
    
    # Get plant statistics
    total_plants = Plant.objects.filter(active=True).count()
    plants_ready_for_harvest = Plant.objects.filter(
        active=True,
        harvest_date_estimate__lte=today
    ).count()
    
    recently_planted = Plant.objects.filter(
        active=True,
        planting_date__gte=today - timezone.timedelta(days=7)
    ).count()
    
    # Get plants ready for harvest
    harvest_ready_plants = Plant.objects.filter(
        active=True,
        harvest_date_estimate__lte=today
    ).order_by('harvest_date_estimate')[:5]
    
    # Get recently planted plants
    recent_plants = Plant.objects.filter(
        active=True
    ).order_by('-planting_date')[:5]
    
    # Get greenhouse layout summary (first 5x5 for overview)
    layout_summary = get_greenhouse_layout_summary(max_rows=5, max_columns=5)
    
    context = {
        'total_plants': total_plants,
        'plants_ready_for_harvest': plants_ready_for_harvest,
        'recently_planted': recently_planted,
        'harvest_ready_plants': harvest_ready_plants,
        'recent_plants': recent_plants,
        'layout_summary': layout_summary,
        'current_date': today,
    }
    
    return render(request, 'irrigation/plant_dashboard.html', context)


def plant_detail_view(request, plant_id):
    """View details of a specific plant (FR-16)"""
    plant = get_object_or_404(Plant, id=plant_id)
    
    context = {
        'plant': plant,
        'can_edit': plant.active,  # Only allow editing of active plants
    }
    
    return render(request, 'irrigation/plant_detail.html', context)


def create_plant_view(request):
    """Create a new plant registration (FR-9)"""
    if request.method == 'POST':
        try:
            # Extract form data
            name = request.POST.get('name').strip()
            variety = request.POST.get('variety', '').strip() or None
            planting_date = request.POST.get('planting_date')
            location_row = int(request.POST.get('location_row'))
            location_column = int(request.POST.get('location_column'))
            watering_frequency = int(request.POST.get('watering_frequency', 1))
            watering_duration = int(request.POST.get('watering_duration', 300))
            water_amount_ml = request.POST.get('water_amount_ml')
            harvest_date_estimate = request.POST.get('harvest_date_estimate')  
            harvest_quantity_estimate = request.POST.get('harvest_quantity_estimate')
            location_description = request.POST.get('location_description', '').strip() or None
            notes = request.POST.get('notes', '').strip() or None
            
            # Validate water amount
            water_amount_ml = int(water_amount_ml) if water_amount_ml else None
            
            # Validate harvest data  
            harvest_date_estimate = datetime.fromisoformat(harvest_date_estimate).date() if harvest_date_estimate else None
            harvest_quantity_estimate = float(harvest_quantity_estimate) if harvest_quantity_estimate else None
            
            # Parse planting date
            planting_date = datetime.fromisoformat(planting_date).date()
            
            # Check if location is already occupied
            existing_plant = Plant.objects.filter(
                location_row=location_row,
                location_column=location_column,
                active=True
            ).first()
            
            if existing_plant:
                messages.error(request, f'Atrašanās vieta R{location_row}C{location_column} jau ir aizņemta ar augu: {existing_plant.name}')
                return render(request, 'irrigation/create_plant.html')
            
            # Create the plant
            plant = Plant.objects.create(
                name=name,
                variety=variety,
                planting_date=planting_date,
                location_row=location_row,
                location_column=location_column,
                watering_frequency=watering_frequency,
                watering_duration=watering_duration,
                water_amount_ml=water_amount_ml,
                harvest_date_estimate=harvest_date_estimate,
                harvest_quantity_estimate=harvest_quantity_estimate,
                location_description=location_description,
                notes=notes
            )
            
            messages.success(request, f'Augs "{plant.name}" veiksmīgi reģistrēts pozīcijā {plant.location_coordinate}!')
            return redirect('irrigation:plant_detail', plant_id=plant.id)
            
        except ValueError as e:
            messages.error(request, f'Nepareizi dati: {str(e)}')
        except Exception as e:
            messages.error(request, f'Kļūda reģistrējot augu: {str(e)}')
    
    return render(request, 'irrigation/create_plant.html')


def edit_plant_view(request, plant_id):
    """Edit plant information (FR-16)"""
    plant = get_object_or_404(Plant, id=plant_id)
    
    if not plant.active:
        messages.warning(request, 'Nav iespējams rediģēt neaktīvu augu.')
        return redirect('irrigation:plant_detail', plant_id=plant.id)
    
    if request.method == 'POST':
        try:
            # Update plant data
            plant.name = request.POST.get('name').strip()
            plant.variety = request.POST.get('variety', '').strip() or None
            plant.planting_date = datetime.fromisoformat(request.POST.get('planting_date')).date()
            
            new_location_row = int(request.POST.get('location_row'))
            new_location_column = int(request.POST.get('location_column'))
            
            # Check location change conflicts
            if (new_location_row != plant.location_row or new_location_column != plant.location_column):
                existing_plant = Plant.objects.filter(
                    location_row=new_location_row,
                    location_column=new_location_column,
                    active=True
                ).exclude(id=plant.id).first()
                
                if existing_plant:
                    messages.error(request, f'Atrašanās vieta R{new_location_row}C{new_location_column} jau ir aizņemta ar augu: {existing_plant.name}')
                    return render(request, 'irrigation/edit_plant.html', {'plant': plant})
            
            plant.location_row = new_location_row
            plant.location_column = new_location_column
            plant.watering_frequency = int(request.POST.get('watering_frequency', 1))
            plant.watering_duration = int(request.POST.get('watering_duration', 300))
            
            water_amount_ml = request.POST.get('water_amount_ml')
            plant.water_amount_ml = int(water_amount_ml) if water_amount_ml else None
            
            harvest_date = request.POST.get('harvest_date_estimate')
            plant.harvest_date_estimate = datetime.fromisoformat(harvest_date).date() if harvest_date else None
            
            harvest_quantity = request.POST.get('harvest_quantity_estimate')
            plant.harvest_quantity_estimate = float(harvest_quantity) if harvest_quantity else None
            
            plant.location_description = request.POST.get('location_description', '').strip() or None
            plant.notes = request.POST.get('notes', '').strip() or None
            
            plant.save()
            
            messages.success(request, f'Auga "{plant.name}" informācija veiksmīgi atjaunināta!')
            return redirect('irrigation:plant_detail', plant_id=plant.id)
            
        except ValueError as e:
            messages.error(request, f'Nepareizi dati: {str(e)}')
        except Exception as e:
            messages.error(request, f'Kļūda atjauninot augu: {str(e)}')
    
    context = {'plant': plant}
    return render(request, 'irrigation/edit_plant.html', context)


def deactivate_plant_view(request, plant_id):
    """Deactivate plant (soft delete)"""
    plant = get_object_or_404(Plant, id=plant_id)
    
    if request.method == 'POST':
        plant.active = False
        plant.save()
        messages.success(request, f'Augs "{plant.name}" veiksmīgi deaktivizēts!')
        return redirect('irrigation:plant_dashboard')
    
    return render(request, 'irrigation/confirm_deactivate_plant.html', {'plant': plant})


def greenhouse_layout_view(request):
    """Display greenhouse layout with plant positions (FR-15)"""
    max_rows = int(request.GET.get('rows', 10))
    max_columns = int(request.GET.get('columns', 10))
    
    layout = get_greenhouse_layout_summary(max_rows=max_rows, max_columns=max_columns)
    
    context = {
        'layout': layout,
        'max_rows': max_rows,
        'max_columns': max_columns,
        'row_range': range(1, max_rows + 1),
        'column_range': range(1, max_columns + 1),
    }
    
    return render(request, 'irrigation/greenhouse_layout.html', context)


def plants_ready_for_harvest_view(request):
    """View plants that are ready for harvest (FR-14)"""
    today = timezone.now().date()
    
    ready_plants = Plant.objects.filter(
        active=True,
        harvest_date_estimate__lte=today
    ).order_by('harvest_date_estimate')
    
    upcoming_harvest = Plant.objects.filter(
        active=True,
        harvest_date_estimate__gt=today,
        harvest_date_estimate__lte=today + timezone.timedelta(days=7)
    ).order_by('harvest_date_estimate')
    
    context = {
        'ready_plants': ready_plants,
        'upcoming_harvest': upcoming_harvest,
        'current_date': today,
    }
    
    return render(request, 'irrigation/harvest_ready.html', context)


def get_greenhouse_layout_summary(max_rows=10, max_columns=10):
    """Helper function to generate greenhouse layout data"""
    plants = Plant.objects.filter(active=True) 
    
    layout = {}
    for row in range(1, max_rows + 1):
        layout[row] = {}
        for col in range(1, max_columns + 1):
            layout[row][col] = None
    
    for plant in plants:
        if plant.location_row <= max_rows and plant.location_column <= max_columns:
            layout[plant.location_row][plant.location_column] = {
                'id': plant.id,
                'name': plant.name,
                'variety': plant.variety,
                'planting_date': plant.planting_date,
                'days_since_planting': plant.days_since_planting,
                'harvest_ready': plant.is_ready_for_harvest
            }
    
    return layout


# API endpoints for plants
def plants_api(request):
    """API endpoint for plant data (for AJAX requests)"""
    if request.method == 'GET':
        active_only = request.GET.get('active_only', 'true').lower() == 'true'
        search_query = request.GET.get('search', '')
        
        queryset = Plant.objects.all()
        
        if active_only:
            queryset = queryset.filter(active=True)
        
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) | 
                Q(variety__icontains=search_query)
            )
        
        plants_data = []
        for plant in queryset.order_by('-created_at')[:50]:  # Limit to 50 for performance
            plants_data.append({
                'id': plant.id,
                'name': plant.name,
                'variety': plant.variety,
                'location': plant.location_coordinate,
                'planting_date': plant.planting_date.isoformat(),
                'days_since_planting': plant.days_since_planting,
                'harvest_ready': plant.is_ready_for_harvest,
                'active': plant.active
            })
        
        return JsonResponse({
            'status': 'success',
            'plants': plants_data,
            'count': len(plants_data)
        })
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)