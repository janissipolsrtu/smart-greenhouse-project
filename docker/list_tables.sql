SELECT table_name FROM information_schema.tables WHERE table_schema=public AND (table_name LIKE %%device%% OR table_name LIKE %%greenhouse%%) ORDER BY table_name;
