-- Section 1
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

-- Section 2
CREATE TABLE IF NOT EXISTS monitoring.hourly_metrics (
 hour_start DateTime('UTC'),probe_id UInt32,msm_id UInt32,af UInt8,asn UInt32,
 samples UInt64,sent UInt64,received UInt64,rtt_sum Float64,rtt_count UInt64,rtt_min Nullable(Float64),rtt_max Nullable(Float64),
 normal_rtt_sum Float64,normal_rtt_count UInt64,loss_samples UInt64,full_loss_samples UInt64,connects UInt64,disconnects UInt64,
 version UInt64
) ENGINE=ReplacingMergeTree(version) PARTITION BY toDate(hour_start) ORDER BY (hour_start,probe_id,msm_id,af,asn);
CREATE TABLE IF NOT EXISTS monitoring.daily_metrics (
 day Date,probe_id UInt32,msm_id UInt32,af UInt8,asn UInt32,
 samples UInt64,sent UInt64,received UInt64,rtt_sum Float64,rtt_count UInt64,rtt_min Nullable(Float64),rtt_max Nullable(Float64),
 normal_rtt_sum Float64,normal_rtt_count UInt64,loss_samples UInt64,full_loss_samples UInt64,connects UInt64,disconnects UInt64,
 version UInt64
) ENGINE=ReplacingMergeTree(version) PARTITION BY toYYYYMM(day) ORDER BY (day,probe_id,msm_id,af,asn);
CREATE OR REPLACE VIEW monitoring.raw_ping_last_5h AS SELECT * FROM monitoring.ping_results FINAL WHERE event_time>=now()-INTERVAL 5 HOUR;
CREATE OR REPLACE VIEW monitoring.raw_probe_events_last_5h AS SELECT * FROM monitoring.probe_events FINAL WHERE event_time>=now()-INTERVAL 5 HOUR;
CREATE OR REPLACE VIEW monitoring.hourly_network_metrics AS
 SELECT hour_start,toTimeZone(hour_start,'Europe/Kyiv') AS local_hour,probe_id,msm_id,af,asn,samples,sent,received,
 100.0*(sent-received)/nullIf(sent,0) AS packet_loss_pct,rtt_sum/nullIf(rtt_count,0) AS avg_rtt_ms,rtt_min AS min_rtt_ms,rtt_max AS max_rtt_ms,
 100.0*(samples-full_loss_samples)/nullIf(samples,0) AS measurement_success_pct,connects,disconnects
 FROM monitoring.hourly_metrics FINAL WHERE af>0 AND hour_start>=now()-INTERVAL 2 DAY AND hour_start<toStartOfHour(now());
CREATE OR REPLACE VIEW monitoring.daily_network_metrics AS
 SELECT day,probe_id,msm_id,af,asn,samples,sent,received,100.0*(sent-received)/nullIf(sent,0) AS packet_loss_pct,
 rtt_sum/nullIf(rtt_count,0) AS avg_rtt_ms,rtt_min AS min_rtt_ms,rtt_max AS max_rtt_ms,
 100.0*(samples-full_loss_samples)/nullIf(samples,0) AS measurement_success_pct,connects,disconnects
 FROM monitoring.daily_metrics FINAL WHERE af>0;
CREATE OR REPLACE VIEW monitoring.hourly_provider_metrics AS
 SELECT hour_start,asn,af,msm_id,uniqExact(probe_id) AS observed_probes,sum(samples) AS samples,
 100.0*(sum(sent)-sum(received))/nullIf(sum(sent),0) AS packet_loss_pct,
 sum(rtt_sum)/nullIf(sum(rtt_count),0) AS avg_rtt_ms,sum(disconnects) AS disconnects
 FROM monitoring.hourly_metrics FINAL WHERE af>0 AND hour_start>=now()-INTERVAL 2 DAY AND hour_start<toStartOfHour(now()) GROUP BY hour_start,asn,af,msm_id;
CREATE OR REPLACE VIEW monitoring.daily_provider_metrics AS
 SELECT day,asn,af,msm_id,uniqExact(probe_id) AS observed_probes,sum(samples) AS samples,
 100.0*(sum(sent)-sum(received))/nullIf(sum(sent),0) AS packet_loss_pct,
 sum(rtt_sum)/nullIf(sum(rtt_count),0) AS avg_rtt_ms,sum(disconnects) AS disconnects
 FROM monitoring.daily_metrics FINAL WHERE af>0 GROUP BY day,asn,af,msm_id;

-- Section 3
CREATE TABLE IF NOT EXISTS monitoring.probe_directory (probe_id UInt32,country LowCardinality(String),asn_v4 UInt32,asn_v6 UInt32,latitude Nullable(Float64),longitude Nullable(Float64),status String,version UInt64)
ENGINE=ReplacingMergeTree(version) ORDER BY probe_id;
CREATE OR REPLACE VIEW monitoring.live_network_measurements AS
 SELECT r.event_id,r.event_time,toTimeZone(r.event_time,'Europe/Kyiv') AS local_time,r.prb_id AS probe_id,r.msm_id,r.af,
 if(r.af=6,p.asn_v6,p.asn_v4) AS asn,p.country,p.latitude,p.longitude,r.rtt_avg AS rtt_ms,r.loss_pct AS packet_loss_pct,r.sent,r.rcvd AS received,r.dst_name AS target,r.source_mode
 FROM (SELECT * FROM monitoring.ping_results FINAL WHERE event_time>=now()-INTERVAL 5 HOUR) r
 LEFT JOIN (SELECT * FROM monitoring.probe_directory FINAL) p ON p.probe_id=r.prb_id;
CREATE OR REPLACE VIEW monitoring.daily_probe_activity AS SELECT day,probe_id,asn,connects,disconnects FROM monitoring.daily_metrics FINAL WHERE af=0;
CREATE OR REPLACE VIEW monitoring.hourly_country_metrics AS
 SELECT hour_start,toTimeZone(hour_start,'Europe/Kyiv') AS local_hour,af,msm_id,uniqExact(probe_id) AS observed_probes,sum(samples) AS samples,
 100.0*(sum(sent)-sum(received))/nullIf(sum(sent),0) AS packet_loss_pct,sum(rtt_sum)/nullIf(sum(rtt_count),0) AS avg_rtt_ms
 FROM monitoring.hourly_metrics FINAL WHERE af>0 AND hour_start>=now()-INTERVAL 2 DAY AND hour_start<toStartOfHour(now()) GROUP BY hour_start,af,msm_id;
CREATE OR REPLACE VIEW monitoring.daily_country_metrics AS
 SELECT day,af,msm_id,uniqExact(probe_id) AS observed_probes,sum(samples) AS samples,
 100.0*(sum(sent)-sum(received))/nullIf(sum(sent),0) AS packet_loss_pct,sum(rtt_sum)/nullIf(sum(rtt_count),0) AS avg_rtt_ms
 FROM monitoring.daily_metrics FINAL WHERE af>0 GROUP BY day,af,msm_id;

-- Section 4
CREATE TABLE IF NOT EXISTS monitoring.retention_runs (key String,value String,version UInt64)
ENGINE=ReplacingMergeTree(version) ORDER BY key;
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.ping_ingest_trigger TO monitoring.retention_runs AS
SELECT 'ingest_request' AS key,toString(max(ingested_at)) AS value,toUInt64(toUnixTimestamp64Nano(now64(9))) AS version FROM monitoring.ping_results;
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.status_ingest_trigger TO monitoring.retention_runs AS
SELECT 'status_ingest_request' AS key,toString(max(ingested_at)) AS value,toUInt64(toUnixTimestamp64Nano(now64(9))) AS version FROM monitoring.probe_events;
