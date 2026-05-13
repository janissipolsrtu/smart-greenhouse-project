BEGIN;

-- 1) Update existing greenhouse_config rows by matching name first, then location fallback.
UPDATE greenhouse_config gc
SET
  controller_ip = COALESCE(NULLIF(gc.controller_ip::text, '')::inet, NULLIF(g.mqtt_broker, '')::inet),
  controller_username = CASE
    WHEN COALESCE(gc.controller_username, '') = '' THEN COALESCE(g.mqtt_username, gc.controller_username)
    ELSE gc.controller_username
  END,
  controller_password = CASE
    WHEN COALESCE(gc.controller_password, '') = '' THEN COALESCE(g.mqtt_password, gc.controller_password)
    ELSE gc.controller_password
  END,
  updated_at = NOW()
FROM greenhouses g
WHERE gc.name = g.name
   OR (gc.location = g.location AND gc.location IS NOT NULL AND g.location IS NOT NULL);

-- 2) Insert missing greenhouse_config rows for greenhouses that don't exist there yet.
INSERT INTO greenhouse_config (
  name, location, season, is_active,
  controller_ip, controller_username, controller_password,
  feature_plants, feature_layout, feature_meteostation,
  feature_watering_liters, feature_smart_suggestions,
  created_at, updated_at
)
SELECT
  g.name,
  COALESCE(g.location, ''),
  '',
  COALESCE(g.active, FALSE),
  NULLIF(g.mqtt_broker, '')::inet,
  COALESCE(g.mqtt_username, ''),
  COALESCE(g.mqtt_password, ''),
  TRUE,
  TRUE,
  FALSE,
  FALSE,
  FALSE,
  NOW(),
  NOW()
FROM greenhouses g
WHERE NOT EXISTS (
  SELECT 1 FROM greenhouse_config gc WHERE gc.name = g.name
);

COMMIT;

-- Verification
SELECT COUNT(*) AS greenhouses_count FROM greenhouses;
SELECT COUNT(*) AS greenhouse_config_count FROM greenhouse_config;
SELECT name, controller_ip, controller_username, (controller_password <> '') AS has_password FROM greenhouse_config ORDER BY id;
