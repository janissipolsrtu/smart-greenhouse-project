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


class WateringPlan(models.Model):
    """Container for planned watering cycles (none or many cycles)."""

    id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    greenhouse_config = models.ForeignKey('GreenhouseConfig', on_delete=models.SET_NULL, null=True, blank=True, related_name='watering_plans')
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'watering_plans'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.id})"

    @property
    def cycle_count(self):
        return self.cycles.count()


class WateringCycle(models.Model):
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
    plan = models.ForeignKey(
        WateringPlan,
        on_delete=models.SET_NULL,
        related_name='cycles',
        null=True,
        blank=True,
        help_text="Optional watering plan container"
    )
    device = models.CharField(max_length=50, choices=DEVICE_CHOICES, default='0x540f57fffe890af8')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    executed_at = models.DateTimeField(null=True, blank=True)
    result = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'watering_cycle'
        ordering = ['-scheduled_time']
    
    def __str__(self):
        return f"Watering Cycle {self.id} - {self.scheduled_time}"
    
    @property
    def duration_minutes(self):
        """Return duration in minutes for display"""
        return self.duration / 60
    
    @property
    def is_overdue(self):
        """Check if the cycle is overdue"""
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


class GreenhouseConfig(models.Model):
    """Configuration for a greenhouse and its controller. Multiple greenhouses supported."""

    name = models.CharField(max_length=120, help_text="Siltumnīcas nosaukums")
    location = models.CharField(max_length=200, blank=True, help_text="Siltumnīcas atrašanās vieta")
    season = models.CharField(max_length=100, blank=True, help_text="Sezona (piem., Pavasaris 2026)")
    is_active = models.BooleanField(default=False, help_text="Aktīvā siltumnīca")
    controller_ip = models.GenericIPAddressField(null=True, blank=True, help_text="Kontrollera IP adrese")
    controller_username = models.CharField(max_length=100, blank=True, help_text="Kontrollera lietotājvārds")
    controller_password = models.CharField(max_length=255, blank=True, help_text="Kontrollera parole (glabāta šifrēta)")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'greenhouse_config'
        verbose_name = "Greenhouse Configuration"

    def __str__(self):
        return f"{self.name} @ {self.location or 'nav norādīts'}"

    @classmethod
    def get_config(cls):
        """Return the active greenhouse, falling back to the first one."""
        return cls.objects.filter(is_active=True).first() or cls.objects.first()

    def set_active(self):
        """Mark this greenhouse as active and deactivate all others."""
        GreenhouseConfig.objects.exclude(pk=self.pk).update(is_active=False)
        self.is_active = True
        self.save(update_fields=['is_active'])

    def set_password(self, raw_password):
        """Store a bcrypt hash of the controller password."""
        import hashlib, os
        salt = os.urandom(16).hex()
        hashed = hashlib.sha256(f"{salt}{raw_password}".encode()).hexdigest()
        self.controller_password = f"{salt}:{hashed}"

    def check_password(self, raw_password):
        """Verify a plain-text password against the stored hash."""
        import hashlib
        if ':' not in self.controller_password:
            return False
        salt, hashed = self.controller_password.split(':', 1)
        return hashlib.sha256(f"{salt}{raw_password}".encode()).hexdigest() == hashed


class Device(models.Model):
    """A physical Zigbee/MQTT device paired to a specific greenhouse."""

    DEVICE_TYPE_CHOICES = [
        ('irrigation_controller', 'Irrigation Controller'),
        ('temperature_sensor', 'Temperature Sensor'),
        ('humidity_sensor', 'Humidity Sensor'),
        ('other', 'Other'),
    ]

    zigbee_id = models.CharField(
        max_length=100,
        help_text="Zigbee IEEE address, e.g. 0x540f57fffe890af8",
    )
    name = models.CharField(max_length=120, help_text="Human-readable device name")
    device_type = models.CharField(
        max_length=40,
        choices=DEVICE_TYPE_CHOICES,
        default='other',
        help_text="Type of device",
    )
    greenhouse = models.ForeignKey(
        GreenhouseConfig,
        on_delete=models.CASCADE,
        related_name='devices',
        help_text="Greenhouse this device belongs to",
    )
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'devices'
        ordering = ['device_type', 'name']
        unique_together = [('greenhouse', 'zigbee_id')]

    def __str__(self):
        return f"{self.name} ({self.zigbee_id}) @ {self.greenhouse.name}"

    @property
    def mqtt_topic(self):
        return f"zigbee2mqtt/{self.zigbee_id}"


class PathCell(models.Model):
    """Model for storing greenhouse path cells (walkways between beds)"""
    
    row = models.PositiveIntegerField(help_text="Rindas numurs siltumnīcā")
    column = models.PositiveIntegerField(help_text="Kolonnas numurs siltumnīcā") 
    description = models.CharField(max_length=200, blank=True, null=True, help_text="Ceļa apraksts")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'path_cells'
        unique_together = ['row', 'column']  # Only one path per location
        ordering = ['row', 'column']
        indexes = [
            models.Index(fields=['row', 'column']),
        ]
    
    def __str__(self):
        return f"Ceļš R{self.row}C{self.column}"
    
    @property
    def location_coordinate(self):
        """Get location as coordinate string (e.g., 'R1C3')"""
        return f"R{self.row}C{self.column}"