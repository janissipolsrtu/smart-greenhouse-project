from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0003_rename_irrigationplan_wateringcycle'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE TABLE IF NOT EXISTS watering_plans ("
                        "id VARCHAR(100) PRIMARY KEY, "
                        "name VARCHAR(120) NOT NULL, "
                        "description TEXT NULL, "
                        "start_date DATE NULL, "
                        "end_date DATE NULL, "
                        "active BOOLEAN NOT NULL DEFAULT TRUE, "
                        "created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(), "
                        "updated_at TIMESTAMP WITHOUT TIME ZONE NULL"
                        ");"
                    ),
                    reverse_sql="DROP TABLE IF EXISTS watering_plans;",
                ),
                migrations.RunSQL(
                    sql="ALTER TABLE irrigation_plans ADD COLUMN IF NOT EXISTS plan_id VARCHAR(100);",
                    reverse_sql="ALTER TABLE irrigation_plans DROP COLUMN IF EXISTS plan_id;",
                ),
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'irrigation_plans_plan_id_fk') THEN "
                        "ALTER TABLE irrigation_plans "
                        "ADD CONSTRAINT irrigation_plans_plan_id_fk "
                        "FOREIGN KEY (plan_id) REFERENCES watering_plans(id) ON DELETE SET NULL; "
                        "END IF; "
                        "END $$;"
                    ),
                    reverse_sql=(
                        "DO $$ BEGIN "
                        "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'irrigation_plans_plan_id_fk') THEN "
                        "ALTER TABLE irrigation_plans DROP CONSTRAINT irrigation_plans_plan_id_fk; "
                        "END IF; "
                        "END $$;"
                    ),
                ),
                migrations.RunSQL(
                    sql="CREATE INDEX IF NOT EXISTS ix_irrigation_plans_plan_id ON irrigation_plans(plan_id);",
                    reverse_sql="DROP INDEX IF EXISTS ix_irrigation_plans_plan_id;",
                ),
            ],
            state_operations=[
                migrations.CreateModel(
                    name='WateringPlan',
                    fields=[
                        ('id', models.CharField(max_length=100, primary_key=True, serialize=False)),
                        ('name', models.CharField(max_length=120)),
                        ('description', models.TextField(blank=True, null=True)),
                        ('start_date', models.DateField(blank=True, null=True)),
                        ('end_date', models.DateField(blank=True, null=True)),
                        ('active', models.BooleanField(default=True)),
                        ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                    ],
                    options={
                        'db_table': 'watering_plans',
                        'ordering': ['-created_at'],
                    },
                ),
                migrations.AddField(
                    model_name='wateringcycle',
                    name='plan',
                    field=models.ForeignKey(blank=True, help_text='Optional watering plan container', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cycles', to='irrigation.wateringplan'),
                ),
            ],
        ),
    ]
