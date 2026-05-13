-- 1) Create device_types table
CREATE TABLE IF NOT EXISTS device_types (
    id          serial PRIMARY KEY,
    type_key    character varying(40)  NOT NULL UNIQUE,
    name        character varying(120) NOT NULL,
    created_at  timestamp with time zone NOT NULL DEFAULT now()
);

-- 2) Seed from existing distinct device_type / name pairs in devices table
INSERT INTO device_types (type_key, name)
SELECT DISTINCT ON (device_type) device_type, name
FROM devices
ORDER BY device_type, id
ON CONFLICT (type_key) DO NOTHING;

-- 3) Ensure 'other' type exists (may have no devices yet)
INSERT INTO device_types (type_key, name) VALUES ('other', 'Cits')
ON CONFLICT (type_key) DO NOTHING;

-- 4) Add device_type_id FK column on devices
ALTER TABLE devices
ADD COLUMN IF NOT EXISTS device_type_id integer;

-- 5) Backfill from existing device_type string
UPDATE devices d
SET device_type_id = dt.id
FROM device_types dt
WHERE d.device_type = dt.type_key
  AND d.device_type_id IS NULL;

-- 6) Set NOT NULL constraint now that all rows are backfilled
ALTER TABLE devices
ALTER COLUMN device_type_id SET NOT NULL;

-- 7) Add FK constraint
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'devices_device_type_id_fkey'
    ) THEN
        ALTER TABLE devices
        ADD CONSTRAINT devices_device_type_id_fkey
        FOREIGN KEY (device_type_id)
        REFERENCES device_types(id)
        ON DELETE RESTRICT;
    END IF;
END $$;

-- 8) Add index
CREATE INDEX IF NOT EXISTS devices_device_type_id_idx ON devices (device_type_id);
