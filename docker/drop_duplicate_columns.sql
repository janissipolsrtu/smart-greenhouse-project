-- Remove duplicate location from greenhouse_config (kept in greenhouses only)
ALTER TABLE greenhouse_config DROP COLUMN IF EXISTS location;

-- Remove is_active from greenhouse_config (multi-greenhouse selection via updated_at ordering)
ALTER TABLE greenhouse_config DROP COLUMN IF EXISTS is_active;

-- Remove active from greenhouses (soft-delete replaced with real delete)
ALTER TABLE greenhouses DROP COLUMN IF EXISTS active;
