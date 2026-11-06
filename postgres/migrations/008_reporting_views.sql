
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE OR REPLACE VIEW reporting.incidents AS
SELECT incident_id,coalesce(episode_id,incident_id) AS episode_id,first_event_time AS started_at,
resolved_at,kind AS incident_type,scope,severity,
CASE WHEN kind='RECOVERED' THEN 'Повідомлення про відновлення'
 WHEN resolved_at IS NOT NULL THEN 'Відновлено' ELSE 'Триває' END AS incident_status,
NULLIF(details->>'probe_id','')::bigint AS probe_id,
NULLIF(details->>'asn','')::bigint AS provider_asn,
NULLIF(details->>'msm_id','')::integer AS measurement_id,
CASE details->>'af' WHEN '4' THEN 'IPv4' WHEN '6' THEN 'IPv6' ELSE 'Не застосовується' END AS ip_version,
notification_status
FROM (
 SELECT DISTINCT ON (coalesce(episode_id,incident_id)) *,
 min(event_time) OVER (PARTITION BY coalesce(episode_id,incident_id)) AS first_event_time
 FROM public.monitoring_incidents WHERE kind<>'RECOVERED'
 ORDER BY coalesce(episode_id,incident_id),event_time DESC
) episodes;

CREATE OR REPLACE VIEW reporting.incidents_hourly AS
SELECT date_trunc('hour',started_at) AS period_start,incident_type,severity,ip_version,
measurement_id,count(DISTINCT episode_id) AS incident_count
FROM reporting.incidents WHERE incident_type<>'RECOVERED'
GROUP BY 1,2,3,4,5;

CREATE OR REPLACE VIEW reporting.incidents_daily AS
SELECT (started_at AT TIME ZONE 'Europe/Kyiv')::date AS day,incident_type,ip_version,
measurement_id,count(DISTINCT episode_id) AS incident_count
FROM reporting.incidents WHERE incident_type<>'RECOVERED'
GROUP BY 1,2,3,4;

CREATE OR REPLACE VIEW reporting.processing_errors_hourly AS
SELECT date_trunc('hour',received_at) AS period_start,stage,reason,count(*) AS rejected_events
FROM public.processing_errors GROUP BY 1,2,3;

CREATE OR REPLACE VIEW reporting.telegram_deliveries_daily AS
SELECT (o.created_at AT TIME ZONE 'Europe/Kyiv')::date AS day,d.status AS delivery_status,
count(*) AS delivery_count
FROM public.telegram_deliveries d JOIN public.telegram_outbox o ON o.id=d.outbox_id
GROUP BY 1,2;
