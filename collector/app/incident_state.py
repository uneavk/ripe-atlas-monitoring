"""Durable episodes: silence or old data never means recovery."""
from .alert_rules import Incident

SCHEMA="""
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
"""

def key(i):
    return f'{i.kind}:{i.scope}:{i.details.get("msm_id",0)}:{i.details.get("af",0)}'

def recovered(episode, pings, statuses, now):
    kind,scope,details,last_seen=episode
    if kind=='PROBE_DOWN':
        probe=details['probe_id'];event=statuses.get(probe,{})
        return (event.get('timestamp',0)>last_seen and event.get('event','').lower() in ('connect','connected')) or any(p['prb_id']==probe and p['timestamp']>last_seen for p in pings)
    members=details.get('affected_probe_ids') or [details.get('probe_id')]
    if not members or None in members:return False
    for probe in members:
        rows={p['timestamp']:p for p in pings if p['prb_id']==probe and p['timestamp']>last_seen and now-600<=p['timestamp']<=now+30 and (not details.get('msm_id') or (p['msm_id']==details['msm_id'] and p['af']==details['af']))}
        recent=[rows[t] for t in sorted(rows)][-2:]
        if len(recent)<2 or recent[-1]['timestamp']<now-300:return False
        if kind=='HIGH_RTT':
            if not all(p.get('rtt_avg') is not None and p['rtt_avg']<=2*details['baseline']+10 and p['loss_pct']<=50 for p in recent):return False
        elif not all(p['loss_pct']<=50 for p in recent):return False
    return True

def recovery_events(conn,pings,statuses,current,now):
    active={key(i) for i in current}
    rows=conn.execute('SELECT episode_key,kind,scope,details,extract(epoch FROM last_seen_at)::bigint FROM incident_episodes WHERE resolved_at IS NULL').fetchall()
    for episode_key,kind,scope,details,last_seen in rows:
        if episode_key in active or not recovered((kind,scope,details,last_seen),pings,statuses,now):continue
        yield Incident('RECOVERED',scope,now,dict(details,original_kind=kind,episode_key=episode_key), 'info')
