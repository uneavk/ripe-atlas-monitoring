"""Readable reporting layer. Storage tables and retention remain in monitoring."""
from pathlib import Path
def quote(value):
    return "'"+str(value).replace('\\','\\\\').replace("'","\\'")+"'"

MEASUREMENTS=[(1001,'K-root','k.root-servers.net','IPv4',4,240),(2001,'K-root','k.root-servers.net','IPv6',6,240),(1004,'F-root','f.root-servers.net','IPv4',4,240),(2004,'F-root','f.root-servers.net','IPv6',6,240)]
METRICS=[('measurement_count','Кількість вимірювань','шт.'),('probes_observed','Спостережувані зонди','зондів'),('packets_sent','Надіслано пакетів','пакетів'),('packets_received','Отримано пакетів','пакетів'),('packets_lost','Втрачено пакетів','пакетів'),('packet_loss_pct','Втрата пакетів','%'),('avg_rtt_ms','Середня затримка','мс'),('min_rtt_ms','Мінімальна затримка','мс'),('max_rtt_ms','Максимальна затримка','мс'),('successful_measurements_pct','Вимірювання з відповіддю','%'),('high_loss_measurements','Вимірювання із втратою понад 50%','шт.'),('no_reply_measurements','Вимірювання без відповіді','шт.')]

def definitions():
    statements=['CREATE DATABASE IF NOT EXISTS analytics']
    rows=' UNION ALL '.join('SELECT '+','.join([f'toUInt32({m}) AS measurement_id',quote(short)+' AS target_name',quote(host)+' AS target_hostname',quote(ip)+' AS ip_version',f'toUInt8({af}) AS address_family',f'toUInt32({interval}) AS interval_seconds']) for m,short,host,ip,af,interval in MEASUREMENTS)
    statements.append('CREATE OR REPLACE VIEW analytics.measurement_directory AS '+rows)
    statements.append('CREATE OR REPLACE VIEW analytics.kpi_directory AS '+' UNION ALL '.join('SELECT '+quote(code)+' AS kpi_code,'+quote(name)+' AS kpi_name,'+quote(unit)+' AS unit' for code,name,unit in METRICS))
    statements.append("""CREATE OR REPLACE VIEW analytics.probe_directory AS
SELECT probe_id,country AS country_code,asn_v4 AS ipv4_provider_asn,asn_v6 AS ipv6_provider_asn,
latitude,longitude,status AS atlas_status FROM monitoring.probe_directory FINAL""")
    statements.append("""CREATE OR REPLACE VIEW analytics.measurements_live AS
SELECT toTimeZone(p.event_time,'Europe/Kyiv') AS measured_at,p.prb_id AS probe_id,
p.msm_id AS measurement_id,concat('IPv',toString(p.af)) AS ip_version,
coalesce(nullIf(m.target_name,''),p.dst_name,'Unknown') AS target_name,
p.dst_addr AS destination_address,p.src_addr AS source_address,
if(p.af=6,d.asn_v6,d.asn_v4) AS provider_asn,if(provider_asn=0,'Невідомий ASN',concat('AS',toString(provider_asn))) AS provider_name,
d.country AS country_code,d.latitude,d.longitude,p.sent AS packets_sent,p.rcvd AS packets_received,
p.sent-p.rcvd AS packets_lost,p.loss_pct AS packet_loss_pct,p.rtt_avg AS avg_rtt_ms,
p.rtt_min AS min_rtt_ms,p.rtt_max AS max_rtt_ms,p.source_mode,p.event_id
FROM monitoring.ping_results AS p FINAL
LEFT JOIN (SELECT * FROM monitoring.probe_directory FINAL) d ON d.probe_id=p.prb_id
LEFT JOIN analytics.measurement_directory m ON m.measurement_id=p.msm_id
WHERE p.af IN (4,6) AND p.event_time>=now()-INTERVAL 5 HOUR""")
    for level in ('network','providers'):
        extra=',provider_asn,provider_name' if level=='providers' else ''
        statements.append(f"""CREATE OR REPLACE VIEW analytics.{level}_5minutes AS
SELECT toStartOfFiveMinutes(measured_at) AS period_start,measurement_id,target_name,ip_version{extra},
count() AS measurement_count,uniqExact(probe_id) AS probes_observed,
sum(q.packets_sent) AS packets_sent,sum(q.packets_received) AS packets_received,
100.0*(packets_sent-packets_received)/nullIf(packets_sent,0) AS packet_loss_pct,
avg(q.avg_rtt_ms) AS avg_rtt_ms,min(q.min_rtt_ms) AS min_rtt_ms,max(q.max_rtt_ms) AS max_rtt_ms,
100.0*countIf(q.packets_received>0)/count() AS successful_measurements_pct,
countIf(q.packets_received=0) AS no_reply_measurements
FROM analytics.measurements_live q
GROUP BY period_start,measurement_id,target_name,ip_version{extra}""")
    for grain in ('hourly','daily'):
        hourly=grain=='hourly'
        time="toTimeZone(h.hour_start,'Europe/Kyiv')" if hourly else "toDateTime(h.day,'Europe/Kyiv')"
        period_filter="h.hour_start>=now()-INTERVAL 48 HOUR AND h.hour_start<toStartOfHour(now())" if hourly else '1'
        for level in ('network','providers','probes'):
            dims=['h.msm_id','h.af']
            if level in ('providers','probes'):dims.append('h.asn')
            if level=='probes':dims.append('h.probe_id')
            extra=',h.asn AS provider_asn' if level in ('providers','probes') else ''
            if level=='probes':extra+=',h.probe_id AS probe_id'
            aggregate=f"""SELECT {time} AS period_start,h.msm_id AS measurement_id,
concat('IPv',toString(h.af)) AS ip_version{extra},
sum(h.samples) AS measurement_count,uniqExactIf(h.probe_id,h.samples>0) AS probes_observed,
sum(h.sent) AS packets_sent,sum(h.received) AS packets_received,packets_sent-packets_received AS packets_lost,
100.0*packets_lost/nullIf(packets_sent,0) AS packet_loss_pct,
sum(h.rtt_sum)/nullIf(sum(h.rtt_count),0) AS avg_rtt_ms,
min(h.rtt_min) AS min_rtt_ms,max(h.rtt_max) AS max_rtt_ms,
100.0*(measurement_count-sum(h.full_loss_samples))/nullIf(measurement_count,0) AS successful_measurements_pct,
sum(h.loss_samples) AS high_loss_measurements,sum(h.full_loss_samples) AS no_reply_measurements
FROM monitoring.{grain}_metrics AS h FINAL
WHERE h.af IN (4,6) AND h.msm_id>0 AND h.samples>0 AND {period_filter}
GROUP BY period_start,{','.join(dims)}"""
            name=f'{level}_{grain}'
            columns='q.*'
            if level in ('providers','probes'):columns+=",if(q.provider_asn=0,'Невідомий ASN',concat('AS',toString(q.provider_asn))) AS provider_name"
            statements.append(f"CREATE OR REPLACE VIEW analytics.{name} AS SELECT {columns},coalesce(nullIf(m.target_name,''),concat('RIPE ',toString(q.measurement_id))) AS target_name FROM ({aggregate}) q LEFT JOIN analytics.measurement_directory m ON m.measurement_id=q.measurement_id")
            metric_pairs=','.join('tuple('+quote(code)+','+quote(label)+','+quote(unit)+',toNullable(toFloat64(q.'+code+')))' for code,label,unit in METRICS if not(level=='probes' and code=='probes_observed'))
            selected='q.period_start,q.measurement_id,q.target_name,q.ip_version'
            if level in ('providers','probes'):selected+=',q.provider_asn,q.provider_name'
            if level=='probes':selected+=',q.probe_id'
            statements.append(f'CREATE OR REPLACE VIEW analytics.{name}_kpi AS SELECT {selected},tupleElement(metric,1) AS kpi_code,tupleElement(metric,2) AS kpi_name,tupleElement(metric,3) AS unit,tupleElement(metric,4) AS value FROM analytics.{name} q ARRAY JOIN [{metric_pairs}] AS metric')
    statements.append("""CREATE OR REPLACE VIEW analytics.data_freshness AS
SELECT m.measurement_id,m.target_name,m.ip_version,if(p.measurements=0,NULL,toTimeZone(p.latest_at,'Europe/Kyiv')) AS latest_measurement_at,
if(p.measurements=0,NULL,dateDiff('second',p.latest_at,now())) AS data_age_seconds,
p.measurements AS measurements_last_5h,p.probes AS probes_observed_last_5h,
multiIf(p.measurements=0,'Немає даних',dateDiff('second',p.latest_at,now())>900,'Дані застаріли','Дані надходять') AS data_status
FROM analytics.measurement_directory m LEFT JOIN
(SELECT msm_id,max(event_time) AS latest_at,count() AS measurements,uniqExact(prb_id) AS probes
FROM monitoring.ping_results FINAL WHERE event_time>=now()-INTERVAL 5 HOUR GROUP BY msm_id) p ON p.msm_id=m.measurement_id""")
    statements.append("""CREATE OR REPLACE VIEW analytics.probe_events_live AS
SELECT toTimeZone(event_time,'Europe/Kyiv') AS event_at,prb_id AS probe_id,event AS connection_event,event_id
FROM monitoring.probe_events FINAL WHERE event_time>=now()-INTERVAL 5 HOUR""")
    return statements

def main():
    from .retention_clickhouse import ch
    for statement in definitions():ch(statement)
    print('Installed analytics reporting views; IPv4/IPv6 explicit; no formula columns')

if __name__=='__main__':main()
