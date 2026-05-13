from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0002_pathcell'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='IrrigationPlan',
            new_name='WateringCycle',
        ),
    ]
