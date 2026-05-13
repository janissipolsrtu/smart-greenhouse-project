-- 1) Add reverse link on greenhouse_config (many configs -> one greenhouse)
ALTER TABLE greenhouse_config
ADD COLUMN IF NOT EXISTS greenhouse_id character varying;

-- 2) Backfill from current forward link
UPDATE greenhouse_config gc
SET greenhouse_id = g.id
FROM greenhouses g
WHERE g.greenhouse_config_id = gc.id
  AND (gc.greenhouse_id IS NULL OR gc.greenhouse_id <> g.id);

-- 3) Fallback backfill by name for any remaining rows
UPDATE greenhouse_config gc
SET greenhouse_id = g.id
FROM greenhouses g
WHERE gc.greenhouse_id IS NULL
  AND gc.name = g.name;

-- 4) Add index on greenhouse_id
CREATE INDEX IF NOT EXISTS greenhouse_config_greenhouse_id_idx
ON greenhouse_config (greenhouse_id);

-- 5) Add FK greenhouse_config.greenhouse_id -> greenhouses.id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'greenhouse_config_greenhouse_id_fkey'
    ) THEN
        ALTER TABLE greenhouse_config
        ADD CONSTRAINT greenhouse_config_greenhouse_id_fkey
        FOREIGN KEY (greenhouse_id)
        REFERENCES greenhouses(id)
        ON DELETE SET NULL;
    END IF;
END $$;

-- 6) Drop old forward constraints/column from greenhouses
ALTER TABLE greenhouses
DROP CONSTRAINT IF EXISTS greenhouses_greenhouse_config_id_fkey;

ALTER TABLE greenhouses
DROP CONSTRAINT IF EXISTS greenhouses_greenhouse_config_id_key;

ALTER TABLE greenhouses
DROP COLUMN IF EXISTS greenhouse_config_id;
