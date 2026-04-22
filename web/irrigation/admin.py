from django.contrib import admin
from .models import IrrigationPlan, SensorData, Plant


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


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'variety', 'location_coordinate', 'planting_date', 
        'days_since_planting', 'harvest_date_estimate', 'active', 'created_at'
    ]
    list_filter = [
        'active', 'planting_date', 'harvest_date_estimate', 
        'location_row', 'watering_frequency'
    ]
    search_fields = ['name', 'variety', 'notes', 'location_description']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'location_coordinate', 
        'days_since_planting', 'days_to_harvest'
    ]
    ordering = ['-created_at']
    date_hierarchy = 'planting_date'
    
    fieldsets = (
        ('Auga informācija', {
            'fields': ('id', 'name', 'variety', 'active')
        }),
        ('Stādīšanas informācija', {
            'fields': ('planting_date', 'created_at', 'updated_at')
        }),
        ('Atrašanās vieta siltumnīcā', {
            'fields': (
                ('location_row', 'location_column'), 
                'location_coordinate',
                'location_description'
            )
        }),
        ('Laistīšanas vajadzības', {
            'fields': (
                'watering_frequency', 'watering_duration', 'water_amount_ml'
            ),
            'description': 'Auga laistīšanas prasības un grafiks'
        }),
        ('Ražas prognoze', {
            'fields': (
                'harvest_date_estimate', 'harvest_quantity_estimate', 
                'days_to_harvest'
            ),
            'description': 'Prognozētā raža un novākšanas laiks'
        }),
        ('Papildu informācija', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Aprēķinātie dati', {
            'fields': ('days_since_planting',),
            'description': 'Automātiski aprēķinātie lauki'
        })
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields
        # When creating a new object, don't make computed fields readonly
        return ['id', 'created_at', 'updated_at']
    
    def location_coordinate(self, obj):
        """Display location as coordinate"""
        return obj.location_coordinate
    location_coordinate.short_description = 'Koordinātes'
    
    def days_since_planting(self, obj):
        """Display days since planting"""
        return obj.days_since_planting
    days_since_planting.short_description = 'Dienas kopš stādīšanas'
    
    def days_to_harvest(self, obj):
        """Display days to harvest"""
        days = obj.days_to_harvest
        if days is not None:
            return f"{days} dienas" if days > 0 else "Gatavs novākšanai"
        return "Nav norādīts"
    days_to_harvest.short_description = 'Dienas līdz ražai'