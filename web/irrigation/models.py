from django.db import models
from django.utils import timezone
import json


class SensorData(models.Model):
    """Model for storing sensor data from MQTT devices"""
    
    id = models.AutoField(primary_key=True)
    device_name = models.CharField(max_length=100, help_text="Name of the sensor device")
    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Temperature in Celsius")
    humidity = models.IntegerField(null=True, blank=True, help_text="Humidity percentage")
    linkquality = models.IntegerField(null=True, blank=True, help_text="Signal strength")
    max_temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temperature_unit = models.CharField(max_length=20, default='celsius')
    raw_data = models.JSONField(null=True, blank=True, help_text="Raw JSON data from sensor")
    timestamp = models.DateTimeField(default=timezone.now, help_text="When the sensor reading was taken")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the record was created")
    
    class Meta:
        db_table = 'sensor_data'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device_name', '-timestamp']),
            models.Index(fields=['-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.device_name} - {self.temperature}°C at {self.timestamp}"
    
    @property
    def formatted_timestamp(self):
        """Return a formatted timestamp for display"""
        return self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    
    @property
    def temperature_fahrenheit(self):
        """Convert temperature to Fahrenheit"""
        if self.temperature is not None:
            return (float(self.temperature) * 9/5) + 32
        return None
    
    def get_raw_data_pretty(self):
        """Return pretty-printed raw data"""
        if self.raw_data:
            return json.dumps(self.raw_data, indent=2)
        return ""


class IrrigationPlan(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('executing', 'Executing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    DEVICE_CHOICES = [
        ('0x540f57fffe890af8', '🏠 Main Irrigation Controller (0x540f57fffe890af8)'),
        # Add more devices here when you expand your system
    ]
    
    id = models.CharField(max_length=100, primary_key=True)
    scheduled_time = models.DateTimeField()
    duration = models.IntegerField(help_text="Duration in seconds")
    description = models.TextField(blank=True, null=True, help_text="Optional description")
    device = models.CharField(max_length=50, choices=DEVICE_CHOICES, default='0x540f57fffe890af8')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    executed_at = models.DateTimeField(null=True, blank=True)
    result = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'irrigation_plans'
        ordering = ['-scheduled_time']
    
    def __str__(self):
        return f"Irrigation Plan {self.id} - {self.scheduled_time}"
    
    @property
    def duration_minutes(self):
        """Return duration in minutes for display"""
        return self.duration / 60
    
    @property
    def is_overdue(self):
        """Check if the plan is overdue"""
        return timezone.now() > self.scheduled_time and self.status == 'pending'
    
    @property
    def time_until_execution(self):
        """Calculate time until execution"""
        if self.scheduled_time > timezone.now():
            delta = self.scheduled_time - timezone.now()
            return delta
        return None