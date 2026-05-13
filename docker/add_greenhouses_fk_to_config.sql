-- Add FK column on greenhouses that points to greenhouse_config(id)
ALTER TABLE greenhouses
ADD COLUMN IF NOT EXISTS greenhouse_config_id integer;

-- Backfill link using current logical key (name)
UPDATE greenhouses g
SET greenhouse_config_id = gc.id
FROM greenhouse_config gc
WHERE g.name = gc.name
  AND (g.greenhouse_config_id IS NULL OR g.greenhouse_config_id <> gc.id);

-- Ensure one-to-one mapping from greenhouse to config where linked
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'greenhouses_greenhouse_config_id_key'
    ) THEN
        ALTER TABLE greenhouses
        ADD CONSTRAINT greenhouses_greenhouse_config_id_key UNIQUE (greenhouse_config_id);
    END IF;
END $$;

-- Add FK constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'greenhouses_greenhouse_config_id_fkey'
    ) THEN
        ALTER TABLE greenhouses
        ADD CONSTRAINT greenhouses_greenhouse_config_id_fkey
        FOREIGN KEY (greenhouse_config_id)
        REFERENCES greenhouse_config(id)
        ON DELETE SET NULL;
    END IF;
END $$;
