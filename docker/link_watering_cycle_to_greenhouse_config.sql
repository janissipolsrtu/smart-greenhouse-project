-- 1) Add greenhouse_config_id column
ALTER TABLE watering_cycle
ADD COLUMN IF NOT EXISTS greenhouse_config_id integer;

-- 2) Backfill from watering_plans using existing plan_id link
UPDATE watering_cycle wc
SET greenhouse_config_id = wp.greenhouse_config_id
FROM watering_plans wp
WHERE wc.plan_id = wp.id
  AND wc.greenhouse_config_id IS NULL;

-- 3) Add FK constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'watering_cycle_greenhouse_config_id_fkey'
    ) THEN
        ALTER TABLE watering_cycle
        ADD CONSTRAINT watering_cycle_greenhouse_config_id_fkey
        FOREIGN KEY (greenhouse_config_id)
        REFERENCES greenhouse_config(id)
        ON DELETE SET NULL;
    END IF;
END $$;

-- 4) Add index for filtering/grouping by greenhouse
CREATE INDEX IF NOT EXISTS ix_watering_cycle_greenhouse_config_id
ON watering_cycle (greenhouse_config_id);
