from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0006_greenhouseconfig'),
    ]

    operations = [
        migrations.AddField(
            model_name='greenhouseconfig',
            name='is_active',
            field=models.BooleanField(default=False, help_text='Aktīvā siltumnīca'),
        ),
    ]
