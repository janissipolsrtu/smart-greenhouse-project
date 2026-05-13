SELECT 'greenhouses' AS table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema='public' AND table_name='greenhouses'
UNION ALL
SELECT 'greenhouse_config' AS table_name, column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema='public' AND table_name='greenhouse_config';
