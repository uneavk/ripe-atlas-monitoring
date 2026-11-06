CREATE DATABASE IF NOT EXISTS monitoring;

CREATE TABLE IF NOT EXISTS monitoring.ping_results
(
    event_id String,
    msm_id UInt32,
    prb_id UInt32,
    event_time DateTime64(3, 'UTC'),
    af UInt8,
    sent UInt16,
    rcvd UInt16,
    loss_pct Float32,
    rtt_min Nullable(Float32),
    rtt_avg Nullable(Float32),
    rtt_max Nullable(Float32),
    dst_name Nullable(String),
    dst_addr Nullable(String),
    src_addr Nullable(String),
    source_mode LowCardinality(String),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(event_time)
ORDER BY (msm_id, prb_id, event_time, event_id);

CREATE TABLE IF NOT EXISTS monitoring.probe_events
(
    event_id String,
    prb_id UInt32,
    event_time DateTime64(3, 'UTC'),
    event LowCardinality(String),
    ingested_at DateTime64(3, 'UTC') DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(event_time)
ORDER BY (prb_id, event_time, event_id);
