-- 1) Create seasons table
CREATE TABLE IF NOT EXISTS seasons (
    id            serial PRIMARY KEY,
    greenhouse_id character varying NOT NULL,
    name          character varying(120) NOT NULL,
    start_date    date,
    end_date      date,
    is_active     boolean NOT NULL DEFAULT true,
    created_at    timestamp with time zone NOT NULL DEFAULT now(),
    updated_at    timestamp with time zone NOT NULL DEFAULT now(),
    CONSTRAINT seasons_greenhouse_name_key UNIQUE (greenhouse_id, name)
);

-- 2) Add FK from seasons to greenhouses
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'seasons_greenhouse_id_fkey'
    ) THEN
        ALTER TABLE seasons
        ADD CONSTRAINT seasons_greenhouse_id_fkey
        FOREIGN KEY (greenhouse_id)
        REFERENCES greenhouses(id)
        ON DELETE CASCADE;
    END IF;
END $$;

-- 3) Add greenhouse/season links on plants
ALTER TABLE plants ADD COLUMN IF NOT EXISTS greenhouse_id character varying;
ALTER TABLE plants ADD COLUMN IF NOT EXISTS season_id integer;

-- 4) Seed seasons from greenhouse_config.season where possible
INSERT INTO seasons (greenhouse_id, name, is_active)
SELECT DISTINCT gc.greenhouse_id, gc.season, true
FROM greenhouse_config gc
WHERE COALESCE(gc.greenhouse_id, '') <> ''
  AND COALESCE(NULLIF(gc.season, ''), '') <> ''
ON CONFLICT (greenhouse_id, name) DO NOTHING;

-- 5) Ensure each greenhouse has at least one season row
INSERT INTO seasons (greenhouse_id, name, is_active)
SELECT g.id, 'Default Season', true
FROM greenhouses g
WHERE NOT EXISTS (
    SELECT 1 FROM seasons s WHERE s.greenhouse_id = g.id
)
ON CONFLICT (greenhouse_id, name) DO NOTHING;

-- 6) Backfill plants.greenhouse_id
UPDATE plants p
SET greenhouse_id = picked.greenhouse_id
FROM (
    SELECT gc.greenhouse_id
    FROM greenhouse_config gc
    WHERE COALESCE(gc.greenhouse_id, '') <> ''
    ORDER BY gc.selected DESC, gc.id ASC
    LIMIT 1
) AS picked
WHERE p.greenhouse_id IS NULL;

UPDATE plants p
SET greenhouse_id = g.id
FROM (
    SELECT id FROM greenhouses ORDER BY created_at ASC LIMIT 1
) AS g
WHERE p.greenhouse_id IS NULL;

-- 7) Backfill plants.season_id to active/default season for its greenhouse
UPDATE plants p
SET season_id = chosen.id
FROM (
    SELECT DISTINCT ON (s.greenhouse_id)
        s.greenhouse_id,
        s.id
    FROM seasons s
    ORDER BY s.greenhouse_id, s.is_active DESC, s.id ASC
) AS chosen
WHERE p.greenhouse_id = chosen.greenhouse_id
  AND p.season_id IS NULL;

-- 8) Add FK constraints
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'plants_greenhouse_id_fkey'
    ) THEN
        ALTER TABLE plants
        ADD CONSTRAINT plants_greenhouse_id_fkey
        FOREIGN KEY (greenhouse_id)
        REFERENCES greenhouses(id)
        ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'plants_season_id_fkey'
    ) THEN
        ALTER TABLE plants
        ADD CONSTRAINT plants_season_id_fkey
        FOREIGN KEY (season_id)
        REFERENCES seasons(id)
        ON DELETE SET NULL;
    END IF;
END $$;

-- 9) Add supporting indexes
CREATE INDEX IF NOT EXISTS ix_plants_greenhouse_id ON plants (greenhouse_id);
CREATE INDEX IF NOT EXISTS ix_plants_season_id ON plants (season_id);
CREATE INDEX IF NOT EXISTS ix_seasons_greenhouse_id ON seasons (greenhouse_id);
