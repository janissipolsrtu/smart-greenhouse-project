SELECT column_name
FROM information_schema.columns
WHERE table_schema='public'
  AND table_name='greenhouse_config'
  AND column_name IN ('controller_ip','controller_username','controller_password')
ORDER BY column_name;
