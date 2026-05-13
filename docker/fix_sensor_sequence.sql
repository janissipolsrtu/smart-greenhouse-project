-- Fix sensor_data_id_seq to start from max(id) + 1
BEGIN;

-- Get current max ID and set sequence accordingly
SELECT setval('sensor_data_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM sensor_data));

-- Verify the sequence is now correct
SELECT 
    'Next ID from sequence' as check_point,
    nextval('sensor_data_id_seq') as next_id,
    (SELECT MAX(id) FROM sensor_data) as current_max_id;

COMMIT;
