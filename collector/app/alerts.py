"""Independent incident detection and durable Telegram delivery; no Kafka ingestion dependency."""
from __future__ import annotations
import argparse,json,logging,os,signal,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
import requests,psycopg
from psycopg.types.json import Jsonb
from .alert_rules import detect,format_message,Incident
from .incident_state import SCHEMA,key,recovery_events
from .pipeline_errors import ErrorReader,SCHEMA as ERROR_SCHEMA
from .telegram_subscriptions import poll,dispatch

log=logging.getLogger('alerts');running=True
def stop(*args):
    global running
    running=False

def credentials():
    path=Path(os.getenv('TELEGRAM_CONFIG_FILE','/run/telegram/config.json'))
    if path.is_file():return json.loads(path.read_text(encoding='utf-8-sig'))
    return {'token':os.getenv('TELEGRAM_BOT_TOKEN',''),'chat_id':os.getenv('TELEGRAM_CHAT_ID','')}

def ch_query(sql):
    response=requests.post(os.getenv('CLICKHOUSE_URL','http://clickhouse:8123/'),data=(sql+' FORMAT JSONEachRow').encode(),auth=(os.environ['CLICKHOUSE_USER'],os.environ['CLICKHOUSE_PASSWORD']),timeout=(5,30))
    response.raise_for_status()
    return [json.loads(line) for line in response.text.splitlines() if line]

def snapshot(now,conn):
    # FINAL removes duplicates before detection, including replayed historical records.
    pings=ch_query(f"SELECT event_id,prb_id,msm_id,af,toUnixTimestamp(event_time) AS timestamp,loss_pct,rtt_avg,source_mode FROM monitoring.ping_results FINAL WHERE event_time >= fromUnixTimestamp({now-900}) AND event_time <= fromUnixTimestamp({now+30}) AND source_mode='stream' ORDER BY event_time")
    # Raw retention is five hours: use complete hourly sufficient statistics
    # for the older history, and raw samples for the uncompleted boundary hour.
    boundary=((now-60)//3600)*3600
    history=ch_query(f'SELECT probe_id,msm_id,af,sum(normal_rtt_count) AS samples,sum(normal_rtt_sum) AS total FROM monitoring.hourly_metrics FINAL WHERE hour_start>=toDateTime({((now-86400)//3600)*3600}) AND hour_start<toDateTime({boundary}) GROUP BY probe_id,msm_id,af')
    totals={(r['probe_id'],r['msm_id'],r['af']):[int(r['samples']),float(r['total'])] for r in history}
    rows=ch_query(f"SELECT prb_id,msm_id,af,countIf(rtt_avg>0 AND loss_pct<=50) AS samples,sumIf(rtt_avg,rtt_avg>0 AND loss_pct<=50) AS total FROM monitoring.ping_results FINAL WHERE event_time >= fromUnixTimestamp({boundary}) AND event_time < fromUnixTimestamp({now-60}) GROUP BY prb_id,msm_id,af")
    for r in rows:
        key=(r['prb_id'],r['msm_id'],r['af']);count,total=totals.get(key,[0,0]);totals[key]=[count+int(r['samples']),total+float(r.get('total') or 0)]
    baselines={key:{'samples':count,'value':total/count} for key,(count,total) in totals.items() if count>=10}
    rows=ch_query(f"SELECT prb_id,argMax(event,event_time) AS event,max(toUnixTimestamp(event_time)) AS timestamp FROM monitoring.probe_events FINAL WHERE event_time <= fromUnixTimestamp({now+30}) GROUP BY prb_id")
    for r in rows:
        conn.execute('INSERT INTO probe_connectivity_state VALUES (%s,%s,%s) ON CONFLICT(probe_id) DO UPDATE SET event=excluded.event,event_timestamp=excluded.event_timestamp WHERE excluded.event_timestamp>probe_connectivity_state.event_timestamp',(r['prb_id'],r['event'],r['timestamp']))
    statuses={r[0]:dict(event=r[1],timestamp=r[2]) for r in conn.execute('SELECT probe_id,event,event_timestamp FROM probe_connectivity_state')}
    probes={int(r['probe_id']):{'asn_v4':r['asn_v4'],'asn_v6':r['asn_v6']} for r in ch_query('SELECT probe_id,asn_v4,asn_v6 FROM monitoring.probe_directory FINAL')}
    incidents=detect(pings,baselines,statuses,probes,now)
    freshness=ch_query('SELECT msm_id,max(toUnixTimestamp(event_time)) AS latest FROM monitoring.ping_results FINAL GROUP BY msm_id')
    latest={r['msm_id']:int(r['latest']) for r in freshness}
    for msm in (1001,2001,1004,2004):
        if latest.get(msm,0)<now-900:
            incidents.append(Incident('PIPELINE_STALE',f'measurement:{msm}',now//900*900,{'msm_id':msm,'af':4 if msm<2000 else 6}))
    recoveries=list(recovery_events(conn,pings,statuses,incidents,now))
    # Fresh data is explicit evidence of pipeline recovery.
    for k,details in conn.execute("SELECT episode_key,details FROM incident_episodes WHERE kind='PIPELINE_STALE' AND resolved_at IS NULL"):
        if latest.get(details['msm_id'],0)>=now-300:
            recoveries.append(Incident('RECOVERED',f"measurement:{details['msm_id']}",now,dict(details,original_kind='PIPELINE_STALE',episode_key=k),'info'))
    return incidents+recoveries

def record(conn,incident,enabled):
    with conn.transaction():
        episode_key=key(incident)
        if incident.kind=='RECOVERED':
            episode_key=incident.details['episode_key']
            closed=conn.execute('UPDATE incident_episodes SET resolved_at=to_timestamp(%s) WHERE episode_key=%s AND resolved_at IS NULL RETURNING opening_id',(incident.timestamp,episode_key)).fetchone()
            if not closed:return
            conn.execute('UPDATE monitoring_incidents SET resolved_at=to_timestamp(%s) WHERE episode_id=%s',(incident.timestamp,closed[0]))
        else:
            previous=conn.execute('SELECT severity FROM incident_episodes WHERE episode_key=%s AND resolved_at IS NULL FOR UPDATE',(episode_key,)).fetchone()
            if previous:
                conn.execute('UPDATE incident_episodes SET last_seen_at=greatest(last_seen_at,to_timestamp(%s)),details=%s,severity=%s WHERE episode_key=%s',(incident.timestamp,Jsonb(incident.details),incident.severity,episode_key))
                if previous[0]==incident.severity or incident.severity!='critical':return
        row=conn.execute('INSERT INTO monitoring_incidents(incident_id,kind,scope,event_time,severity,details,notification_status) VALUES (%s,%s,%s,to_timestamp(%s),%s,%s,%s) ON CONFLICT DO NOTHING RETURNING incident_id',(incident.id,incident.kind,incident.scope,incident.timestamp,incident.severity,Jsonb(incident.details),'checking')).fetchone()
        if not row:return
        if incident.kind!='RECOVERED':
            conn.execute('INSERT INTO incident_episodes VALUES (%s,%s,%s,to_timestamp(%s),to_timestamp(%s),NULL,%s,%s,%s) ON CONFLICT(episode_key) DO UPDATE SET opened_at=CASE WHEN incident_episodes.resolved_at IS NULL THEN incident_episodes.opened_at ELSE excluded.opened_at END,opening_id=CASE WHEN incident_episodes.resolved_at IS NULL THEN incident_episodes.opening_id ELSE excluded.opening_id END,last_seen_at=excluded.last_seen_at,resolved_at=NULL,severity=excluded.severity,details=excluded.details',(episode_key,incident.kind,incident.scope,incident.timestamp,incident.timestamp,incident.severity,Jsonb(incident.details),incident.id))
            conn.execute('UPDATE monitoring_incidents SET episode_id=(SELECT opening_id FROM incident_episodes WHERE episode_key=%s) WHERE incident_id=%s',(episode_key,incident.id))
        cooldown_scope=episode_key+':'+incident.severity+(':'+str(incident.timestamp) if incident.kind=='RECOVERED' else '')
        conn.execute('INSERT INTO notification_cooldowns(scope) VALUES (%s) ON CONFLICT DO NOTHING',(cooldown_scope,))
        last=conn.execute('SELECT last_queued_at FROM notification_cooldowns WHERE scope=%s FOR UPDATE',(cooldown_scope,)).fetchone()[0]
        now=datetime.now(timezone.utc)
        recent=conn.execute("SELECT count(*) FROM telegram_outbox WHERE created_at>now()-interval '1 minute'").fetchone()[0]
        reason='queued'
        if not enabled:reason='delivery_not_configured'
        elif (now-last).total_seconds()<incident.cooldown:reason='cooldown'
        # Durable queue retains every episode; Telegram 429 controls delivery.
        if reason=='queued':
            outbox_id=conn.execute('INSERT INTO telegram_outbox(incident_id,message) VALUES (%s,%s) RETURNING id',(incident.id,format_message(incident))).fetchone()[0]
            conn.execute('INSERT INTO telegram_deliveries(outbox_id,chat_id) SELECT %s,chat_id FROM telegram_subscribers WHERE active ON CONFLICT DO NOTHING',(outbox_id,))
            conn.execute('UPDATE notification_cooldowns SET last_queued_at=now() WHERE scope=%s',(cooldown_scope,))
        conn.execute('UPDATE monitoring_incidents SET notification_status=%s WHERE incident_id=%s',(reason,incident.id))
        log.info('incident kind=%s id=%s notification=%s',incident.kind,incident.id[:12],reason)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    interval=max(5,int(os.getenv('ALERT_POLL_SECONDS','10')))
    log.info('alerts_started interval=%s seconds',interval)
    error_reader=None
    while running:
        try:
            config=credentials();enabled=False
            with psycopg.connect(os.environ['POSTGRES_DSN'],autocommit=True) as conn:
                conn.execute(SCHEMA)
                conn.execute(ERROR_SCHEMA)
                try:
                    if error_reader is None:error_reader=ErrorReader()
                    error_reader.poll(conn)
                except Exception as error:log.error('diagnostics_failed type=%s',type(error).__name__)
                try:poll(conn,config)
                except Exception as error:log.error('telegram_poll_failed type=%s',type(error).__name__)
                enabled=bool(config.get('token') and conn.execute('SELECT EXISTS(SELECT 1 FROM telegram_subscribers WHERE active)').fetchone()[0])
                try:
                    for incident in snapshot(int(time.time()),conn):record(conn,incident,enabled)
                except Exception as error:
                    # Existing outbox delivery continues even if ClickHouse is down.
                    log.error('detection_failed type=%s',type(error).__name__)
                dispatch(conn,config)
            log.info('alerts_cycle_ok telegram_configured=%s',enabled)
        except Exception as error:
            # Exception text can contain connection passwords or bot request URLs.
            log.error('alerts_cycle_failed type=%s',type(error).__name__)
        if args.once:break
        for _ in range(interval):
            if not running:break
            time.sleep(1)

if __name__=='__main__':main()
