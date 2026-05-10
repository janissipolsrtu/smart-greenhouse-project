from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0005_rename_irrigation_plans_to_watering_cycle'),
    ]

    operations = [
        migrations.CreateModel(
            name='GreenhouseConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Siltumnīcas nosaukums', max_length=120)),
                ('location', models.CharField(blank=True, help_text='Siltumnīcas atrašanās vieta', max_length=200)),
                ('controller_ip', models.GenericIPAddressField(blank=True, help_text='Kontrollera IP adrese', null=True)),
                ('controller_username', models.CharField(blank=True, help_text='Kontrollera lietotājvārds', max_length=100)),
                ('controller_password', models.CharField(blank=True, help_text='Kontrollera parole (glabāta šifrēta)', max_length=255)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Greenhouse Configuration',
                'db_table': 'greenhouse_config',
            },
        ),
    ]
