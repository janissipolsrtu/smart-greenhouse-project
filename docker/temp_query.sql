SELECT COUNT(*) as device_count FROM devices;
SELECT COUNT(*) as greenhouse_count FROM greenhouse_config;
SELECT COUNT(*) as sensor_count FROM sensor_data;
SELECT DISTINCT device_name FROM sensor_data LIMIT 3;
