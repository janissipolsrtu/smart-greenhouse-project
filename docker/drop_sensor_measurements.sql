-- Drop the sensor_measurements table after consolidation to sensor_data
-- Verify row count before drop

BEGIN;

SELECT COUNT(*) as sensor_data_rows FROM sensor_data;
SELECT COUNT(*) as sensor_measurements_rows FROM sensor_measurements;

-- Drop the table and its dependencies
DROP TABLE IF EXISTS sensor_measurements CASCADE;

-- Verify drop completed
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('sensor_data', 'sensor_measurements')
ORDER BY table_name;

COMMIT;
