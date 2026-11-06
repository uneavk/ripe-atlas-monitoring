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
