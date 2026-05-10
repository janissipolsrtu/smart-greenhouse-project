from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('irrigation', '0004_wateringplan_and_cycle_plan_fk'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE irrigation_plans RENAME TO watering_cycle;",
                    reverse_sql="ALTER TABLE watering_cycle RENAME TO irrigation_plans;",
                ),
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'irrigation_plans_plan_id_fk') THEN "
                        "ALTER TABLE watering_cycle RENAME CONSTRAINT irrigation_plans_plan_id_fk TO watering_cycle_plan_id_fk; "
                        "END IF; "
                        "END $$;"
                    ),
                    reverse_sql=(
                        "DO $$ BEGIN "
                        "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'watering_cycle_plan_id_fk') THEN "
                        "ALTER TABLE watering_cycle RENAME CONSTRAINT watering_cycle_plan_id_fk TO irrigation_plans_plan_id_fk; "
                        "END IF; "
                        "END $$;"
                    ),
                ),
                migrations.RunSQL(
                    sql=(
                        "DO $$ BEGIN "
                        "IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'ix_irrigation_plans_plan_id') THEN "
                        "ALTER INDEX ix_irrigation_plans_plan_id RENAME TO ix_watering_cycle_plan_id; "
                        "END IF; "
                        "END $$;"
                    ),
                    reverse_sql=(
                        "DO $$ BEGIN "
                        "IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'ix_watering_cycle_plan_id') THEN "
                        "ALTER INDEX ix_watering_cycle_plan_id RENAME TO ix_irrigation_plans_plan_id; "
                        "END IF; "
                        "END $$;"
                    ),
                ),
            ],
            state_operations=[
                migrations.AlterModelTable(
                    name='wateringcycle',
                    table='watering_cycle',
                ),
            ],
        ),
    ]