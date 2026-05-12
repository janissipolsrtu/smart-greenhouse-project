from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0010_device'),
    ]

    operations = [
        migrations.AddField(
            model_name='greenhouseconfig',
            name='feature_layout',
            field=models.BooleanField(default=True, help_text='Iespējot siltumnīcas izkārtojuma moduli'),
        ),
        migrations.AddField(
            model_name='greenhouseconfig',
            name='feature_meteostation',
            field=models.BooleanField(default=False, help_text='Iespējot meteostacijas datu moduli'),
        ),
        migrations.AddField(
            model_name='greenhouseconfig',
            name='feature_plants',
            field=models.BooleanField(default=True, help_text='Iespējot augu pārvaldības moduli'),
        ),
        migrations.AddField(
            model_name='greenhouseconfig',
            name='feature_watering_liters',
            field=models.BooleanField(default=False, help_text='Iespējot laistīšanu litros'),
        ),
    ]
