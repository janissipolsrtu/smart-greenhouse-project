-- Migration: Consolidate sensor_measurements into sensor_data
-- This script copies all 265 rows from sensor_measurements to sensor_data
-- and prepares to drop sensor_measurements table

-- Start transaction
BEGIN;

-- Clear any existing data from sensor_data to avoid duplicates
TRUNCATE TABLE sensor_data;

-- Copy all data from sensor_measurements to sensor_data
INSERT INTO sensor_data (
    id,
    device_name,
    topic,
    temperature,
    humidity,
    linkquality,
    battery,
    max_temperature,
    min_temperature,
    temperature_sensitivity,
    temperature_calibration,
    temperature_sampling,
    temperature_unit,
    humidity_calibration,
    soil_moisture,
    soil_calibration,
    soil_sampling,
    soil_warning,
    dry,
    raw_data,
    timestamp,
    created_at
)
SELECT
    id,
    device_name,
    topic,
    temperature,
    humidity,
    linkquality,
    battery,
    max_temperature,
    min_temperature,
    temperature_sensitivity,
    temperature_calibration,
    temperature_sampling,
    temperature_unit,
    humidity_calibration,
    soil_moisture,
    soil_calibration,
    soil_sampling,
    soil_warning,
    dry,
    raw_data,
    timestamp,
    created_at
FROM sensor_measurements
ORDER BY timestamp ASC;

-- Verify the migration
SELECT 
    'sensor_data' as table_name,
    COUNT(*) as row_count,
    MIN(timestamp) as earliest_timestamp,
    MAX(timestamp) as latest_timestamp
FROM sensor_data
UNION ALL
SELECT 
    'sensor_measurements' as table_name,
    COUNT(*) as row_count,
    MIN(timestamp) as earliest_timestamp,
    MAX(timestamp) as latest_timestamp
FROM sensor_measurements;

-- Commit transaction
COMMIT;
