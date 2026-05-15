from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0019_add_seasons_and_plant_greenhouse_links'),
    ]

    operations = [
        migrations.AddField(
            model_name='greenhouseconfig',
            name='timezone',
            field=models.CharField(default='UTC', help_text='Laika zona (piem., Europe/Riga)', max_length=64),
        ),
    ]
