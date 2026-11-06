CREATE DATABASE IF NOT EXISTS analytics;

CREATE OR REPLACE VIEW analytics.measurement_directory AS SELECT toUInt32(1001) AS measurement_id,'K-root' AS target_name,'k.root-servers.net' AS target_hostname,'IPv4' AS ip_version,toUInt8(4) AS address_family,toUInt32(240) AS interval_seconds UNION ALL SELECT toUInt32(2001) AS measurement_id,'K-root' AS target_name,'k.root-servers.net' AS target_hostname,'IPv6' AS ip_version,toUInt8(6) AS address_family,toUInt32(240) AS interval_seconds UNION ALL SELECT toUInt32(1004) AS measurement_id,'F-root' AS target_name,'f.root-servers.net' AS target_hostname,'IPv4' AS ip_version,toUInt8(4) AS address_family,toUInt32(240) AS interval_seconds UNION ALL SELECT toUInt32(2004) AS measurement_id,'F-root' AS target_name,'f.root-servers.net' AS target_hostname,'IPv6' AS ip_version,toUInt8(6) AS address_family,toUInt32(240) AS interval_seconds;

CREATE OR REPLACE VIEW analytics.kpi_directory AS SELECT 'measurement_count' AS kpi_code,'Кількість вимірювань' AS kpi_name,'шт.' AS unit UNION ALL SELECT 'probes_observed' AS kpi_code,'Спостережувані зонди' AS kpi_name,'зондів' AS unit UNION ALL SELECT 'packets_sent' AS kpi_code,'Надіслано пакетів' AS kpi_name,'пакетів' AS unit UNION ALL SELECT 'packets_received' AS kpi_code,'Отримано пакетів' AS kpi_name,'пакетів' AS unit UNION ALL SELECT 'packets_lost' AS kpi_code,'Втрачено пакетів' AS kpi_name,'пакетів' AS unit UNION ALL SELECT 'packet_loss_pct' AS kpi_code,'Втрата пакетів' AS kpi_name,'%' AS unit UNION ALL SELECT 'avg_rtt_ms' AS kpi_code,'Середня затримка' AS kpi_name,'мс' AS unit UNION ALL SELECT 'min_rtt_ms' AS kpi_code,'Мінімальна затримка' AS kpi_name,'мс' AS unit UNION ALL SELECT 'max_rtt_ms' AS kpi_code,'Максимальна затримка' AS kpi_name,'мс' AS unit UNION ALL SELECT 'successful_measurements_pct' AS kpi_code,'Вимірювання з відповіддю' AS kpi_name,'%' AS unit UNION ALL SELECT 'high_loss_measurements' AS kpi_code,'Вимірювання із втратою понад 50%' AS kpi_name,'шт.' AS unit UNION ALL SELECT 'no_reply_measurements' AS kpi_code,'Вимірювання без відповіді' AS kpi_name,'шт.' AS unit;

CREATE OR REPLACE VIEW analytics.probe_directory AS
SELECT probe_id,country AS country_code,asn_v4 AS ipv4_provider_asn,asn_v6 AS ipv6_provider_asn,
latitude,longitude,status AS atlas_status FROM monitoring.probe_directory FINAL;

CREATE OR REPLACE VIEW analytics.measurements_live AS
SELECT toTimeZone(p.event_time,'Europe/Kyiv') AS measured_at,p.prb_id AS probe_id,
p.msm_id AS measurement_id,concat('IPv',toString(p.af)) AS ip_version,
coalesce(nullIf(m.target_name,''),p.dst_name,'Unknown') AS target_name,
p.dst_addr AS destination_address,p.src_addr AS source_address,
if(p.af=6,d.asn_v6,d.asn_v4) AS provider_asn,if(provider_asn=0,'Невідомий ASN',concat('AS',toString(provider_asn))) AS provider_name,
d.country AS country_code,d.latitude,d.longitude,p.sent AS packets_sent,p.rcvd AS packets_received,
p.sent-p.rcvd AS packets_lost,p.loss_pct AS packet_loss_pct,p.rtt_avg AS avg_rtt_ms,
p.rtt_min AS min_rtt_ms,p.rtt_max AS max_rtt_ms,p.source_mode,p.event_id
FROM monitoring.ping_results AS p FINAL
LEFT JOIN (SELECT * FROM monitoring.probe_directory FINAL) d ON d.probe_id=p.prb_id
LEFT JOIN analytics.measurement_directory m ON m.measurement_id=p.msm_id
WHERE p.af IN (4,6) AND p.event_time>=now()-INTERVAL 5 HOUR;

CREATE OR REPLACE VIEW analytics.network_5minutes AS
SELECT toStartOfFiveMinutes(measured_at) AS period_start,measurement_id,target_name,ip_version,
count() AS measurement_count,uniqExact(probe_id) AS probes_observed,
sum(q.packets_sent) AS packets_sent,sum(q.packets_received) AS packets_received,
100.0*(packets_sent-packets_received)/nullIf(packets_sent,0) AS packet_loss_pct,
avg(q.avg_rtt_ms) AS avg_rtt_ms,min(q.min_rtt_ms) AS min_rtt_ms,max(q.max_rtt_ms) AS max_rtt_ms,
100.0*countIf(q.packets_received>0)/count() AS successful_measurements_pct,
countIf(q.packets_received=0) AS no_reply_measurements
FROM analytics.measurements_live q
GROUP BY period_start,measurement_id,target_name,ip_version;

CREATE OR REPLACE VIEW analytics.providers_5minutes AS
SELECT toStartOfFiveMinutes(measured_at) AS period_start,measurement_id,target_name,ip_version,provider_asn,provider_name,
count() AS measurement_count,uniqExact(probe_id) AS probes_observed,
sum(q.packets_sent) AS packets_sent,sum(q.packets_received) AS packets_received,
100.0*(packets_sent-packets_received)/nullIf(packets_sent,0) AS packet_loss_pct,
avg(q.avg_rtt_ms) AS avg_rtt_ms,min(q.min_rtt_ms) AS min_rtt_ms,max(q.max_rtt_ms) AS max_rtt_ms,
100.0*countIf(q.packets_received>0)/count() AS successful_measurements_pct,
countIf(q.packets_received=0) AS no_reply_measurements
FROM analytics.measurements_live q
GROUP BY period_start,measurement_id,target_name,ip_version,provider_asn,provider_name;

CREATE OR REPLACE VIEW analytics.network_hourly AS SELECT q.*,coalesce(nullIf(m.target_name,''),concat('RIPE ',toString(q.measurement_id))) AS target_name FROM (SELECT toTimeZone(h.hour_start,'Europe/Kyiv') AS period_start,h.msm_id AS measurement_id,
concat('IPv',toString(h.af)) AS ip_version,
sum(h.samples) AS measurement_count,uniqExactIf(h.probe_id,h.samples>0) AS probes_observed,
sum(h.sent) AS packets_sent,sum(h.received) AS packets_received,packets_sent-packets_received AS packets_lost,
100.0*packets_lost/nullIf(packets_sent,0) AS packet_loss_pct,
sum(h.rtt_sum)/nullIf(sum(h.rtt_count),0) AS avg_rtt_ms,
min(h.rtt_min) AS min_rtt_ms,max(h.rtt_max) AS max_rtt_ms,
100.0*(measurement_count-sum(h.full_loss_samples))/nullIf(measurement_count,0) AS successful_measurements_pct,
sum(h.loss_samples) AS high_loss_measurements,sum(h.full_loss_samples) AS no_reply_measurements
FROM monitoring.hourly_metrics AS h FINAL
WHERE h.af IN (4,6) AND h.msm_id>0 AND h.samples>0 AND h.hour_start>=now()-INTERVAL 48 HOUR AND h.hour_start<toStartOfHour(now())
GROUP BY period_start,h.msm_id,h.af) q LEFT JOIN analytics.measurement_directory m ON m.measurement_id=q.measurement_id;

CREATE OR REPLACE VIEW analytics.network_hourly_kpi AS SELECT q.period_start,q.measurement_id,q.target_name,q.ip_version,tupleElement(metric,1) AS kpi_code,tupleElement(metric,2) AS kpi_name,tupleElement(metric,3) AS unit,tupleElement(metric,4) AS value FROM analytics.network_hourly q ARRAY JOIN [tuple('measurement_count','Кількість вимірювань','шт.',toNullable(toFloat64(q.measurement_count))),tuple('probes_observed','Спостережувані зонди','зондів',toNullable(toFloat64(q.probes_observed))),tuple('packets_sent','Надіслано пакетів','пакетів',toNullable(toFloat64(q.packets_sent))),tuple('packets_received','Отримано пакетів','пакетів',toNullable(toFloat64(q.packets_received))),tuple('packets_lost','Втрачено пакетів','пакетів',toNullable(toFloat64(q.packets_lost))),tuple('packet_loss_pct','Втрата пакетів','%',toNullable(toFloat64(q.packet_loss_pct))),tuple('avg_rtt_ms','Середня затримка','мс',toNullable(toFloat64(q.avg_rtt_ms))),tuple('min_rtt_ms','Мінімальна затримка','мс',toNullable(toFloat64(q.min_rtt_ms))),tuple('max_rtt_ms','Максимальна затримка','мс',toNullable(toFloat64(q.max_rtt_ms))),tuple('successful_measurements_pct','Вимірювання з відповіддю','%',toNullable(toFloat64(q.successful_measurements_pct))),tuple('high_loss_measurements','Вимірювання із втратою понад 50%','шт.',toNullable(toFloat64(q.high_loss_measurements))),tuple('no_reply_measurements','Вимірювання без відповіді','шт.',toNullable(toFloat64(q.no_reply_measurements)))] AS metric;

CREATE OR REPLACE VIEW analytics.providers_hourly AS SELECT q.*,if(q.provider_asn=0,'Невідомий ASN',concat('AS',toString(q.provider_asn))) AS provider_name,coalesce(nullIf(m.target_name,''),concat('RIPE ',toString(q.measurement_id))) AS target_name FROM (SELECT toTimeZone(h.hour_start,'Europe/Kyiv') AS period_start,h.msm_id AS measurement_id,
concat('IPv',toString(h.af)) AS ip_version,h.asn AS provider_asn,
sum(h.samples) AS measurement_count,uniqExactIf(h.probe_id,h.samples>0) AS probes_observed,
sum(h.sent) AS packets_sent,sum(h.received) AS packets_received,packets_sent-packets_received AS packets_lost,
100.0*packets_lost/nullIf(packets_sent,0) AS packet_loss_pct,
sum(h.rtt_sum)/nullIf(sum(h.rtt_count),0) AS avg_rtt_ms,
min(h.rtt_min) AS min_rtt_ms,max(h.rtt_max) AS max_rtt_ms,
100.0*(measurement_count-sum(h.full_loss_samples))/nullIf(measurement_count,0) AS successful_measurements_pct,
sum(h.loss_samples) AS high_loss_measurements,sum(h.full_loss_samples) AS no_reply_measurements
FROM monitoring.hourly_metrics AS h FINAL
WHERE h.af IN (4,6) AND h.msm_id>0 AND h.samples>0 AND h.hour_start>=now()-INTERVAL 48 HOUR AND h.hour_start<toStartOfHour(now())
GROUP BY period_start,h.msm_id,h.af,h.asn) q LEFT JOIN analytics.measurement_directory m ON m.measurement_id=q.measurement_id;

CREATE OR REPLACE VIEW analytics.providers_hourly_kpi AS SELECT q.period_start,q.measurement_id,q.target_name,q.ip_version,q.provider_asn,q.provider_name,tupleElement(metric,1) AS kpi_code,tupleElement(metric,2) AS kpi_name,tupleElement(metric,3) AS unit,tupleElement(metric,4) AS value FROM analytics.providers_hourly q ARRAY JOIN [tuple('measurement_count','Кількість вимірювань','шт.',toNullable(toFloat64(q.measurement_count))),tuple('probes_observed','Спостережувані зонди','зондів',toNullable(toFloat64(q.probes_observed))),tuple('packets_sent','Надіслано пакетів','пакетів',toNullable(toFloat64(q.packets_sent))),tuple('packets_received','Отримано пакетів','пакетів',toNullable(toFloat64(q.packets_received))),tuple('packets_lost','Втрачено пакетів','пакетів',toNullable(toFloat64(q.packets_lost))),tuple('packet_loss_pct','Втрата пакетів','%',toNullable(toFloat64(q.packet_loss_pct))),tuple('avg_rtt_ms','Середня затримка','мс',toNullable(toFloat64(q.avg_rtt_ms))),tuple('min_rtt_ms','Мінімальна затримка','мс',toNullable(toFloat64(q.min_rtt_ms))),tuple('max_rtt_ms','Максимальна затримка','мс',toNullable(toFloat64(q.max_rtt_ms))),tuple('successful_measurements_pct','Вимірювання з відповіддю','%',toNullable(toFloat64(q.successful_measurements_pct))),tuple('high_loss_measurements','Вимірювання із втратою понад 50%','шт.',toNullable(toFloat64(q.high_loss_measurements))),tuple('no_reply_measurements','Вимірювання без відповіді','шт.',toNullable(toFloat64(q.no_reply_measurements)))] AS metric;

CREATE OR REPLACE VIEW analytics.probes_hourly AS SELECT q.*,if(q.provider_asn=0,'Невідомий ASN',concat('AS',toString(q.provider_asn))) AS provider_name,coalesce(nullIf(m.target_name,''),concat('RIPE ',toString(q.measurement_id))) AS target_name FROM (SELECT toTimeZone(h.hour_start,'Europe/Kyiv') AS period_start,h.msm_id AS measurement_id,
concat('IPv',toString(h.af)) AS ip_version,h.asn AS provider_asn,h.probe_id AS probe_id,
sum(h.samples) AS measurement_count,uniqExactIf(h.probe_id,h.samples>0) AS probes_observed,
sum(h.sent) AS packets_sent,sum(h.received) AS packets_received,packets_sent-packets_received AS packets_lost,
100.0*packets_lost/nullIf(packets_sent,0) AS packet_loss_pct,
sum(h.rtt_sum)/nullIf(sum(h.rtt_count),0) AS avg_rtt_ms,
min(h.rtt_min) AS min_rtt_ms,max(h.rtt_max) AS max_rtt_ms,
100.0*(measurement_count-sum(h.full_loss_samples))/nullIf(measurement_count,0) AS successful_measurements_pct,
sum(h.loss_samples) AS high_loss_measurements,sum(h.full_loss_samples) AS no_reply_measurements
FROM monitoring.hourly_metrics AS h FINAL
WHERE h.af IN (4,6) AND h.msm_id>0 AND h.samples>0 AND h.hour_start>=now()-INTERVAL 48 HOUR AND h.hour_start<toStartOfHour(now())
GROUP BY period_start,h.msm_id,h.af,h.asn,h.probe_id) q LEFT JOIN analytics.measurement_directory m ON m.measurement_id=q.measurement_id;

CREATE OR REPLACE VIEW analytics.probes_hourly_kpi AS SELECT q.period_start,q.measurement_id,q.target_name,q.ip_version,q.provider_asn,q.provider_name,q.probe_id,tupleElement(metric,1) AS kpi_code,tupleElement(metric,2) AS kpi_name,tupleElement(metric,3) AS unit,tupleElement(metric,4) AS value FROM analytics.probes_hourly q ARRAY JOIN [tuple('measurement_count','Кількість вимірювань','шт.',toNullable(toFloat64(q.measurement_count))),tuple('packets_sent','Надіслано пакетів','пакетів',toNullable(toFloat64(q.packets_sent))),tuple('packets_received','Отримано пакетів','пакетів',toNullable(toFloat64(q.packets_received))),tuple('packets_lost','Втрачено пакетів','пакетів',toNullable(toFloat64(q.packets_lost))),tuple('packet_loss_pct','Втрата пакетів','%',toNullable(toFloat64(q.packet_loss_pct))),tuple('avg_rtt_ms','Середня затримка','мс',toNullable(toFloat64(q.avg_rtt_ms))),tuple('min_rtt_ms','Мінімальна затримка','мс',toNullable(toFloat64(q.min_rtt_ms))),tuple('max_rtt_ms','Максимальна затримка','мс',toNullable(toFloat64(q.max_rtt_ms))),tuple('successful_measurements_pct','Вимірювання з відповіддю','%',toNullable(toFloat64(q.successful_measurements_pct))),tuple('high_loss_measurements','Вимірювання із втратою понад 50%','шт.',toNullable(toFloat64(q.high_loss_measurements))),tuple('no_reply_measurements','Вимірювання без відповіді','шт.',toNullable(toFloat64(q.no_reply_measurements)))] AS metric;

CREATE OR REPLACE VIEW analytics.network_daily AS SELECT q.*,coalesce(nullIf(m.target_name,''),concat('RIPE ',toString(q.measurement_id))) AS target_name FROM (SELECT toDateTime(h.day,'Europe/Kyiv') AS period_start,h.msm_id AS measurement_id,
concat('IPv',toString(h.af)) AS ip_version,
sum(h.samples) AS measurement_count,uniqExactIf(h.probe_id,h.samples>0) AS probes_observed,
sum(h.sent) AS packets_sent,sum(h.received) AS packets_received,packets_sent-packets_received AS packets_lost,
100.0*packets_lost/nullIf(packets_sent,0) AS packet_loss_pct,
sum(h.rtt_sum)/nullIf(sum(h.rtt_count),0) AS avg_rtt_ms,
min(h.rtt_min) AS min_rtt_ms,max(h.rtt_max) AS max_rtt_ms,
100.0*(measurement_count-sum(h.full_loss_samples))/nullIf(measurement_count,0) AS successful_measurements_pct,
sum(h.loss_samples) AS high_loss_measurements,sum(h.full_loss_samples) AS no_reply_measurements
FROM monitoring.daily_metrics AS h FINAL
WHERE h.af IN (4,6) AND h.msm_id>0 AND h.samples>0 AND 1
GROUP BY period_start,h.msm_id,h.af) q LEFT JOIN analytics.measurement_directory m ON m.measurement_id=q.measurement_id;

CREATE OR REPLACE VIEW analytics.network_daily_kpi AS SELECT q.period_start,q.measurement_id,q.target_name,q.ip_version,tupleElement(metric,1) AS kpi_code,tupleElement(metric,2) AS kpi_name,tupleElement(metric,3) AS unit,tupleElement(metric,4) AS value FROM analytics.network_daily q ARRAY JOIN [tuple('measurement_count','Кількість вимірювань','шт.',toNullable(toFloat64(q.measurement_count))),tuple('probes_observed','Спостережувані зонди','зондів',toNullable(toFloat64(q.probes_observed))),tuple('packets_sent','Надіслано пакетів','пакетів',toNullable(toFloat64(q.packets_sent))),tuple('packets_received','Отримано пакетів','пакетів',toNullable(toFloat64(q.packets_received))),tuple('packets_lost','Втрачено пакетів','пакетів',toNullable(toFloat64(q.packets_lost))),tuple('packet_loss_pct','Втрата пакетів','%',toNullable(toFloat64(q.packet_loss_pct))),tuple('avg_rtt_ms','Середня затримка','мс',toNullable(toFloat64(q.avg_rtt_ms))),tuple('min_rtt_ms','Мінімальна затримка','мс',toNullable(toFloat64(q.min_rtt_ms))),tuple('max_rtt_ms','Максимальна затримка','мс',toNullable(toFloat64(q.max_rtt_ms))),tuple('successful_measurements_pct','Вимірювання з відповіддю','%',toNullable(toFloat64(q.successful_measurements_pct))),tuple('high_loss_measurements','Вимірювання із втратою понад 50%','шт.',toNullable(toFloat64(q.high_loss_measurements))),tuple('no_reply_measurements','Вимірювання без відповіді','шт.',toNullable(toFloat64(q.no_reply_measurements)))] AS metric;

CREATE OR REPLACE VIEW analytics.providers_daily AS SELECT q.*,if(q.provider_asn=0,'Невідомий ASN',concat('AS',toString(q.provider_asn))) AS provider_name,coalesce(nullIf(m.target_name,''),concat('RIPE ',toString(q.measurement_id))) AS target_name FROM (SELECT toDateTime(h.day,'Europe/Kyiv') AS period_start,h.msm_id AS measurement_id,
concat('IPv',toString(h.af)) AS ip_version,h.asn AS provider_asn,
sum(h.samples) AS measurement_count,uniqExactIf(h.probe_id,h.samples>0) AS probes_observed,
sum(h.sent) AS packets_sent,sum(h.received) AS packets_received,packets_sent-packets_received AS packets_lost,
100.0*packets_lost/nullIf(packets_sent,0) AS packet_loss_pct,
sum(h.rtt_sum)/nullIf(sum(h.rtt_count),0) AS avg_rtt_ms,
min(h.rtt_min) AS min_rtt_ms,max(h.rtt_max) AS max_rtt_ms,
100.0*(measurement_count-sum(h.full_loss_samples))/nullIf(measurement_count,0) AS successful_measurements_pct,
sum(h.loss_samples) AS high_loss_measurements,sum(h.full_loss_samples) AS no_reply_measurements
FROM monitoring.daily_metrics AS h FINAL
WHERE h.af IN (4,6) AND h.msm_id>0 AND h.samples>0 AND 1
GROUP BY period_start,h.msm_id,h.af,h.asn) q LEFT JOIN analytics.measurement_directory m ON m.measurement_id=q.measurement_id;

CREATE OR REPLACE VIEW analytics.providers_daily_kpi AS SELECT q.period_start,q.measurement_id,q.target_name,q.ip_version,q.provider_asn,q.provider_name,tupleElement(metric,1) AS kpi_code,tupleElement(metric,2) AS kpi_name,tupleElement(metric,3) AS unit,tupleElement(metric,4) AS value FROM analytics.providers_daily q ARRAY JOIN [tuple('measurement_count','Кількість вимірювань','шт.',toNullable(toFloat64(q.measurement_count))),tuple('probes_observed','Спостережувані зонди','зондів',toNullable(toFloat64(q.probes_observed))),tuple('packets_sent','Надіслано пакетів','пакетів',toNullable(toFloat64(q.packets_sent))),tuple('packets_received','Отримано пакетів','пакетів',toNullable(toFloat64(q.packets_received))),tuple('packets_lost','Втрачено пакетів','пакетів',toNullable(toFloat64(q.packets_lost))),tuple('packet_loss_pct','Втрата пакетів','%',toNullable(toFloat64(q.packet_loss_pct))),tuple('avg_rtt_ms','Середня затримка','мс',toNullable(toFloat64(q.avg_rtt_ms))),tuple('min_rtt_ms','Мінімальна затримка','мс',toNullable(toFloat64(q.min_rtt_ms))),tuple('max_rtt_ms','Максимальна затримка','мс',toNullable(toFloat64(q.max_rtt_ms))),tuple('successful_measurements_pct','Вимірювання з відповіддю','%',toNullable(toFloat64(q.successful_measurements_pct))),tuple('high_loss_measurements','Вимірювання із втратою понад 50%','шт.',toNullable(toFloat64(q.high_loss_measurements))),tuple('no_reply_measurements','Вимірювання без відповіді','шт.',toNullable(toFloat64(q.no_reply_measurements)))] AS metric;

CREATE OR REPLACE VIEW analytics.probes_daily AS SELECT q.*,if(q.provider_asn=0,'Невідомий ASN',concat('AS',toString(q.provider_asn))) AS provider_name,coalesce(nullIf(m.target_name,''),concat('RIPE ',toString(q.measurement_id))) AS target_name FROM (SELECT toDateTime(h.day,'Europe/Kyiv') AS period_start,h.msm_id AS measurement_id,
concat('IPv',toString(h.af)) AS ip_version,h.asn AS provider_asn,h.probe_id AS probe_id,
sum(h.samples) AS measurement_count,uniqExactIf(h.probe_id,h.samples>0) AS probes_observed,
sum(h.sent) AS packets_sent,sum(h.received) AS packets_received,packets_sent-packets_received AS packets_lost,
100.0*packets_lost/nullIf(packets_sent,0) AS packet_loss_pct,
sum(h.rtt_sum)/nullIf(sum(h.rtt_count),0) AS avg_rtt_ms,
min(h.rtt_min) AS min_rtt_ms,max(h.rtt_max) AS max_rtt_ms,
100.0*(measurement_count-sum(h.full_loss_samples))/nullIf(measurement_count,0) AS successful_measurements_pct,
sum(h.loss_samples) AS high_loss_measurements,sum(h.full_loss_samples) AS no_reply_measurements
FROM monitoring.daily_metrics AS h FINAL
WHERE h.af IN (4,6) AND h.msm_id>0 AND h.samples>0 AND 1
GROUP BY period_start,h.msm_id,h.af,h.asn,h.probe_id) q LEFT JOIN analytics.measurement_directory m ON m.measurement_id=q.measurement_id;

CREATE OR REPLACE VIEW analytics.probes_daily_kpi AS SELECT q.period_start,q.measurement_id,q.target_name,q.ip_version,q.provider_asn,q.provider_name,q.probe_id,tupleElement(metric,1) AS kpi_code,tupleElement(metric,2) AS kpi_name,tupleElement(metric,3) AS unit,tupleElement(metric,4) AS value FROM analytics.probes_daily q ARRAY JOIN [tuple('measurement_count','Кількість вимірювань','шт.',toNullable(toFloat64(q.measurement_count))),tuple('packets_sent','Надіслано пакетів','пакетів',toNullable(toFloat64(q.packets_sent))),tuple('packets_received','Отримано пакетів','пакетів',toNullable(toFloat64(q.packets_received))),tuple('packets_lost','Втрачено пакетів','пакетів',toNullable(toFloat64(q.packets_lost))),tuple('packet_loss_pct','Втрата пакетів','%',toNullable(toFloat64(q.packet_loss_pct))),tuple('avg_rtt_ms','Середня затримка','мс',toNullable(toFloat64(q.avg_rtt_ms))),tuple('min_rtt_ms','Мінімальна затримка','мс',toNullable(toFloat64(q.min_rtt_ms))),tuple('max_rtt_ms','Максимальна затримка','мс',toNullable(toFloat64(q.max_rtt_ms))),tuple('successful_measurements_pct','Вимірювання з відповіддю','%',toNullable(toFloat64(q.successful_measurements_pct))),tuple('high_loss_measurements','Вимірювання із втратою понад 50%','шт.',toNullable(toFloat64(q.high_loss_measurements))),tuple('no_reply_measurements','Вимірювання без відповіді','шт.',toNullable(toFloat64(q.no_reply_measurements)))] AS metric;

CREATE OR REPLACE VIEW analytics.data_freshness AS
SELECT m.measurement_id,m.target_name,m.ip_version,if(p.measurements=0,NULL,toTimeZone(p.latest_at,'Europe/Kyiv')) AS latest_measurement_at,
if(p.measurements=0,NULL,dateDiff('second',p.latest_at,now())) AS data_age_seconds,
p.measurements AS measurements_last_5h,p.probes AS probes_observed_last_5h,
multiIf(p.measurements=0,'Немає даних',dateDiff('second',p.latest_at,now())>900,'Дані застаріли','Дані надходять') AS data_status
FROM analytics.measurement_directory m LEFT JOIN
(SELECT msm_id,max(event_time) AS latest_at,count() AS measurements,uniqExact(prb_id) AS probes
FROM monitoring.ping_results FINAL WHERE event_time>=now()-INTERVAL 5 HOUR GROUP BY msm_id) p ON p.msm_id=m.measurement_id;

CREATE OR REPLACE VIEW analytics.probe_events_live AS
SELECT toTimeZone(event_time,'Europe/Kyiv') AS event_at,prb_id AS probe_id,event AS connection_event,event_id
FROM monitoring.probe_events FINAL WHERE event_time>=now()-INTERVAL 5 HOUR;
