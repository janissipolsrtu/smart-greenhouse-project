from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.generic import ListView
from django.http import JsonResponse
from django.db import connection
from django.db.models import Avg, Max, Min, Count, Q
from django.core.mail import send_mail
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
import os
from .models import WateringPlan, WateringCycle, SensorData, Plant, PathCell, GreenhouseConfig, Device
from .forms import RegistrationForm
import uuid
import time
import json
import threading
from datetime import datetime, timedelta


class WateringCycleListView(ListView):
    model = WateringCycle
    template_name = 'smart_greenhouse/plan_list.html'
    context_object_name = 'plans'
    paginate_by = 10
    
    def get_queryset(self):
        return WateringCycle.objects.all().order_by('-scheduled_time')


@require_http_methods(["GET", "POST"])
def login_view(request):
    """Login page for web UI users."""
    if request.user.is_authenticated:
        return redirect('irrigation:dashboard')

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, 'Pieslēgšanās veiksmīga.')
            next_url = request.GET.get('next') or request.POST.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('irrigation:dashboard')

        username = (request.POST.get('username') or '').strip().lower()
        if username and User.objects.filter(username=username, is_active=False).exists():
            messages.warning(request, 'Lietotājs vēl nav apstiprināts. Pārbaudiet e-pastu un apstipriniet kontu.')

    return render(request, 'registration/login.html', {'form': form, 'next': request.GET.get('next', '')})


def logout_view(request):
    """Logout current user."""
    logout(request)
    messages.info(request, 'Jūs esat atslēdzies no sistēmas.')
    return redirect('irrigation:login')


@require_http_methods(["GET", "POST"])
def register_view(request):
    """Self-registration with email confirmation."""
    if request.user.is_authenticated:
        return redirect('irrigation:dashboard')

    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        password = form.cleaned_data['password1']

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            is_active=False,
        )

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verify_url = request.build_absolute_uri(
            reverse('irrigation:verify_email', kwargs={'uidb64': uidb64, 'token': token})
        )

        send_mail(
            subject='Apstipriniet kontu Gudrā siltumnīca',
            message=(
                'Paldies par reģistrāciju.\n\n'
                'Lai aktivizētu kontu, atveriet saiti:\n'
                f'{verify_url}\n\n'
                'Ja šo pieprasījumu neveicāt jūs, ignorējiet šo vēstuli.'
            ),
            from_email=os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@smart-greenhouse.local'),
            recipient_list=[email],
            fail_silently=False,
        )

        messages.success(request, 'Reģistrācija veiksmīga. Pārbaudiet e-pastu un apstipriniet kontu.')
        return redirect('irrigation:login')

    return render(request, 'registration/register.html', {'form': form})


def verify_email_view(request, uidb64, token):
    """Activate account via email link token."""
    user = None
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save(update_fields=['is_active'])
        login(request, user)
        messages.success(request, 'E-pasts apstiprināts. Konts aktivizēts.')
        return redirect('irrigation:dashboard')

    messages.error(request, 'Apstiprināšanas saite nav derīga vai ir beigusies.')
    return redirect('irrigation:login')


def dashboard_view(request):
    """Main dashboard view with overview"""
    now = timezone.now()

    # Greenhouse context
    active_greenhouse = GreenhouseConfig.get_config()
    all_greenhouses = GreenhouseConfig.objects.all().order_by('name')

    # Get statistics
    total_cycles = WateringCycle.objects.count()
    pending_cycles = WateringCycle.objects.filter(status='pending').count()
    completed_cycles = WateringCycle.objects.filter(status='completed').count()
    failed_cycles = WateringCycle.objects.filter(status='failed').count()
    total_plan_containers = WateringPlan.objects.count()
    
    # Get upcoming cycles (next 24 hours)
    upcoming_cycles = WateringCycle.objects.filter(
        scheduled_time__gte=now,
        scheduled_time__lte=now + timezone.timedelta(days=1),
        status='pending'
    ).order_by('scheduled_time')[:5]
    
    # Get recent completed cycles
    recent_completed = WateringCycle.objects.filter(
        status__in=['completed', 'failed']
    ).order_by('-executed_at')[:5]
    
    # Get overdue cycles
    overdue_cycles = WateringCycle.objects.filter(
        scheduled_time__lt=now,
        status='pending'
    ).count()

    # Compact latest sensor snippet for dashboard sidebar.
    dashboard_sensor_snippet = []
    greenhouse_devices = Device.objects.none()
    if active_greenhouse:
        greenhouse_devices = Device.objects.filter(greenhouse=active_greenhouse, active=True).exclude(
            name__iexact='Laistīšanas vārsts'
        ).exclude(
            device_type='irrigation_controller'
        ).order_by('name')

    sensor_identifiers = []
    if greenhouse_devices.exists():
        sensor_identifiers = list(greenhouse_devices.values_list('zigbee_id', flat=True)) + list(greenhouse_devices.values_list('name', flat=True))

    with connection.cursor() as cursor:
        if sensor_identifiers:
            cursor.execute(
                """
                SELECT DISTINCT ON (device_name)
                    device_name, temperature, humidity, soil_moisture, linkquality, battery, timestamp
                FROM sensor_measurements
                WHERE device_name = ANY(%s)
                ORDER BY device_name, timestamp DESC
                """,
                [sensor_identifiers],
            )
        else:
            cursor.execute(
                """
                SELECT DISTINCT ON (device_name)
                    device_name, temperature, humidity, soil_moisture, linkquality, battery, timestamp
                FROM sensor_measurements
                ORDER BY device_name, timestamp DESC
                LIMIT 5
                """
            )

        latest_sensor_rows = cursor.fetchall()

    name_map = {str(device.zigbee_id): device.name for device in greenhouse_devices}
    for row in latest_sensor_rows:
        device_name, temperature, humidity, soil_moisture, linkquality, battery, timestamp = row
        dashboard_sensor_snippet.append({
            'device_name': device_name,
            'device_label': name_map.get(str(device_name), str(device_name)),
            'temperature': temperature,
            'humidity': humidity,
            'soil_moisture': soil_moisture,
            'linkquality': linkquality,
            'battery': battery,
            'timestamp': timestamp,
        })

    dashboard_sensor_snippet.sort(key=lambda item: item['timestamp'] or timezone.datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    dashboard_sensor_snippet = dashboard_sensor_snippet[:3]
    
    # Generate greenhouse layout grid using the same persisted size as layout page
    if active_greenhouse:
        rows_key = f'layout_rows_{active_greenhouse.pk}'
        columns_key = f'layout_columns_{active_greenhouse.pk}'
    else:
        rows_key = 'layout_rows_default'
        columns_key = 'layout_columns_default'

    def _safe_grid_size(value, default):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(5, min(20, parsed))

    max_rows = _safe_grid_size(request.session.get(rows_key), 10)
    max_columns = _safe_grid_size(request.session.get(columns_key), 10)
    plants = Plant.objects.filter(active=True)
    paths = PathCell.objects.all()
    
    grid_data = []
    for row in range(1, max_rows + 1):
        row_data = []
        for col in range(1, max_columns + 1):
            # Find plant at this position
            plant_at_position = plants.filter(location_row=row, location_column=col).first()
            # Find path at this position
            path_at_position = paths.filter(row=row, column=col).first()
            
            if plant_at_position:
                row_data.append({
                    'cell_type': 'plant',
                    'has_plant': True,
                    'plant': plant_at_position,
                    'has_path': False,
                    'path': None,
                    'row': row,
                    'col': col
                })
            elif path_at_position:
                row_data.append({
                    'cell_type': 'path',
                    'has_plant': False,
                    'plant': None,
                    'has_path': True,
                    'path': path_at_position,
                    'row': row,
                    'col': col
                })
            else:
                row_data.append({
                    'cell_type': 'empty',
                    'has_plant': False,
                    'plant': None,
                    'has_path': False,
                    'path': None,
                    'row': row,
                    'col': col
                })
        grid_data.append(row_data)
    
    context = {
        'total_cycles': total_cycles,
        'total_plans': total_cycles,
        'pending_cycles': pending_cycles,
        'pending_plans': pending_cycles,
        'completed_cycles': completed_cycles,
        'completed_plans': completed_cycles,
        'failed_cycles': failed_cycles,
        'failed_plans': failed_cycles,
        'overdue_cycles': overdue_cycles,
        'overdue_plans': overdue_cycles,
        'upcoming_cycles': upcoming_cycles,
        'upcoming_plans': upcoming_cycles,
        'recent_completed': recent_completed,
        'total_plan_containers': total_plan_containers,
        'active_greenhouse': active_greenhouse,
        'all_greenhouses': all_greenhouses,
        'grid_data': grid_data,
        'max_rows': max_rows,
        'max_columns': max_columns,
        'row_range': range(1, max_rows + 1),
        'column_range': range(1, max_columns + 1),
        'dashboard_sensor_snippet': dashboard_sensor_snippet,
    }

    return render(request, 'smart_greenhouse/dashboard.html', context)


def create_cycle_view(request):
    """Create a new watering cycle"""
    if request.method == 'POST':
        try:
            scheduled_time = request.POST.get('scheduled_time')
            duration = int(request.POST.get('duration'))
            device = request.POST.get('device', '0x540f57fffe890af8')
            description = request.POST.get('description', '')
            plan_id = request.POST.get('plan_id') or None
            
            # Parse the datetime
            scheduled_datetime = timezone.datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
            if timezone.is_aware(scheduled_datetime):
                scheduled_datetime = timezone.make_naive(scheduled_datetime, timezone.utc)
            
            # Generate unique cycle ID
            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            cycle_id = f"cycle_{timestamp}_{unique_id}"
            
            plan = None
            if plan_id:
                plan = WateringPlan.objects.filter(id=plan_id).first()

            # Create the cycle
            cycle = WateringCycle.objects.create(
                id=cycle_id,
                scheduled_time=scheduled_datetime,
                duration=duration,
                device=device,
                plan=plan,
                description=description,
                status='pending'
            )
            
            messages.success(request, f'Laistīšanas cikls {cycle_id} veiksmīgi izveidots!')
            return redirect('irrigation:dashboard')
            
        except Exception as e:
            messages.error(request, f'Kļūda izveidojot ciklu: {str(e)}')

    plans = WateringPlan.objects.filter(active=True).order_by('-created_at')
    selected_plan_id = request.GET.get('plan_id', '')
    return render(request, 'smart_greenhouse/create_plan.html', {
        'plans': plans,
        'selected_plan_id': selected_plan_id,
    })


def cycle_detail_view(request, cycle_id):
    """View details of a specific watering cycle"""
    cycle = get_object_or_404(WateringCycle, id=cycle_id)
    return render(request, 'smart_greenhouse/plan_detail.html', {'cycle': cycle, 'plan': cycle})


def delete_cycle_view(request, cycle_id):
    """Delete a watering cycle"""
    cycle = get_object_or_404(WateringCycle, id=cycle_id)
    
    if request.method == 'POST':
        cycle.delete()
        messages.success(request, f'Cikls {cycle_id} veiksmīgi dzēsts!')
        return redirect('irrigation:dashboard')
    
    return render(request, 'smart_greenhouse/confirm_delete.html', {'cycle': cycle, 'plan': cycle})


class WateringPlanListView(ListView):
    model = WateringPlan
    template_name = 'smart_greenhouse/watering_plan_list.html'
    context_object_name = 'plans'
    paginate_by = 10

    def get_queryset(self):
        return WateringPlan.objects.select_related('greenhouse_config').all().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['upcoming_cycles'] = WateringCycle.objects.filter(
            scheduled_time__gte=timezone.now(),
            status='pending'
        ).select_related('plan').order_by('scheduled_time')[:10]
        return context


def create_plan_view(request):
    """Create a new watering plan (container for cycles)."""
    if request.method == 'POST':
        try:
            name = request.POST.get('name', '').strip()
            description = request.POST.get('description', '').strip() or None
            greenhouse_id = request.POST.get('greenhouse_config')
            start_date_raw = request.POST.get('start_date') or None
            end_date_raw = request.POST.get('end_date') or None
            active = request.POST.get('active') == 'on'

            auto_create_cycles = request.POST.get('auto_create_cycles') == 'on'
            schedule_type = request.POST.get('schedule_type', 'daily')
            interval_days = int(request.POST.get('interval_days', 1) or 1)
            weekly_day = int(request.POST.get('weekly_day', 0) or 0)
            cycle_description = request.POST.get('cycle_description', '').strip() or None
            cycle_device = request.POST.get('device', '0x540f57fffe890af8')

            # Parse multiple cycle times and durations
            cycle_times_raw = request.POST.getlist('cycle_times')
            cycle_durations_raw = request.POST.getlist('cycle_durations')

            start_date = datetime.fromisoformat(start_date_raw).date() if start_date_raw else None
            end_date = datetime.fromisoformat(end_date_raw).date() if end_date_raw else None

            if not name:
                raise ValueError('Plāna nosaukums ir obligāts')

            if start_date and end_date and end_date < start_date:
                raise ValueError('Beigu datumam jābūt pēc sākuma datuma')

            if auto_create_cycles:
                if not start_date or not end_date:
                    raise ValueError('Lai automātiski izveidotu ciklus, jānorāda sākuma un beigu datums')
                if schedule_type not in ['daily', 'interval', 'weekly']:
                    raise ValueError('Nederīgs atkārtošanās tips')
                if interval_days < 1 or interval_days > 7:
                    raise ValueError('Intervālam jābūt no 1 līdz 7 dienām')
                if weekly_day < 0 or weekly_day > 6:
                    raise ValueError('Nederīga nedēļas diena')
                if not cycle_times_raw:
                    raise ValueError('Jānorāda vismaz viena laistīšanas reice')

            # Parse and validate cycle times/durations
            cycle_schedule = []
            if auto_create_cycles and cycle_times_raw:
                for time_str, duration_str in zip(cycle_times_raw, cycle_durations_raw):
                    try:
                        cycle_time = datetime.strptime(time_str, '%H:%M').time()
                        cycle_duration = int(duration_str)
                        if cycle_duration < 1 or cycle_duration > 3600:
                            raise ValueError(f'Cikla ilgumam {time_str} jābūt no 1 līdz 3600 sekundēm')
                        cycle_schedule.append((cycle_time, cycle_duration))
                    except (ValueError, IndexError) as e:
                        raise ValueError(f'Kļūda laistīšanas reices {time_str} apstrādē: {str(e)}')

            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            plan_id = f"plan_{timestamp}_{unique_id}"

            greenhouse = None
            if greenhouse_id:
                greenhouse = get_object_or_404(GreenhouseConfig, pk=greenhouse_id)

            plan = WateringPlan.objects.create(
                id=plan_id,
                name=name,
                description=description,
                greenhouse_config=greenhouse,
                start_date=start_date,
                end_date=end_date,
                active=active,
            )

            created_cycles = 0
            if auto_create_cycles:
                current_date = start_date
                max_cycles = 500

                while current_date <= end_date and created_cycles < max_cycles:
                    should_create = False

                    if schedule_type == 'daily':
                        should_create = True
                    elif schedule_type == 'interval':
                        day_diff = (current_date - start_date).days
                        should_create = (day_diff % interval_days) == 0
                    elif schedule_type == 'weekly':
                        should_create = current_date.weekday() == weekly_day

                    if should_create:
                        # Create a cycle for each scheduled time
                        for cycle_time, cycle_duration in cycle_schedule:
                            cycle_timestamp = int(time.time())
                            cycle_unique_id = str(uuid.uuid4())[:8]
                            cycle_id = f"cycle_{cycle_timestamp}_{cycle_unique_id}"

                            scheduled_dt = datetime.combine(current_date, cycle_time)
                            WateringCycle.objects.create(
                                id=cycle_id,
                                plan=plan,
                                scheduled_time=scheduled_dt,
                                duration=cycle_duration,
                                device=cycle_device,
                                description=cycle_description,
                                status='pending'
                            )
                            created_cycles += 1

                    current_date += timedelta(days=1)

            if auto_create_cycles:
                messages.success(request, f'Laistīšanas plāns {plan_id} veiksmīgi izveidots ar {created_cycles} cikliem!')
            else:
                messages.success(request, f'Laistīšanas plāns {plan_id} veiksmīgi izveidots!')
            return redirect('irrigation:plan_list')
        except Exception as e:
            messages.error(request, f'Kļūda izveidojot plānu: {str(e)}')

    active_greenhouse = GreenhouseConfig.get_config()
    all_greenhouses = GreenhouseConfig.objects.all().order_by('name')
    context = {
        'active_greenhouse': active_greenhouse,
        'all_greenhouses': all_greenhouses,
    }
    return render(request, 'smart_greenhouse/create_watering_plan.html', context)


def plan_detail_view(request, plan_id):
    """View watering plan details and assigned cycles."""
    plan = get_object_or_404(WateringPlan, id=plan_id)
    assigned_cycles = plan.cycles.all().order_by('-scheduled_time')
    unassigned_cycles = WateringCycle.objects.filter(plan__isnull=True, status='pending').order_by('scheduled_time')[:50]

    return render(request, 'smart_greenhouse/watering_plan_detail.html', {
        'plan': plan,
        'assigned_cycles': assigned_cycles,
        'unassigned_cycles': unassigned_cycles,
    })


def delete_plan_view(request, plan_id):
    """Delete watering plan and unassign related cycles."""
    plan = get_object_or_404(WateringPlan, id=plan_id)

    if request.method == 'POST':
        WateringCycle.objects.filter(plan=plan).update(plan=None)
        plan.delete()
        messages.success(request, f'Plāns {plan_id} veiksmīgi dzēsts!')
        return redirect('irrigation:plan_list')

    return render(request, 'smart_greenhouse/confirm_delete_plan.html', {'plan': plan})


def assign_cycle_to_plan_view(request, plan_id, cycle_id):
    """Assign existing cycle to plan."""
    plan = get_object_or_404(WateringPlan, id=plan_id)
    cycle = get_object_or_404(WateringCycle, id=cycle_id)

    if request.method == 'POST':
        cycle.plan = plan
        cycle.save(update_fields=['plan', 'updated_at'])
        messages.success(request, f'Cikls {cycle.id} pievienots plānam {plan.name}.')

    return redirect('irrigation:plan_detail', plan_id=plan.id)


def unassign_cycle_from_plan_view(request, plan_id, cycle_id):
    """Remove cycle from plan (cycle remains existing)."""
    plan = get_object_or_404(WateringPlan, id=plan_id)
    cycle = get_object_or_404(WateringCycle, id=cycle_id, plan=plan)

    if request.method == 'POST':
        cycle.plan = None
        cycle.save(update_fields=['plan', 'updated_at'])
        messages.success(request, f'Cikls {cycle.id} noņemts no plāna {plan.name}.')

    return redirect('irrigation:plan_detail', plan_id=plan.id)


def system_status_view(request):
    """System status and monitoring"""
    context = {
        'current_time': timezone.now(),
        'system_status': 'operational',  # TODO: Add real system checks
    }
    return render(request, 'smart_greenhouse/system_status.html', context)


def temperature_dashboard_view(request):
    """Temperature sensor dashboard view"""
    now = timezone.now()
    active_greenhouse = GreenhouseConfig.get_config()
    soil_sensor_id = '0xa4c138a5cfe7b9f0'

    def reading_value(reading, key):
        if not reading:
            return None
        if isinstance(reading, dict):
            return reading.get(key)
        return getattr(reading, key, None)

    def unique_identifiers(values):
        return [value for value in dict.fromkeys(values) if value]

    def choose_latest_record(orm_record, measurement_record):
        orm_ts = reading_value(orm_record, 'timestamp')
        measurement_ts = reading_value(measurement_record, 'timestamp')
        if measurement_record and (not orm_record or (measurement_ts and orm_ts and measurement_ts > orm_ts) or (measurement_ts and not orm_ts)):
            return measurement_record
        return orm_record

    def merge_temperature_stats(orm_stats, measurement_stats):
        max_values = [value for value in [
            orm_stats.get('sensor_max_temperature') if orm_stats else None,
            measurement_stats.get('sensor_max_temperature') if measurement_stats else None,
        ] if value is not None]
        min_values = [value for value in [
            orm_stats.get('sensor_min_temperature') if orm_stats else None,
            measurement_stats.get('sensor_min_temperature') if measurement_stats else None,
        ] if value is not None]
        return {
            'sensor_max_temperature': max(max_values) if max_values else None,
            'sensor_min_temperature': min(min_values) if min_values else None,
        }

    def build_sensor_payload(latest_reading, raw_payload):
        raw_payload = raw_payload if isinstance(raw_payload, dict) else {}

        temperature_value = reading_value(latest_reading, 'temperature') if reading_value(latest_reading, 'temperature') is not None else raw_payload.get('temperature')
        humidity_value = reading_value(latest_reading, 'humidity') if reading_value(latest_reading, 'humidity') is not None else raw_payload.get('humidity')
        linkquality_value = reading_value(latest_reading, 'linkquality') if reading_value(latest_reading, 'linkquality') is not None else raw_payload.get('linkquality')

        return {
            'temperature': temperature_value,
            'humidity': humidity_value,
            'linkquality': linkquality_value,
            'battery': reading_value(latest_reading, 'battery') if reading_value(latest_reading, 'battery') is not None else raw_payload.get('battery'),
            'soil_moisture': raw_payload.get('soil_moisture'),
            'temperature_unit': raw_payload.get('temperature_unit', 'celsius'),
            'temperature_unit_convert': raw_payload.get('temperature_unit_convert', 'celsius'),
        }

    def fetch_latest_measurement(device_identifiers):
        identifiers = [identifier for identifier in device_identifiers if identifier]
        if not identifiers:
            return None
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT device_name, temperature, humidity, linkquality, battery,
                       soil_moisture, max_temperature, min_temperature,
                       temperature_unit, raw_data, timestamp
                FROM sensor_measurements
                WHERE device_name = ANY(%s)
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                [identifiers],
            )
            row = cursor.fetchone()

        if not row:
            return None

        return {
            'device_name': row[0],
            'temperature': row[1],
            'humidity': row[2],
            'linkquality': row[3],
            'battery': row[4],
            'soil_moisture': row[5],
            'max_temperature': row[6],
            'min_temperature': row[7],
            'temperature_unit': row[8],
            'raw_data': row[9],
            'timestamp': row[10],
            'formatted_timestamp': row[10].strftime('%Y-%m-%d %H:%M:%S') if row[10] else None,
        }

    def fetch_measurement_stats(device_identifiers):
        identifiers = [identifier for identifier in device_identifiers if identifier]
        if not identifiers:
            return {'sensor_max_temperature': None, 'sensor_min_temperature': None}
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT MAX(temperature) AS sensor_max_temperature,
                       MIN(temperature) AS sensor_min_temperature
                FROM sensor_measurements
                WHERE device_name = ANY(%s)
                """,
                [identifiers],
            )
            row = cursor.fetchone()

        return {
            'sensor_max_temperature': row[0] if row else None,
            'sensor_min_temperature': row[1] if row else None,
        }

    greenhouse_devices = Device.objects.none()
    sensor_query = SensorData.objects.all()

    if active_greenhouse:
        greenhouse_devices = Device.objects.filter(greenhouse=active_greenhouse, active=True).exclude(
            name__iexact='Laistīšanas vārsts'
        ).exclude(
            device_type='irrigation_controller'
        ).order_by('name')
        device_ids = list(greenhouse_devices.values_list('zigbee_id', flat=True))
        device_names = list(greenhouse_devices.values_list('name', flat=True))
        if device_ids or device_names:
            sensor_query = SensorData.objects.filter(
                Q(device_name__in=device_ids) | Q(device_name__in=device_names)
            )

    # Build latest readings per selected greenhouse sensor device.
    latest_readings = []
    if greenhouse_devices.exists():
        for device in greenhouse_devices:
            device_identifiers = unique_identifiers([device.zigbee_id, device.name])
            device_readings = sensor_query.filter(
                Q(device_name=device.zigbee_id) | Q(device_name=device.name)
            )
            latest = device_readings.order_by('-timestamp').first()
            latest_fallback = fetch_latest_measurement(device_identifiers)

            orm_stats = device_readings.aggregate(
                sensor_max_temperature=Max('temperature'),
                sensor_min_temperature=Min('temperature')
            )
            measurement_stats = fetch_measurement_stats(device_identifiers)
            device_stats = merge_temperature_stats(orm_stats, measurement_stats)

            latest_record = choose_latest_record(latest, latest_fallback)
            raw_data = reading_value(latest_record, 'raw_data') if isinstance(reading_value(latest_record, 'raw_data'), dict) else {}
            payload_fields = build_sensor_payload(latest_record, raw_data)
            is_soil_sensor = str(device.zigbee_id).lower() == soil_sensor_id
            latest_readings.append({
                'device_name': device.zigbee_id,
                'device_label': device.name,
                'device_type': device.device_type,
                'reading': latest_record,
                'temperature': payload_fields.get('temperature'),
                'humidity': payload_fields.get('humidity'),
                'linkquality': payload_fields.get('linkquality'),
                'battery': payload_fields.get('battery'),
                'soil_moisture': payload_fields.get('soil_moisture') if is_soil_sensor else None,
                'temperature_unit': payload_fields.get('temperature_unit') if is_soil_sensor else payload_fields.get('temperature_unit_convert'),
                'latest_max_temperature': raw_data.get('max_temperature', reading_value(latest_record, 'max_temperature')),
                'latest_min_temperature': raw_data.get('min_temperature', reading_value(latest_record, 'min_temperature')),
                'sensor_max_temperature': device_stats.get('sensor_max_temperature'),
                'sensor_min_temperature': device_stats.get('sensor_min_temperature'),
            })
    else:
        # Fallback for setups without registered greenhouse devices.
        orm_device_names = set(sensor_query.values_list('device_name', flat=True).distinct())
        with connection.cursor() as cursor:
            cursor.execute("SELECT DISTINCT device_name FROM sensor_measurements")
            measurement_device_names = {row[0] for row in cursor.fetchall() if row and row[0]}

        for device_name in sorted(orm_device_names.union(measurement_device_names)):
            if str(device_name).strip().lower() == 'laistīšanas vārsts':
                continue
            latest = sensor_query.filter(device_name=device_name).order_by('-timestamp').first()
            latest_fallback = fetch_latest_measurement([device_name])

            orm_stats = sensor_query.filter(device_name=device_name).aggregate(
                sensor_max_temperature=Max('temperature'),
                sensor_min_temperature=Min('temperature')
            )
            measurement_stats = fetch_measurement_stats([device_name])
            device_stats = merge_temperature_stats(orm_stats, measurement_stats)

            latest_record = choose_latest_record(latest, latest_fallback)
            raw_data = reading_value(latest_record, 'raw_data') if isinstance(reading_value(latest_record, 'raw_data'), dict) else {}
            payload_fields = build_sensor_payload(latest_record, raw_data)
            is_soil_sensor = str(device_name).lower() == soil_sensor_id
            latest_readings.append({
                'device_name': device_name,
                'device_label': device_name,
                'device_type': 'other',
                'reading': latest_record,
                'temperature': payload_fields.get('temperature'),
                'humidity': payload_fields.get('humidity'),
                'linkquality': payload_fields.get('linkquality'),
                'battery': payload_fields.get('battery'),
                'soil_moisture': payload_fields.get('soil_moisture') if is_soil_sensor else None,
                'temperature_unit': payload_fields.get('temperature_unit') if is_soil_sensor else payload_fields.get('temperature_unit_convert'),
                'latest_max_temperature': raw_data.get('max_temperature', reading_value(latest_record, 'max_temperature')),
                'latest_min_temperature': raw_data.get('min_temperature', reading_value(latest_record, 'min_temperature')),
                'sensor_max_temperature': device_stats.get('sensor_max_temperature'),
                'sensor_min_temperature': device_stats.get('sensor_min_temperature'),
            })
    
    # Get statistics for the last 24 hours
    twenty_four_hours_ago = now - timezone.timedelta(hours=24)
    recent_data = sensor_query.filter(timestamp__gte=twenty_four_hours_ago)
    
    stats = recent_data.aggregate(
        max_temperature=Max('temperature'),
        min_temperature=Min('temperature'),
        total_readings=Count('id')
    )
    measurement_identifiers = []
    if active_greenhouse and greenhouse_devices.exists():
        measurement_identifiers = unique_identifiers(
            list(greenhouse_devices.values_list('zigbee_id', flat=True)) +
            list(greenhouse_devices.values_list('name', flat=True))
        )

    with connection.cursor() as cursor:
        if measurement_identifiers:
            cursor.execute(
                """
                SELECT MAX(temperature), MIN(temperature), COUNT(*)
                FROM sensor_measurements
                WHERE timestamp >= %s AND device_name = ANY(%s)
                """,
                [twenty_four_hours_ago, measurement_identifiers],
            )
        else:
            cursor.execute(
                """
                SELECT MAX(temperature), MIN(temperature), COUNT(*)
                FROM sensor_measurements
                WHERE timestamp >= %s
                """,
                [twenty_four_hours_ago],
            )
        measurement_stats = cursor.fetchone()

    stats = {
        'max_temperature': measurement_stats[0] if measurement_stats else stats.get('max_temperature'),
        'min_temperature': measurement_stats[1] if measurement_stats else stats.get('min_temperature'),
        'total_readings': measurement_stats[2] if measurement_stats else stats.get('total_readings', 0),
    }
    
    # Get hourly averages for the last 24 hours for charting
    hourly_data = []
    for hour in range(24):
        hour_start = now - timezone.timedelta(hours=hour+1)
        hour_end = now - timezone.timedelta(hours=hour)
        
        with connection.cursor() as cursor:
            if measurement_identifiers:
                cursor.execute(
                    """
                    SELECT AVG(temperature), AVG(humidity)
                    FROM sensor_measurements
                    WHERE timestamp >= %s AND timestamp < %s AND device_name = ANY(%s)
                    """,
                    [hour_start, hour_end, measurement_identifiers],
                )
            else:
                cursor.execute(
                    """
                    SELECT AVG(temperature), AVG(humidity)
                    FROM sensor_measurements
                    WHERE timestamp >= %s AND timestamp < %s
                    """,
                    [hour_start, hour_end],
                )
            measurement_hour_avg = cursor.fetchone()

        hour_avg = {
            'avg_temp': measurement_hour_avg[0] if measurement_hour_avg else None,
            'avg_humidity': measurement_hour_avg[1] if measurement_hour_avg else None,
        }
        
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
        'device_count': len(latest_readings),
        'active_greenhouse': active_greenhouse,
    }
    
    return render(request, 'smart_greenhouse/temperature_dashboard.html', context)


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
    def _normalize_row(row):
        row = row or {}
        ts = row.get('timestamp')
        temperature = row.get('temperature')
        raw_data = row.get('raw_data') if isinstance(row.get('raw_data'), dict) else {}
        return {
            'device_name': row.get('device_name'),
            'temperature': temperature,
            'humidity': row.get('humidity'),
            'linkquality': row.get('linkquality'),
            'max_temperature': row.get('max_temperature'),
            'temperature_unit': row.get('temperature_unit') or raw_data.get('temperature_unit') or raw_data.get('temperature_unit_convert') or 'celsius',
            'raw_data': raw_data,
            'timestamp': ts,
            'formatted_timestamp': ts.strftime('%Y-%m-%d %H:%M:%S') if ts else None,
            'temperature_fahrenheit': ((float(temperature) * 9 / 5) + 32) if temperature is not None else None,
            'get_raw_data_pretty': json.dumps(raw_data, indent=2) if raw_data else '',
        }

    def _resolve_identifiers(initial_name):
        identifiers = [initial_name]
        device_match = Device.objects.filter(Q(zigbee_id=initial_name) | Q(name=initial_name)).first()
        if device_match:
            identifiers.extend([device_match.zigbee_id, device_match.name])
        # Keep order and remove empties/duplicates
        return [value for value in dict.fromkeys(identifiers) if value]

    identifiers = _resolve_identifiers(device_name)

    # Load latest and recent readings from Timescale measurements table.
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT device_name, temperature, humidity, linkquality, max_temperature,
                   temperature_unit, raw_data, timestamp
            FROM sensor_measurements
            WHERE device_name = ANY(%s)
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            [identifiers],
        )
        latest_row = cursor.fetchone()

        cursor.execute(
            """
            SELECT device_name, temperature, humidity, linkquality, max_temperature,
                   temperature_unit, raw_data, timestamp
            FROM sensor_measurements
            WHERE device_name = ANY(%s)
              AND timestamp >= NOW() - INTERVAL '7 days'
            ORDER BY timestamp DESC
            LIMIT 100
            """,
            [identifiers],
        )
        recent_rows = cursor.fetchall()

        cursor.execute(
            """
            SELECT AVG(temperature), MAX(temperature), MIN(temperature),
                   AVG(humidity), MAX(humidity), MIN(humidity), COUNT(*)
            FROM sensor_measurements
            WHERE device_name = ANY(%s)
              AND timestamp >= NOW() - INTERVAL '7 days'
            """,
            [identifiers],
        )
        stats_row = cursor.fetchone()

    if not latest_row:
        messages.error(request, f'Dati nav atrasti ierīcei: {device_name}')
        return redirect('irrigation:sensor_dashboard')

    latest_reading = _normalize_row({
        'device_name': latest_row[0],
        'temperature': latest_row[1],
        'humidity': latest_row[2],
        'linkquality': latest_row[3],
        'max_temperature': latest_row[4],
        'temperature_unit': latest_row[5],
        'raw_data': latest_row[6],
        'timestamp': latest_row[7],
    })

    readings = [
        _normalize_row({
            'device_name': row[0],
            'temperature': row[1],
            'humidity': row[2],
            'linkquality': row[3],
            'max_temperature': row[4],
            'temperature_unit': row[5],
            'raw_data': row[6],
            'timestamp': row[7],
        })
        for row in recent_rows
    ]

    stats = {
        'avg_temperature': stats_row[0] if stats_row else None,
        'max_temperature': stats_row[1] if stats_row else None,
        'min_temperature': stats_row[2] if stats_row else None,
        'avg_humidity': stats_row[3] if stats_row else None,
        'max_humidity': stats_row[4] if stats_row else None,
        'min_humidity': stats_row[5] if stats_row else None,
        'total_readings': stats_row[6] if stats_row else 0,
    }
    
    context = {
        'device_name': latest_reading.get('device_name') or device_name,
        'latest_reading': latest_reading,
        'recent_readings': readings,
        'stats': stats,
    }
    
    return render(request, 'smart_greenhouse/sensor_detail.html', context)


def _insert_sensor_measurement(reading_data, timestamp):
    """Insert into TimescaleDB hypertable while keeping Django model compatibility."""
    raw_payload = reading_data.get('raw_data') if isinstance(reading_data.get('raw_data'), dict) else {}

    def pick(*keys, default=None):
        for key in keys:
            if key in reading_data and reading_data.get(key) is not None:
                return reading_data.get(key)
            if key in raw_payload and raw_payload.get(key) is not None:
                return raw_payload.get(key)
        return default

    device_name = pick('device_name')
    topic = pick('topic')
    if not topic and device_name:
        topic = f"zigbee2mqtt/{device_name}"

    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO sensor_measurements (
                device_name, topic, temperature, humidity, linkquality,
                battery, max_temperature, min_temperature, temperature_sensitivity,
                temperature_calibration, temperature_sampling, temperature_unit,
                humidity_calibration, soil_moisture, soil_calibration, soil_sampling,
                soil_warning, dry, raw_data, timestamp
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            """,
            [
                device_name,
                topic,
                pick('temperature'),
                pick('humidity'),
                pick('linkquality'),
                pick('battery'),
                pick('max_temperature'),
                pick('min_temperature'),
                pick('temperature_sensitivity'),
                pick('temperature_calibration'),
                pick('temperature_sampling'),
                pick('temperature_unit', 'temperature_unit_convert', default='celsius'),
                pick('humidity_calibration'),
                pick('soil_moisture'),
                pick('soil_calibration'),
                pick('soil_sampling'),
                pick('soil_warning'),
                pick('dry'),
                json.dumps(reading_data.get('raw_data')) if reading_data.get('raw_data') is not None else None,
                timestamp,
            ],
        )


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
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp, timezone.utc)
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

                # Also store in Timescale hypertable for Grafana time-series workloads.
                _insert_sensor_measurement(reading_data, timestamp)
                
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

def _feature_enabled(feature_name, default=True):
    """Return active greenhouse feature state with a safe default."""
    active_greenhouse = GreenhouseConfig.get_config()
    if not active_greenhouse:
        return default
    return bool(getattr(active_greenhouse, feature_name, default))


def _redirect_feature_disabled(request, feature_title):
    """Redirect user to setup when a feature is disabled."""
    messages.warning(request, f'Funkcija "{feature_title}" ir atspējota aktīvajā siltumnīcā. Iespējojiet to iestatījumos.')
    return redirect('irrigation:setup')

class PlantListView(ListView):
    """List all plants with pagination"""
    model = Plant
    template_name = 'smart_greenhouse/plant_list.html'
    context_object_name = 'plants'
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        if not _feature_enabled('feature_plants', default=True):
            return _redirect_feature_disabled(request, 'Augi')
        return super().dispatch(request, *args, **kwargs)
    
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
    if not _feature_enabled('feature_plants', default=True):
        return _redirect_feature_disabled(request, 'Augi')

    now = timezone.now()
    today = now.date()
    
    # Greenhouse context
    active_greenhouse = GreenhouseConfig.get_config()
    all_greenhouses = GreenhouseConfig.objects.all().order_by('name')
    
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
        'active_greenhouse': active_greenhouse,
        'all_greenhouses': all_greenhouses,
    }
    
    return render(request, 'smart_greenhouse/plant_dashboard.html', context)


def plant_detail_view(request, plant_id):
    """View details of a specific plant (FR-16)"""
    if not _feature_enabled('feature_plants', default=True):
        return _redirect_feature_disabled(request, 'Augi')

    plant = get_object_or_404(Plant, id=plant_id)
    
    context = {
        'plant': plant,
        'can_edit': plant.active,  # Only allow editing of active plants
    }
    
    return render(request, 'smart_greenhouse/plant_detail.html', context)


def create_plant_view(request):
    """Create a new plant registration (FR-9)"""
    if not _feature_enabled('feature_plants', default=True):
        return _redirect_feature_disabled(request, 'Augi')

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
                return render(request, 'smart_greenhouse/create_plant.html')
            
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
    
    return render(request, 'smart_greenhouse/create_plant.html')


def edit_plant_view(request, plant_id):
    """Edit plant information (FR-16)"""
    if not _feature_enabled('feature_plants', default=True):
        return _redirect_feature_disabled(request, 'Augi')

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
                    return render(request, 'smart_greenhouse/edit_plant.html', {'plant': plant})
            
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
    return render(request, 'smart_greenhouse/edit_plant.html', context)


def deactivate_plant_view(request, plant_id):
    """Deactivate plant (soft delete)"""
    if not _feature_enabled('feature_plants', default=True):
        return _redirect_feature_disabled(request, 'Augi')

    plant = get_object_or_404(Plant, id=plant_id)
    
    if request.method == 'POST':
        plant.active = False
        plant.save()
        messages.success(request, f'Augs "{plant.name}" veiksmīgi deaktivizēts!')
        return redirect('irrigation:plant_dashboard')
    
    return render(request, 'smart_greenhouse/confirm_deactivate_plant.html', {'plant': plant})


@ensure_csrf_cookie
def greenhouse_layout_view(request):
    """Display greenhouse layout with plant positions and paths (FR-15)"""
    if not _feature_enabled('feature_layout', default=True):
        return _redirect_feature_disabled(request, 'Siltumnīcas izkārtojums')

    # Greenhouse context
    active_greenhouse = GreenhouseConfig.get_config()
    all_greenhouses = GreenhouseConfig.objects.all().order_by('name')

    # Resolve layout size keys per active greenhouse
    if active_greenhouse:
        rows_key = f'layout_rows_{active_greenhouse.pk}'
        columns_key = f'layout_columns_{active_greenhouse.pk}'
    else:
        rows_key = 'layout_rows_default'
        columns_key = 'layout_columns_default'

    def _safe_grid_size(value, default):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return max(5, min(20, parsed))

    # Update size via POST
    if request.method == 'POST':
        max_rows = _safe_grid_size(request.POST.get('rows'), 10)
        max_columns = _safe_grid_size(request.POST.get('columns'), 10)

        request.session[rows_key] = max_rows
        request.session[columns_key] = max_columns

        return JsonResponse({
            'success': True,
            'rows': max_rows,
            'columns': max_columns,
        })

    # Read persisted size for GET (query params still allowed as fallback)
    default_rows = request.session.get(rows_key, 10)
    default_columns = request.session.get(columns_key, 10)
    max_rows = _safe_grid_size(request.GET.get('rows'), default_rows)
    max_columns = _safe_grid_size(request.GET.get('columns'), default_columns)
    
    # Get all active plants and path cells
    plants = Plant.objects.filter(active=True)
    paths = PathCell.objects.all()
    
    # Create a simple grid structure for the template
    grid_data = []
    for row in range(1, max_rows + 1):
        row_data = []
        for col in range(1, max_columns + 1):
            # Find plant at this position
            plant_at_position = plants.filter(location_row=row, location_column=col).first()
            # Find path at this position
            path_at_position = paths.filter(row=row, column=col).first()
            
            if plant_at_position:
                row_data.append({
                    'cell_type': 'plant',
                    'has_plant': True,
                    'plant': plant_at_position,
                    'has_path': False,
                    'path': None,
                    'row': row,
                    'col': col
                })
            elif path_at_position:
                row_data.append({
                    'cell_type': 'path',
                    'has_plant': False,
                    'plant': None,
                    'has_path': True,
                    'path': path_at_position,
                    'row': row,
                    'col': col
                })
            else:
                row_data.append({
                    'cell_type': 'empty',
                    'has_plant': False,
                    'plant': None,
                    'has_path': False,
                    'path': None,
                    'row': row,
                    'col': col
                })
        grid_data.append(row_data)
    
    context = {
        'grid_data': grid_data,
        'max_rows': max_rows,
        'max_columns': max_columns,
        'row_range': range(1, max_rows + 1),
        'column_range': range(1, max_columns + 1),
        'active_greenhouse': active_greenhouse,
        'all_greenhouses': all_greenhouses,
    }
    
    return render(request, 'smart_greenhouse/greenhouse_layout.html', context)


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
            }
    
    return layout


# API endpoints for plants
@csrf_exempt
def plants_api(request):
    """API endpoint for plant data (for AJAX requests)"""
    if not _feature_enabled('feature_plants', default=True):
        return JsonResponse({'success': False, 'error': 'Augu modulis ir atspējots aktīvajā siltumnīcā.'}, status=403)

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
                'active': plant.active
            })
        
        return JsonResponse({
            'status': 'success',
            'plants': plants_data,
            'count': len(plants_data)
        })
    
    elif request.method == 'POST':
        try:
            # Parse JSON data
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'location_row', 'location_column', 'planting_date', 'watering_frequency', 'watering_duration']
            for field in required_fields:
                if field not in data or not data[field]:
                    return JsonResponse({'success': False, 'error': f'Nepieciešams lauks: {field}'}, status=400)
            
            # Check if location is already occupied
            existing_plant = Plant.objects.filter(
                location_row=int(data['location_row']),
                location_column=int(data['location_column']),
                active=True
            ).first()
            
            if existing_plant:
                return JsonResponse({
                    'success': False, 
                    'error': f'Pozīcija jau ir aizņemta ar augu "{existing_plant.name}"'
                }, status=400)
            
            # Parse dates
            try:
                planting_date = datetime.strptime(data['planting_date'], '%Y-%m-%d').date()
            except ValueError:
                return JsonResponse({'success': False, 'error': 'Nepareizs stādīšanas datuma formāts'}, status=400)
            
            harvest_date = None
            if data.get('harvest_date_estimate'):
                try:
                    harvest_date = datetime.strptime(data['harvest_date_estimate'], '%Y-%m-%d').date()
                except ValueError:
                    return JsonResponse({'success': False, 'error': 'Nepareizs ražas datuma formāts'}, status=400)
            
            # Create the plant
            plant = Plant.objects.create(
                name=data['name'],
                variety=data.get('variety', ''),
                planting_date=planting_date,
                watering_frequency=int(data['watering_frequency']),
                watering_duration=int(data['watering_duration']),
                water_amount_ml=int(data.get('water_amount_ml', 500)),
                harvest_date_estimate=harvest_date,
                harvest_quantity_estimate=float(data.get('harvest_quantity_estimate', 0)) if data.get('harvest_quantity_estimate') else None,
                location_row=int(data['location_row']),
                location_column=int(data['location_column']),
                location_description=data.get('location_description', ''),
                notes=data.get('notes', ''),
                active=True
            )
            
            return JsonResponse({
                'success': True,
                'plant': {
                    'id': plant.id,
                    'name': plant.name,
                    'variety': plant.variety,
                    'location': plant.location_coordinate,
                    'planting_date': plant.planting_date.isoformat()
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Nepareizi JSON dati'}, status=400)
        except ValueError as e:
            return JsonResponse({'success': False, 'error': f'Datu kļūda: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Servera kļūda: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# API endpoint for path management
@csrf_exempt
def paths_api(request):
    """API endpoint for path data (for AJAX requests)"""
    if not _feature_enabled('feature_layout', default=True):
        return JsonResponse({'success': False, 'error': 'Izkārtojuma modulis ir atspējots aktīvajā siltumnīcā.'}, status=403)

    if request.method == 'GET':
        # Get all path cells
        paths = PathCell.objects.all()
        
        paths_data = []
        for path in paths:
            paths_data.append({
                'row': path.row,
                'column': path.column,
                'location': path.location_coordinate,
                'description': path.description,
                'created_at': path.created_at.isoformat()
            })
        
        return JsonResponse({
            'status': 'success',
            'paths': paths_data,
            'count': len(paths_data)
        })
    
    elif request.method == 'POST':
        try:
            # Parse JSON data
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['row', 'column']
            for field in required_fields:
                if field not in data or not data[field]:
                    return JsonResponse({'success': False, 'error': f'Nepieciešams lauks: {field}'}, status=400)
            
            row = int(data['row'])
            column = int(data['column'])
            
            # Check if location is already occupied by plant
            existing_plant = Plant.objects.filter(
                location_row=row,
                location_column=column,
                active=True
            ).first()
            
            if existing_plant:
                return JsonResponse({
                    'success': False, 
                    'error': f'Pozīcijā R{row}C{column} jau ir novietots augs "{existing_plant.name}"'
                }, status=400)
            
            # Check if path already exists at this location
            existing_path = PathCell.objects.filter(row=row, column=column).first()
            
            if existing_path:
                return JsonResponse({
                    'success': False, 
                    'error': f'Ceļš jau eksistē pozīcijā R{row}C{column}'
                }, status=400)
            
            # Create the path
            path = PathCell.objects.create(
                row=row,
                column=column,
                description=data.get('description', '')
            )
            
            return JsonResponse({
                'success': True,
                'path': {
                    'row': path.row,
                    'column': path.column,
                    'location': path.location_coordinate,
                    'description': path.description
                }
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Nepareizi JSON dati'}, status=400)
        except ValueError as e:
            return JsonResponse({'success': False, 'error': f'Datu kļūda: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Servera kļūda: {str(e)}'}, status=500)
            
    elif request.method == 'DELETE':
        try:
            # Parse JSON data
            data = json.loads(request.body)
            
            # Validate required fields
            if 'row' not in data or 'column' not in data:
                return JsonResponse({'success': False, 'error': 'Nepieciešami lauki: row, column'}, status=400)
            
            row = int(data['row'])
            column = int(data['column'])
            
            # Find and delete the path
            path = PathCell.objects.filter(row=row, column=column).first()
            
            if not path:
                return JsonResponse({
                    'success': False, 
                    'error': f'Ceļš nav atrasts pozīcijā R{row}C{column}'
                }, status=404)
            
            path.delete()
            
            return JsonResponse({
                'success': True,
                'message': f'Ceļš R{row}C{column} veiksmīgi noņemts'
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Nepareizi JSON dati'}, status=400)
        except ValueError as e:
            return JsonResponse({'success': False, 'error': f'Datu kļūda: {str(e)}'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': f'Servera kļūda: {str(e)}'}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ---------------------------------------------------------------------------
# Setup / Configuration views
# ---------------------------------------------------------------------------

@ensure_csrf_cookie
def setup_view(request):
    """List all greenhouse configurations with their paired devices."""
    greenhouses = GreenhouseConfig.objects.prefetch_related('devices').all().order_by('name')
    active = GreenhouseConfig.get_config()
    return render(request, 'smart_greenhouse/setup.html', {
        'greenhouses': greenhouses,
        'active': active,
        'is_first_setup': not greenhouses.exists(),
        'device_type_choices': Device.DEVICE_TYPE_CHOICES,
    })


def setup_greenhouse_view(request):
    """Create or update a greenhouse record."""
    if request.method == 'POST':
        greenhouse_id = request.POST.get('greenhouse_id', '').strip()
        name = request.POST.get('name', '').strip()
        location = request.POST.get('location', '').strip()
        season = request.POST.get('season', '').strip()
        feature_plants = request.POST.get('feature_plants') == 'on'
        feature_layout = request.POST.get('feature_layout') == 'on'
        feature_meteostation = request.POST.get('feature_meteostation') == 'on'
        feature_watering_liters = request.POST.get('feature_watering_liters') == 'on'
        feature_smart_suggestions = request.POST.get('feature_smart_suggestions') == 'on'

        if not name:
            messages.error(request, 'Siltumnīcas nosaukums ir obligāts.')
            return redirect('irrigation:setup')

        if greenhouse_id:
            config = get_object_or_404(GreenhouseConfig, pk=greenhouse_id)
        else:
            config = GreenhouseConfig()
            # First greenhouse is automatically active
            if not GreenhouseConfig.objects.exists():
                config.is_active = True

        config.name = name
        config.location = location
        config.season = season
        config.feature_plants = feature_plants
        config.feature_layout = feature_layout
        config.feature_meteostation = feature_meteostation
        config.feature_watering_liters = feature_watering_liters
        config.feature_smart_suggestions = feature_smart_suggestions
        config.save()
        messages.success(request, 'Siltumnīcas konfigurācija saglabāta!')
    return redirect('irrigation:setup')


def setup_controller_view(request):
    """Save or update controller connection settings for a specific greenhouse."""
    if request.method == 'POST':
        greenhouse_id = request.POST.get('greenhouse_id', '').strip()
        controller_ip = request.POST.get('controller_ip', '').strip()
        controller_username = request.POST.get('controller_username', '').strip()
        controller_password = request.POST.get('controller_password', '').strip()

        if greenhouse_id:
            config = get_object_or_404(GreenhouseConfig, pk=greenhouse_id)
        else:
            config = GreenhouseConfig.get_config()

        if config is None:
            messages.error(request, 'Vispirms jākonfigurē siltumnīcas pamatdati.')
            return redirect('irrigation:setup')

        config.controller_ip = controller_ip or None
        config.controller_username = controller_username
        if controller_password:
            config.controller_password = controller_password
        config.save()
        messages.success(request, 'Kontrollera iestatījumi saglabāti!')
    return redirect('irrigation:setup')


@require_http_methods(['POST'])
def setup_select_greenhouse_view(request, greenhouse_id):
    """Set a greenhouse as the active one."""
    config = get_object_or_404(GreenhouseConfig, pk=greenhouse_id)
    config.set_active()
    messages.success(request, f'"{config.name}" iestatīta kā aktīvā siltumnīca.')
    return redirect('irrigation:setup')


@require_http_methods(['POST'])
def setup_delete_greenhouse_view(request, greenhouse_id):
    """Delete a greenhouse configuration."""
    config = get_object_or_404(GreenhouseConfig, pk=greenhouse_id)
    was_active = config.is_active
    name = config.name
    config.delete()
    # If deleted was active, promote the next one
    if was_active:
        remaining = GreenhouseConfig.objects.first()
        if remaining:
            remaining.set_active()
    messages.success(request, f'"{name}" dzēsta.')
    return redirect('irrigation:setup')


@require_http_methods(['POST'])
def setup_add_device_view(request, greenhouse_id):
    """Pair (register) a device to a greenhouse."""
    greenhouse = get_object_or_404(GreenhouseConfig, pk=greenhouse_id)
    zigbee_id = request.POST.get('zigbee_id', '').strip()
    name = request.POST.get('name', '').strip()
    device_type = request.POST.get('device_type', 'other').strip()
    notes = request.POST.get('notes', '').strip()

    if not zigbee_id or not name:
        messages.error(request, 'Zigbee ID un nosaukums ir obligāti.')
        return redirect('irrigation:setup')

    try:
        Device.objects.create(
            greenhouse=greenhouse,
            zigbee_id=zigbee_id,
            name=name,
            device_type=device_type,
            notes=notes,
        )
        messages.success(request, f'Ierīce "{name}" pievienota siltumnīcai "{greenhouse.name}".')
    except Exception as exc:
        messages.error(request, f'Kļūda pievienojot ierīci: {exc}')
    return redirect('irrigation:setup')


@require_http_methods(['POST'])
def setup_remove_device_view(request, device_id):
    """Unpair (delete) a device from a greenhouse."""
    device = get_object_or_404(Device, pk=device_id)
    name = device.name
    greenhouse_name = device.greenhouse.name
    device.delete()
    messages.success(request, f'Ierīce "{name}" noņemta no siltumnīcas "{greenhouse_name}".')
    return redirect('irrigation:setup')


@require_http_methods(['POST'])
def setup_pair_device_view(request):
    """Trigger MQTT permit_join so a new Zigbee device can be paired."""
    try:
        import paho.mqtt.publish as publish

        broker = os.environ.get('MQTT_BROKER', 'mosquitto')
        port = int(os.environ.get('MQTT_PORT', 1883))
        duration = int(request.POST.get('duration', 60))

        payload = json.dumps({'value': True, 'time': duration})
        publish.single(
            topic='zigbee2mqtt/bridge/request/permit_join',
            payload=payload,
            hostname=broker,
            port=port,
        )
        return JsonResponse({'success': True, 'message': f'Ierīces savienošana iespējota uz {duration} sekundēm.'})
    except ImportError:
        return JsonResponse({'success': False, 'error': 'paho-mqtt nav instalēts.'}, status=500)
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


def _get_request_payload(request):
    """Parse JSON body when present, otherwise return POST payload."""
    body = request.body
    if body:
        try:
            return json.loads(body)
        except (json.JSONDecodeError, ValueError):
            pass
    if request.POST:
        return request.POST
    return {}


def _extract_mqtt_connection_params(payload):
    """Extract broker credentials and publish duration from request payload."""
    broker = (
        payload.get('broker_ip')
        or payload.get('mqtt_broker')
        or payload.get('broker')
        or os.environ.get('MQTT_BROKER', 'mosquitto')
    )
    port = int(payload.get('port') or payload.get('mqtt_port') or 1883)
    username = payload.get('username') or payload.get('mqtt_username') or os.environ.get('MQTT_USERNAME', 'mosquitto_api_user1')
    password = payload.get('password') or payload.get('mqtt_password') or os.environ.get('MQTT_PASSWORD', 'mosquitto_password$')
    duration = int(payload.get('duration') or 60)
    return broker, port, username, password, duration


def _resolve_greenhouse_mqtt_params(payload):
    """Resolve MQTT connection params from selected greenhouse with request/env fallback."""
    greenhouse_id = payload.get('greenhouse_id')
    broker, port, username, password, duration = _extract_mqtt_connection_params(payload)

    if greenhouse_id:
        greenhouse = GreenhouseConfig.objects.filter(pk=greenhouse_id).first()
        if greenhouse:
            if greenhouse.controller_ip:
                broker = greenhouse.controller_ip
            if greenhouse.controller_username:
                username = greenhouse.controller_username

            stored_password = (greenhouse.controller_password or '').strip()
            # Older records may contain salted hashes and cannot be used for MQTT auth.
            if stored_password and ':' not in stored_password:
                password = stored_password

    if not password:
        password = os.environ.get('MQTT_PASSWORD', 'mosquitto_password$')

    return broker, port, username, password, duration


def _normalize_bridge_state(raw_payload):
    """Normalize zigbee2mqtt/bridge/state payload to online/offline when possible."""
    try:
        parsed = json.loads(raw_payload)
        if isinstance(parsed, dict):
            state_val = str(parsed.get('state', '')).strip().lower()
        else:
            state_val = str(parsed).strip().lower()
    except json.JSONDecodeError:
        state_val = str(raw_payload).strip().lower()

    if state_val in {'online', 'offline'}:
        return state_val
    return 'offline'


@require_http_methods(['GET'])
def api_bridge_state(request):
    """Read current Zigbee2MQTT bridge state from zigbee2mqtt/bridge/state."""
    greenhouse_id = request.GET.get('greenhouse_id')
    broker = os.environ.get('MQTT_BROKER', 'mosquitto')
    port = int(os.environ.get('MQTT_PORT', 1883))
    username = os.environ.get('MQTT_USERNAME', '')
    password = os.environ.get('MQTT_PASSWORD', '')

    if greenhouse_id:
        greenhouse = GreenhouseConfig.objects.filter(pk=greenhouse_id).first()
        if greenhouse:
            if greenhouse.controller_ip:
                broker = greenhouse.controller_ip
            if greenhouse.controller_username:
                username = greenhouse.controller_username
            stored_password = (greenhouse.controller_password or '').strip()
            if stored_password and ':' not in stored_password:
                password = stored_password

    try:
        import paho.mqtt.client as mqtt

        topic = 'zigbee2mqtt/bridge/state'
        state_holder = {'value': 'offline'}
        received_event = threading.Event()

        client = mqtt.Client(protocol=mqtt.MQTTv311)
        if username and password:
            client.username_pw_set(username, password)

        def on_connect(cl, userdata, flags, rc):
            cl.subscribe(topic, qos=0)

        def on_message(cl, userdata, msg):
            raw_payload = msg.payload.decode(errors='replace')
            state_holder['value'] = _normalize_bridge_state(raw_payload)
            received_event.set()

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(broker, port, 10)
        client.loop_start()
        received_event.wait(3)
        client.loop_stop()
        client.disconnect()

        return JsonResponse({
            'success': True,
            'state': state_holder['value'],
            'topic': topic,
            'broker': broker,
            'port': port,
        })
    except ImportError:
        return JsonResponse({'success': False, 'state': 'offline', 'error': 'paho-mqtt nav instalēts.'}, status=500)
    except Exception as exc:
        return JsonResponse({'success': False, 'state': 'offline', 'error': str(exc)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def api_device_pairing(request):
    """Start Zigbee2MQTT pairing via broker credentials provided by client."""
    payload = _get_request_payload(request)
    broker, port, username, password, duration = _resolve_greenhouse_mqtt_params(payload)

    if not broker:
        return JsonResponse({'success': False, 'error': 'broker_ip ir obligāts'}, status=400)
    if not username or not password:
        return JsonResponse({'success': False, 'error': 'mqtt username/password ir obligāti'}, status=400)
    if duration < 10 or duration > 254:
        return JsonResponse({'success': False, 'error': 'duration jābūt no 10 līdz 254 sekundēm'}, status=400)

    try:
        import paho.mqtt.publish as publish

        request_payload = json.dumps({'time': duration})
        publish.single(
            topic='zigbee2mqtt/bridge/request/permit_join',
            payload=request_payload,
            hostname=broker,
            port=port,
            auth={'username': username, 'password': password},
            qos=0,
        )
        return JsonResponse({
            'success': True,
            'message': f'Pairing ieslēgts uz {duration} sekundēm',
            'broker': broker,
            'port': port,
            'request_topic': 'zigbee2mqtt/bridge/request/permit_join',
            'request_payload': {'time': duration},
        })
    except ImportError:
        return JsonResponse({'success': False, 'error': 'paho-mqtt nav instalēts.'}, status=500)
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def api_device_pairing_status(request):
    """Listen briefly for Zigbee2MQTT bridge events and report pairing detection."""
    payload = _get_request_payload(request)
    broker, port, username, password, _ = _resolve_greenhouse_mqtt_params(payload)
    listen_seconds = int(payload.get('listen_seconds') or 8)
    listen_seconds = max(1, min(listen_seconds, 30))

    if not broker:
        return JsonResponse({'success': False, 'error': 'broker_ip ir obligāts'}, status=400)
    if not username or not password:
        return JsonResponse({'success': False, 'error': 'mqtt username/password ir obligāti'}, status=400)

    try:
        import paho.mqtt.client as mqtt

        topic = 'zigbee2mqtt/bridge/event'
        events = []
        paired_detected = False

        client = mqtt.Client(protocol=mqtt.MQTTv311)
        client.username_pw_set(username, password)

        def on_connect(cl, userdata, flags, rc):
            cl.subscribe(topic, qos=0)

        def on_message(cl, userdata, msg):
            nonlocal paired_detected
            raw_payload = msg.payload.decode(errors='replace')
            event_type = None
            parsed_payload = None
            try:
                parsed_payload = json.loads(raw_payload)
                if isinstance(parsed_payload, dict):
                    event_type = str(parsed_payload.get('type') or '').lower()
            except json.JSONDecodeError:
                parsed_payload = raw_payload

            if event_type == 'device_joined':
                paired_detected = True

            events.append({
                'topic': msg.topic,
                'payload': parsed_payload,
                'event_type': event_type,
            })

        client.on_connect = on_connect
        client.on_message = on_message

        client.connect(broker, port, 60)
        client.loop_start()
        time.sleep(listen_seconds)
        client.loop_stop()
        client.disconnect()

        return JsonResponse({
            'success': True,
            'broker': broker,
            'port': port,
            'topic': topic,
            'listen_seconds': listen_seconds,
            'paired_detected': paired_detected,
            'events_count': len(events),
            'events': events[:20],
            'hint': 'Pairing uzskatāms par veiksmīgu, ja zigbee2mqtt/bridge/event satur type=device_joined.',
        })
    except ImportError:
        return JsonResponse({'success': False, 'error': 'paho-mqtt nav instalēts.'}, status=500)
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)
