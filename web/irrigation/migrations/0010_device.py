from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0009_wateringplan_greenhouse_config'),
    ]

    operations = [
        migrations.CreateModel(
            name='Device',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('zigbee_id', models.CharField(help_text='Zigbee IEEE address, e.g. 0x540f57fffe890af8', max_length=100)),
                ('name', models.CharField(help_text='Human-readable device name', max_length=120)),
                ('device_type', models.CharField(
                    choices=[
                        ('irrigation_controller', 'Irrigation Controller'),
                        ('temperature_sensor', 'Temperature Sensor'),
                        ('humidity_sensor', 'Humidity Sensor'),
                        ('other', 'Other'),
                    ],
                    default='other',
                    help_text='Type of device',
                    max_length=40,
                )),
                ('greenhouse', models.ForeignKey(
                    help_text='Greenhouse this device belongs to',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='devices',
                    to='irrigation.greenhouseconfig',
                )),
                ('active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'devices',
                'ordering': ['device_type', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='device',
            constraint=models.UniqueConstraint(fields=['greenhouse', 'zigbee_id'], name='unique_device_per_greenhouse'),
        ),
    ]
