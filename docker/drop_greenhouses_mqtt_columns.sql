-- Consolidation step: keep MQTT credentials in greenhouse_config only.
BEGIN;

ALTER TABLE greenhouses DROP COLUMN IF EXISTS mqtt_broker;
ALTER TABLE greenhouses DROP COLUMN IF EXISTS mqtt_port;
ALTER TABLE greenhouses DROP COLUMN IF EXISTS mqtt_username;
ALTER TABLE greenhouses DROP COLUMN IF EXISTS mqtt_password;

COMMIT;
