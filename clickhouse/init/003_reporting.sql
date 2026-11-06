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
