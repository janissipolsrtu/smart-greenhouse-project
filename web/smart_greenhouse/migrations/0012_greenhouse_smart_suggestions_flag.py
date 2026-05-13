from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0011_greenhouse_feature_flags'),
    ]

    operations = [
        migrations.AddField(
            model_name='greenhouseconfig',
            name='feature_smart_suggestions',
            field=models.BooleanField(default=False, help_text='Iespējot gudros ieteikumus'),
        ),
    ]
