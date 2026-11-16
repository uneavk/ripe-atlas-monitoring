-- Демонстрація в DBeaver: PostgreSQL, порт 5432, прикладна БД ripe_monitoring.
-- Назву БД і користувача звірте зі своїм .env. Усі запити лише читають дані.
-- Службова БД Metabase є окремою і до цієї демонстрації не належить.

-- 1. Операційні таблиці та читабельні звітні в'ю.
SELECT table_schema, table_name, table_type
FROM information_schema.tables
WHERE table_schema IN ('public', 'reporting')
ORDER BY table_schema, table_type, table_name;

-- 2. Один рядок = один епізод проблеми. Без персональних адресатів Telegram.
SELECT started_at, incident_type, severity, incident_status,
       probe_id, provider_asn, measurement_id, ip_version,
       resolved_at, notification_status
FROM reporting.incidents
ORDER BY started_at DESC LIMIT 20;

-- 3. Нові епізоди за днями. Тривалий збій не рахується щодня заново.
SELECT day, incident_type, sum(incident_count) AS new_episodes
FROM reporting.incidents_daily
GROUP BY day, incident_type ORDER BY day DESC, incident_type;

-- 4. Валідаційні відхилення конвеєра та їх причини.
SELECT stage, reason, sum(rejected_events) AS rejected_events
FROM reporting.processing_errors_hourly
GROUP BY stage, reason ORDER BY rejected_events DESC;

-- 5. Фактичні стани доставки: одна доставка = один адресат.
-- Запит не надсилає нових повідомлень і не показує chat_id.
SELECT day, delivery_status, delivery_count
FROM reporting.telegram_deliveries_daily
ORDER BY day DESC, delivery_status;
