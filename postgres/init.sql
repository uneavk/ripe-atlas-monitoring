-- Section 1
-- PostgreSQL stores incidents, Telegram subscriptions and delivery state. See 002_alerts.sql and 003_telegram_subscriptions.sql.

-- Section 2
CREATE TABLE IF NOT EXISTS monitoring_incidents (
    incident_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    scope TEXT NOT NULL,
    event_time TIMESTAMPTZ NOT NULL,
    severity TEXT NOT NULL,
    details JSONB NOT NULL,
    notification_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS monitoring_incidents_time ON monitoring_incidents(event_time DESC);
CREATE TABLE IF NOT EXISTS notification_cooldowns (
    scope TEXT PRIMARY KEY,
    last_queued_at TIMESTAMPTZ NOT NULL DEFAULT to_timestamp(0)
);
CREATE TABLE IF NOT EXISTS telegram_outbox (
    id BIGSERIAL PRIMARY KEY,
    incident_id TEXT UNIQUE NOT NULL REFERENCES monitoring_incidents(incident_id),
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    telegram_message_id BIGINT,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS telegram_outbox_pending ON telegram_outbox(next_attempt_at) WHERE status='pending';

-- Section 3
CREATE TABLE IF NOT EXISTS telegram_subscribers (
    chat_id BIGINT PRIMARY KEY,
    active BOOLEAN NOT NULL DEFAULT true,
    subscribed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS telegram_poll_state (
    id INTEGER PRIMARY KEY CHECK (id=1),
    next_update_id BIGINT NOT NULL DEFAULT 0,
    pause_until TIMESTAMPTZ NOT NULL DEFAULT to_timestamp(0)
);
INSERT INTO telegram_poll_state(id) VALUES (1) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS telegram_command_replies (
    update_id BIGINT PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error TEXT
);
CREATE TABLE IF NOT EXISTS telegram_deliveries (
    outbox_id BIGINT NOT NULL REFERENCES telegram_outbox(id) ON DELETE CASCADE,
    chat_id BIGINT NOT NULL REFERENCES telegram_subscribers(chat_id),
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ,
    telegram_message_id BIGINT,
    last_error TEXT,
    PRIMARY KEY(outbox_id,chat_id)
);
CREATE INDEX IF NOT EXISTS telegram_deliveries_pending ON telegram_deliveries(next_attempt_at) WHERE status='pending';

-- Section 4
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
