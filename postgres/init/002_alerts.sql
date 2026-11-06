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
