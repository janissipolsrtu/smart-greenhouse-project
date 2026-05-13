ALTER TABLE greenhouse_config ADD COLUMN IF NOT EXISTS selected boolean NOT NULL DEFAULT false;
-- Mark the first row as selected so the UI has a default
UPDATE greenhouse_config SET selected = true WHERE id = (SELECT id FROM greenhouse_config ORDER BY id LIMIT 1);
