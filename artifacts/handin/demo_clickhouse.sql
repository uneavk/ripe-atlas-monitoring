-- Демонстрація в DBeaver: підключення ClickHouse, порт HTTP 8123.
-- Виконуйте по одному запиту (Ctrl+Enter). Усі запити лише читають дані.
-- Початкову схему створює clickhouse/init.sql через Docker Compose.
-- Цей файл показує результат роботи, а не повторно встановлює схему.

-- 1. Фізичні таблиці, звичайні в'ю та два маркери вставок.
SELECT database AS schema_name, name AS object_name, engine AS object_type
FROM system.tables
WHERE database IN ('monitoring', 'analytics')
ORDER BY schema_name, object_type, object_name;

-- 2. Чотири джерела. Ціль і протокол завжди залишаються окремими вимірами.
SELECT measurement_id, target_name, ip_version, interval_seconds
FROM analytics.measurement_directory ORDER BY measurement_id;

-- 3. ASN одного зонда може відрізнятися між IPv4 та IPv6.
SELECT probe_id, country_code, ipv4_provider_asn, ipv6_provider_asn,
       latitude, longitude
FROM analytics.probe_directory ORDER BY probe_id LIMIT 15;

-- 4. Спершу перевіряємо свіжість, потім інтерпретуємо графіки.
SELECT measurement_id, target_name, ip_version, latest_measurement_at,
       data_age_seconds, measurements_last_5h, probes_observed_last_5h, data_status
FROM analytics.data_freshness ORDER BY measurement_id;

-- 5. Один рядок = завершена година / джерело / IP-версія.
SELECT period_start, measurement_id, target_name, ip_version,
       measurement_count, probes_observed,
       round(avg_rtt_ms, 2) AS avg_rtt_ms,
       round(packet_loss_pct, 2) AS packet_loss_pct
FROM analytics.network_hourly
ORDER BY period_start DESC, measurement_id LIMIT 16;

-- 6. Поденні дані фіналізуються після 04:00 Europe/Kyiv, зберігаються безстроково.
SELECT period_start, measurement_id, target_name, ip_version,
       measurement_count, probes_observed,
       round(avg_rtt_ms, 2) AS avg_rtt_ms,
       round(packet_loss_pct, 2) AS packet_loss_pct
FROM analytics.network_daily
ORDER BY period_start DESC, measurement_id LIMIT 20;

-- 7. Довга форма для BI: читабельна назва KPI та одиниця в окремих стовпцях.
SELECT period_start, measurement_id, ip_version, kpi_code, kpi_name, unit, value
FROM analytics.network_hourly_kpi
WHERE period_start = (SELECT max(period_start) FROM analytics.network_hourly_kpi)
  AND measurement_id = 1001
ORDER BY kpi_code;

-- 8. Materialized views спрацьовують на INSERT та записують маркери.
-- Вони не запускають самостійно годинник і не замінюють Store.maintenance().
SHOW CREATE TABLE monitoring.ping_ingest_trigger;
SHOW CREATE TABLE monitoring.status_ingest_trigger;

-- 9. Час останнього очищення й підтверджені ревізії завершених днів.
SELECT key, value FROM monitoring.retention_runs FINAL ORDER BY key;

-- 10. Перевірка фактичної межі raw. Короткий перехідний рядок можливий
-- між надходженням події та найближчим циклом обробника.
SELECT count() AS raw_series,
       min(event_time) AS first_event_utc,
       max(event_time) AS last_event_utc,
       countIf(event_time < now() - INTERVAL 5 HOUR) AS older_than_5h
FROM monitoring.ping_results FINAL;

-- 11. Контрольні приклади агрегування. Це штучні значення лише в SELECT.
-- Вони не потрапляють у таблиці, Kafka, детектор або Telegram.
SELECT 100.0 * (3 + 9 - 0 - 9) / (3 + 9) AS correct_packet_loss_pct,
       (100.0 * 10 + 1 * 100) / (100 + 1) AS correct_mean_rtt_ms,
       uniqExact(probe) AS distinct_probes_for_whole_period
FROM (SELECT arrayJoin(['A', 'B', 'B', 'C']) AS probe);

-- 12. Безпечна демонстрація межі 04:00 на штучному часі.
-- Це пояснювальний SELECT. Виробничу логіку перевіряють модульні тести.
SELECT simulated_now,
       toDate(simulated_now) - if(toHour(simulated_now) >= 4, 1, 2) AS last_finalizable_day
FROM (
  SELECT arrayJoin([
    toDateTime('2026-11-16 03:59:59', 'Europe/Kyiv'),
    toDateTime('2026-11-16 04:00:00', 'Europe/Kyiv')
  ]) AS simulated_now
);
