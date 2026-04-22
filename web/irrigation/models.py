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


class Plant(models.Model):
    """Model for plant registration and management in greenhouse"""
    
    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=100, help_text="Auga nosaukums vai šķirne")  # FR-11
    variety = models.CharField(max_length=100, blank=True, null=True, help_text="Specifiskā šķirne")
    planting_date = models.DateField(help_text="Stādīšanas datums")  # FR-12
    watering_frequency = models.PositiveIntegerField(default=1, help_text="Laistīšanas biežums (reizes dienā)")  # FR-13
    watering_duration = models.PositiveIntegerField(default=300, help_text="Laistīšanas ilgums sekundēs")  # FR-13
    water_amount_ml = models.PositiveIntegerField(blank=True, null=True, help_text="Ūdens daudzums ml")  # FR-13
    harvest_date_estimate = models.DateField(blank=True, null=True, help_text="Ražas prognozes datums")  # FR-14
    harvest_quantity_estimate = models.FloatField(blank=True, null=True, help_text="Prognozētais ražas daudzums (kg)")  # FR-14
    location_row = models.PositiveIntegerField(help_text="Rindas numurs siltumnīcā")  # FR-15
    location_column = models.PositiveIntegerField(help_text="Kolonnas numurs siltumnīcā")  # FR-15
    location_description = models.CharField(max_length=200, blank=True, null=True, help_text="Papildu atrašanās vietas apraksts")  # FR-15
    notes = models.TextField(blank=True, null=True, help_text="Papildu piezīmes par augu")
    active = models.BooleanField(default=True, help_text="Vai augs vēl ir aktīvs")
    created_at = models.DateTimeField(default=timezone.now, help_text="Reģistrācijas datums")
    updated_at = models.DateTimeField(auto_now=True, help_text="Pēdējās izmaiņas")
    
    class Meta:
        db_table = 'plants'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name', 'active']),
            models.Index(fields=['location_row', 'location_column']),
            models.Index(fields=['-planting_date']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.location_coordinate} ({self.planting_date})"
    
    @property
    def location_coordinate(self):
        """Get location as coordinate string (e.g., 'R1C3')"""
        return f"R{self.location_row}C{self.location_column}"
    
    @property
    def days_since_planting(self):
        """Calculate days since planting"""
        if self.planting_date:
            return (timezone.now().date() - self.planting_date).days
        return 0
    
    @property
    def days_to_harvest(self):
        """Calculate days until harvest"""
        if self.harvest_date_estimate:
            return (self.harvest_date_estimate - timezone.now().date()).days
        return None
    
    @property
    def is_ready_for_harvest(self):
        """Check if plant is ready for harvest"""
        if self.harvest_date_estimate:
            return timezone.now().date() >= self.harvest_date_estimate
        return False
    
    @property
    def watering_schedule_daily_ml(self):
        """Calculate total daily water amount"""
        if self.water_amount_ml:
            return self.water_amount_ml * self.watering_frequency
        return None
    
    def save(self, *args, **kwargs):
        """Override save to generate ID if not provided"""
        if not self.id:
            import time
            import uuid
            timestamp = int(time.time())
            unique_id = uuid.uuid4().hex[:8]
            self.id = f"plant_{timestamp}_{unique_id}"
        super().save(*args, **kwargs)