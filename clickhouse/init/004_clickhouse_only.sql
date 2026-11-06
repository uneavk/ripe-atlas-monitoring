CREATE TABLE IF NOT EXISTS monitoring.retention_runs (key String,value String,version UInt64)
ENGINE=ReplacingMergeTree(version) ORDER BY key;
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.ping_ingest_trigger TO monitoring.retention_runs AS
SELECT 'ingest_request' AS key,toString(max(ingested_at)) AS value,toUInt64(toUnixTimestamp64Nano(now64(9))) AS version FROM monitoring.ping_results;
CREATE MATERIALIZED VIEW IF NOT EXISTS monitoring.status_ingest_trigger TO monitoring.retention_runs AS
SELECT 'status_ingest_request' AS key,toString(max(ingested_at)) AS value,toUInt64(toUnixTimestamp64Nano(now64(9))) AS version FROM monitoring.probe_events;
