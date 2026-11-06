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
