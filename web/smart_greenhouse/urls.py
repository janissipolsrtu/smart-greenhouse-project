from django.urls import path
from django.views.generic.base import RedirectView
from . import views

app_name = 'irrigation'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('verify-email/<uidb64>/<token>/', views.verify_email_view, name='verify_email'),

    path('', views.dashboard_view, name='dashboard'),
    path('watering/plans/', views.WateringPlanListView.as_view(), name='plan_list'),
    path('watering/plans/create/', views.create_plan_view, name='create_plan'),
    path('watering/plans/<str:plan_id>/', views.plan_detail_view, name='plan_detail'),
    path('watering/plans/<str:plan_id>/delete/', views.delete_plan_view, name='delete_plan'),
    path('watering/plans/<str:plan_id>/assign-cycle/<str:cycle_id>/', views.assign_cycle_to_plan_view, name='assign_cycle_to_plan'),
    path('watering/plans/<str:plan_id>/unassign-cycle/<str:cycle_id>/', views.unassign_cycle_from_plan_view, name='unassign_cycle_from_plan'),

    path('watering/cycles/', views.WateringCycleListView.as_view(), name='cycle_list'),
    path('watering/cycles/create/', views.create_cycle_view, name='create_cycle'),
    path('watering/cycles/<str:cycle_id>/', views.cycle_detail_view, name='cycle_detail'),
    path('watering/cycles/<str:cycle_id>/delete/', views.delete_cycle_view, name='delete_cycle'),
    path('status/', views.system_status_view, name='system_status'),
    
    # Sensor data dashboard URLs
    path('sensor-data/', views.temperature_dashboard_view, name='sensor_dashboard'),
    path('sensor-data/<str:device_name>/', views.sensor_detail_view, name='sensor_detail'),

    # Backward-compatible redirects from old routes
    path('temperature/', RedirectView.as_view(pattern_name='irrigation:sensor_dashboard', permanent=True)),
    path('temperature/<str:device_name>/', RedirectView.as_view(pattern_name='irrigation:sensor_detail', permanent=True)),
    
    # Plant Management URLs
    path('plants/', views.plant_dashboard_view, name='plant_dashboard'),
    path('plants/list/', views.PlantListView.as_view(), name='plant_list'),
    path('plants/create/', views.create_plant_view, name='create_plant'),
    path('plants/<str:plant_id>/', views.plant_detail_view, name='plant_detail'),
    path('plants/<str:plant_id>/edit/', views.edit_plant_view, name='edit_plant'),
    path('plants/<str:plant_id>/deactivate/', views.deactivate_plant_view, name='deactivate_plant'),
    path('layout/', views.greenhouse_layout_view, name='greenhouse_layout'),
    
    # API endpoints
    path('api/sensor-data/', views.sensor_data_api, name='sensor_data_api'),
    path('api/sensor-data/bulk/', views.bulk_sensor_data_api, name='bulk_sensor_data_api'),
    path('api/health/', views.health_check_api, name='health_check_api'),
    path('api/plants/', views.plants_api, name='plants_api'),
    path('api/paths/', views.paths_api, name='paths_api'),
    path('api/bridge-state/', views.api_bridge_state, name='api_bridge_state'),
    path('api/device/pairing/', views.api_device_pairing, name='api_device_pairing'),
    path('api/device/pairing-status/', views.api_device_pairing_status, name='api_device_pairing_status'),

    # Setup / Configuration
    path('setup/', views.setup_view, name='setup'),
    path('setup/greenhouse/', views.setup_greenhouse_view, name='setup_greenhouse'),
    path('setup/controller/', views.setup_controller_view, name='setup_controller'),
    path('setup/pair-device/', views.setup_pair_device_view, name='setup_pair_device'),
    path('setup/<int:greenhouse_id>/select/', views.setup_select_greenhouse_view, name='setup_select'),
    path('setup/<int:greenhouse_id>/delete/', views.setup_delete_greenhouse_view, name='setup_delete'),
    path('setup/<int:greenhouse_id>/add-device/', views.setup_add_device_view, name='setup_add_device'),
    path('setup/device/<int:device_id>/remove/', views.setup_remove_device_view, name='setup_remove_device'),
]