from django.apps import AppConfig


_schema_checked = False


class IrrigationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'smart_greenhouse'
    label = 'irrigation'

    def ready(self):
        global _schema_checked
        if _schema_checked:
            return

        # Keep startup resilient when DB schema is one migration behind.
        try:
            from django.db import connection

            with connection.cursor() as cursor:
                cursor.execute("SELECT to_regclass('public.watering_cycle')")
                has_watering_cycle = cursor.fetchone()[0] is not None

                cursor.execute("SELECT to_regclass('public.irrigation_plans')")
                has_irrigation_plans = cursor.fetchone()[0] is not None

                if not has_watering_cycle and has_irrigation_plans:
                    cursor.execute("ALTER TABLE irrigation_plans RENAME TO watering_cycle")
                    cursor.execute(
                        "DO $$ BEGIN "
                        "IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'irrigation_plans_plan_id_fk') THEN "
                        "ALTER TABLE watering_cycle RENAME CONSTRAINT irrigation_plans_plan_id_fk TO watering_cycle_plan_id_fk; "
                        "END IF; "
                        "END $$;"
                    )
                    cursor.execute(
                        "DO $$ BEGIN "
                        "IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'ix_irrigation_plans_plan_id') THEN "
                        "ALTER INDEX ix_irrigation_plans_plan_id RENAME TO ix_watering_cycle_plan_id; "
                        "END IF; "
                        "END $$;"
                    )
        except Exception:
            # Ignore startup-time DB issues; normal migrations still handle schema state.
            pass

        _schema_checked = True