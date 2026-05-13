INSERT INTO greenhouses (id, name, location, mqtt_broker, mqtt_port, mqtt_username, mqtt_password, active, created_at, updated_at)
VALUES 
('1', 'Salacgrīvas siltumnīca', 'Salacgrīva', '192.168.8.151', 1883, 'mosquitto_api_user1', 'securepassword', true, NOW(), NOW()),
('2', 'Znotiņu siltumnīca', 'Znotiņi', '', 1883, '', '', true, NOW(), NOW())
ON CONFLICT (id) DO NOTHING;
