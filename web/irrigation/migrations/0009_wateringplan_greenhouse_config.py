from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0008_greenhouseconfig_season'),
    ]

    operations = [
        migrations.AddField(
            model_name='wateringplan',
            name='greenhouse_config',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='watering_plans', to='irrigation.greenhouseconfig'),
        ),
    ]
