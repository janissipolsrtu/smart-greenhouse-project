from django.urls import path
from . import views

app_name = 'irrigation'

urlpatterns = [
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
    
    # Temperature Dashboard URLs
    path('temperature/', views.temperature_dashboard_view, name='temperature_dashboard'),
    path('temperature/<str:device_name>/', views.sensor_detail_view, name='sensor_detail'),
    
    # Plant Management URLs
    path('plants/', views.plant_dashboard_view, name='plant_dashboard'),
    path('plants/list/', views.PlantListView.as_view(), name='plant_list'),
    path('plants/create/', views.create_plant_view, name='create_plant'),
    path('plants/<str:plant_id>/', views.plant_detail_view, name='plant_detail'),
    path('plants/<str:plant_id>/edit/', views.edit_plant_view, name='edit_plant'),
    path('plants/<str:plant_id>/deactivate/', views.deactivate_plant_view, name='deactivate_plant'),
    path('layout/', views.greenhouse_layout_view, name='greenhouse_layout'),
    path('plants/harvest-ready/', views.plants_ready_for_harvest_view, name='harvest_ready'),
    
    # API endpoints
    path('api/sensor-data/', views.sensor_data_api, name='sensor_data_api'),
    path('api/sensor-data/bulk/', views.bulk_sensor_data_api, name='bulk_sensor_data_api'),
    path('api/health/', views.health_check_api, name='health_check_api'),
    path('api/plants/', views.plants_api, name='plants_api'),
    path('api/paths/', views.paths_api, name='paths_api'),
]