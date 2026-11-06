
CREATE TABLE IF NOT EXISTS incident_episodes (
 episode_key text PRIMARY KEY, kind text NOT NULL, scope text NOT NULL,
 opened_at timestamptz NOT NULL, last_seen_at timestamptz NOT NULL,
 resolved_at timestamptz, severity text NOT NULL, details jsonb NOT NULL,
 opening_id text NOT NULL REFERENCES monitoring_incidents(incident_id)
);
CREATE TABLE IF NOT EXISTS probe_connectivity_state (
 probe_id bigint PRIMARY KEY, event text NOT NULL, event_timestamp bigint NOT NULL
);
ALTER TABLE monitoring_incidents ADD COLUMN IF NOT EXISTS resolved_at timestamptz;
ALTER TABLE monitoring_incidents ADD COLUMN IF NOT EXISTS episode_id text;
CREATE OR REPLACE VIEW incident_episode_metrics AS
 SELECT kind,scope,opened_at,last_seen_at,resolved_at,
 CASE WHEN resolved_at IS NULL THEN 'Триває' ELSE 'Відновлено' END AS status_uk,
 extract(epoch FROM (coalesce(resolved_at,now())-opened_at)) AS duration_seconds,
 severity,details,opening_id FROM incident_episodes;
CREATE OR REPLACE VIEW incident_history_metrics AS
 SELECT episode_id,kind,scope,min(event_time) AS opened_at,max(resolved_at) AS resolved_at,
 CASE WHEN max(resolved_at) IS NULL THEN 'Триває' ELSE 'Відновлено' END AS status_uk,
 extract(epoch FROM (coalesce(max(resolved_at),now())-min(event_time))) AS duration_seconds
 FROM monitoring_incidents WHERE episode_id IS NOT NULL AND kind<>'RECOVERED'
 GROUP BY episode_id,kind,scope;


CREATE TABLE IF NOT EXISTS processing_errors (
 topic text NOT NULL, partition_id integer NOT NULL, kafka_offset bigint NOT NULL,
 stage text NOT NULL, reason text NOT NULL, received_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(topic,partition_id,kafka_offset)
);
CREATE OR REPLACE VIEW processing_error_summary AS
 SELECT date_trunc('hour',received_at) AS hour_start,stage,reason,count(*) AS rejected_events
 FROM processing_errors GROUP BY 1,2,3;
