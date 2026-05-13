from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0007_greenhouseconfig_is_active'),
    ]

    operations = [
        migrations.AddField(
            model_name='greenhouseconfig',
            name='season',
            field=models.CharField(blank=True, help_text='Sezona (piem., Pavasaris 2026)', max_length=100),
        ),
    ]
