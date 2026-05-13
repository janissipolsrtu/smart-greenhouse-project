-- 1) Add device_id FK column on sensor_data
ALTER TABLE sensor_data
ADD COLUMN IF NOT EXISTS device_id integer;

-- 2) Backfill by matching sensor_data.device_name = devices.zigbee_id
UPDATE sensor_data sd
SET device_id = d.id
FROM devices d
WHERE sd.device_name = d.zigbee_id
  AND sd.device_id IS NULL;

-- 3) Add FK constraint (nullable - future readings from unknown devices are allowed)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'sensor_data_device_id_fkey'
    ) THEN
        ALTER TABLE sensor_data
        ADD CONSTRAINT sensor_data_device_id_fkey
        FOREIGN KEY (device_id)
        REFERENCES devices(id)
        ON DELETE SET NULL;
    END IF;
END $$;

-- 4) Add index for efficient joins
CREATE INDEX IF NOT EXISTS sensor_data_device_id_idx ON sensor_data (device_id);
