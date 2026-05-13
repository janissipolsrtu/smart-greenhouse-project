SELECT
  tc.table_name AS source_table,
  kcu.column_name AS source_column,
  ccu.table_name AS target_table,
  ccu.column_name AS target_column
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
 AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name = tc.constraint_name
 AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
  AND tc.table_name NOT LIKE 'auth_%'
  AND tc.table_name NOT LIKE 'django_%'
  AND ccu.table_name NOT LIKE 'auth_%'
  AND ccu.table_name NOT LIKE 'django_%'
ORDER BY source_table, source_column;

SELECT table_name
FROM information_schema.tables
WHERE table_schema='public'
  AND table_type='BASE TABLE'
  AND table_name NOT LIKE 'auth_%'
  AND table_name NOT LIKE 'django_%'
ORDER BY table_name;
