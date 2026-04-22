from django.urls import path
from . import views

app_name = 'irrigation'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('plans/', views.IrrigationPlanListView.as_view(), name='plan_list'),
    path('plans/create/', views.create_plan_view, name='create_plan'),
    path('plans/<str:plan_id>/', views.plan_detail_view, name='plan_detail'),
    path('plans/<str:plan_id>/delete/', views.delete_plan_view, name='delete_plan'),
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
    path('greenhouse/layout/', views.greenhouse_layout_view, name='greenhouse_layout'),
    path('plants/harvest-ready/', views.plants_ready_for_harvest_view, name='harvest_ready'),
    
    # API endpoints
    path('api/sensor-data/', views.sensor_data_api, name='sensor_data_api'),
    path('api/sensor-data/bulk/', views.bulk_sensor_data_api, name='bulk_sensor_data_api'),
    path('api/health/', views.health_check_api, name='health_check_api'),
    path('api/plants/', views.plants_api, name='plants_api'),
]