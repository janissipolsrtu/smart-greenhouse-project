from django.contrib import admin
from .models import IrrigationPlan, SensorData


@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
    list_display = ['device_name', 'temperature', 'humidity', 'linkquality', 'timestamp', 'created_at']
    list_filter = ['device_name', 'temperature_unit', 'timestamp']
    search_fields = ['device_name']
    readonly_fields = ['created_at', 'raw_data']
    ordering = ['-timestamp']
    date_hierarchy = 'timestamp'
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing existing sensor data
            return self.readonly_fields + ['timestamp']  # Make timestamp readonly when editing
        return self.readonly_fields


@admin.register(IrrigationPlan)
class IrrigationPlanAdmin(admin.ModelAdmin):
    list_display = ['id', 'scheduled_time', 'duration', 'status', 'executed_at']
    list_filter = ['status', 'scheduled_time']
    search_fields = ['id']
    readonly_fields = ['executed_at', 'created_at']
    ordering = ['-scheduled_time']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ['id']
        return self.readonly_fields