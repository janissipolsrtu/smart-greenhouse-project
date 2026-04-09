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
    
    # API endpoints
    path('api/sensor-data/', views.sensor_data_api, name='sensor_data_api'),
    path('api/sensor-data/bulk/', views.bulk_sensor_data_api, name='bulk_sensor_data_api'),
    path('api/health/', views.health_check_api, name='health_check_api'),
]