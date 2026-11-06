"""Pure anomaly rules. Network-wide events are suspicions, not proven outages."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from html import escape

@dataclass(frozen=True)
class Incident:
    kind: str
    scope: str
    timestamp: int
    details: dict
    severity: str = 'warning'

    @property
    def id(self):
        return sha256(f'{self.kind}:{self.scope}:{self.timestamp}:{self.details.get("msm_id", "")}'.encode()).hexdigest()

    @property
    def cooldown(self):
        return 1800 if self.kind in ('ASN_OUTAGE','REGION_OUTAGE') else 300

def detect(pings, baselines, statuses, probes, now):
    """pings must already be deduplicated. baseline keys: (probe, measurement, AF)."""
    groups=defaultdict(list)
    for p in pings:
        ts=int(p['timestamp'])
        if p.get('source_mode')=='stream' and now-900 <= ts <= now+30:
            groups[(int(p['prb_id']),int(p['msm_id']),int(p['af']))].append(p)
    incidents=[]; observed=set(); bad=set(); newest={}
    by_asn=defaultdict(set);bad_asn=defaultdict(set)
    observed_target=defaultdict(set);bad_target=defaultdict(set)
    for key,rows in groups.items():
        rows.sort(key=lambda x:(x['timestamp'],x['event_id']))
        probe,msm,af=key; latest=rows[-1]; observed.add(probe)
        observed_target[(msm,af)].add(probe)
        asn=(probes.get(probe) or {}).get('asn_v4' if af==4 else 'asn_v6')
        if asn:by_asn[(msm,af,asn)].add(probe)
        newest[probe]=max(newest.get(probe,0),int(latest['timestamp']))
        # Two distinct timestamps, both in a five-minute window. One RIPE sample
        # typically contains only three packets, so an isolated loss is noisy.
        distinct={int(r['timestamp']):r for r in rows if r['timestamp']>=now-600}
        recent=[distinct[t] for t in sorted(distinct)][-2:]
        if len(recent)<2 or latest['timestamp']<now-300:continue
        meta={'probe_id':probe,'asn':(probes.get(probe) or {}).get('asn_v4' if af==4 else 'asn_v6'),'msm_id':msm,'af':af,'samples':2}
        if all(r['loss_pct']>50 for r in recent):
            bad.add(probe)
            bad_target[(msm,af)].add(probe)
            if asn:bad_asn[(msm,af,asn)].add(probe)
            incidents.append(Incident('PACKET_LOSS',f'probe:{probe}',int(latest['timestamp']),dict(meta,value=latest['loss_pct']), 'critical' if latest['loss_pct']==100 else 'warning'))
        base=baselines.get(key)
        if base and base['samples']>=10 and base['value']>0 and all(r.get('rtt_avg') is not None and r['rtt_avg']>2*base['value']+10 for r in recent):
            incidents.append(Incident('HIGH_RTT',f'probe:{probe}',int(latest['timestamp']),dict(meta,value=latest['rtt_avg'],baseline=base['value'])))
    for probe,event in statuses.items():
        ts=int(event['timestamp']); status=str(event['event']).lower()
        if status not in ('disconnect','disconnected','down'):continue
        if now-ts<120:continue
        # A newer ping is evidence that a stale disconnect is no longer valid.
        if newest.get(probe,0)>ts:continue
        observed.add(probe);bad.add(probe)
        observed_target[(0,0)].add(probe);bad_target[(0,0)].add(probe)
        meta=probes.get(probe) or {}
        for asn in set(v for v in (meta.get('asn_v4'),meta.get('asn_v6')) if v):
            by_asn[(0,0,asn)].add(probe);bad_asn[(0,0,asn)].add(probe)
        incidents.append(Incident('PROBE_DOWN',f'probe:{probe}',ts,{'probe_id':probe,'asn':meta.get('asn_v4'),'duration_seconds':now-ts}))
    # Bucketing gives stable identity while the cooldown suppresses repeated windows.
    bucket=(now//300)*300
    for (msm,af,asn),members in by_asn.items():
        affected=members&bad_asn[(msm,af,asn)]
        if len(members)>=4 and len(affected)/len(members)>.34:
            incidents.append(Incident('ASN_OUTAGE',f'asn:{asn}',bucket,{'msm_id':msm,'af':af,'asn':asn,'affected':len(affected),'observed':len(members),'affected_probe_ids':sorted(affected),'percentage':round(100*len(affected)/len(members),1)},'critical'))
    for (msm,af),members in observed_target.items():
        affected=bad_target[(msm,af)]
        if len(members)>=20 and len(affected)/len(members)>.25:
            incidents.append(Incident('REGION_OUTAGE','region:UA',bucket,{'msm_id':msm,'af':af,'affected':len(affected),'observed':len(members),'affected_probe_ids':sorted(affected),'percentage':round(100*len(affected)/len(members),1)},'critical'))
    # Major suspicions go first; per-probe cooldown groups HIGH_RTT and LOSS.
    order={'REGION_OUTAGE':0,'ASN_OUTAGE':1,'PROBE_DOWN':2,'PACKET_LOSS':3,'HIGH_RTT':4}
    return sorted(incidents,key=lambda i:order[i.kind])

def format_message(incident):
    from zoneinfo import ZoneInfo
    d=incident.details
    titles={'HIGH_RTT':'🟠 Підвищена затримка','PACKET_LOSS':'🔴 Втрата пакетів','PROBE_DOWN':'🟠 Зонд відключений','ASN_OUTAGE':'🔴 Підозра на збій мережі провайдера','REGION_OUTAGE':'🔴 Підозра на масштабний збій в Україні'}
    titles.update(RECOVERED='🟢 Відновлення підтверджено',PIPELINE_STALE='🟠 Немає свіжих даних')
    lines=[f'<b>RIPE Atlas · {titles[incident.kind]}</b>']
    if d.get('probe_id'):lines.append(f'Зонд: <code>{d["probe_id"]}</code>')
    if d.get('asn'):lines.append(f'Провайдер: AS{d["asn"]}')
    if incident.kind=='RECOVERED':lines.append('Нові дані підтвердили відновлення після '+escape(d['original_kind'])+'.')
    elif incident.kind=='PIPELINE_STALE':lines.append('Понад 15 хв немає нових вимірювань. Це проблема доступності даних; стан мережі за ними невідомий.')
    elif incident.kind=='HIGH_RTT':lines.append(f'RTT: <b>{d["value"]:.1f} мс</b>; норма: {d["baseline"]:.1f} мс\nДва вимірювання вище 2 × норма + 10 мс.')
    elif incident.kind=='PACKET_LOSS':lines.append(f'Втрачено: <b>{d["value"]:.1f}%</b> пакетів.\nПідтверджено двома вимірюваннями за 10 хв; останнє — не старше 5 хв.')
    elif incident.kind=='PROBE_DOWN':lines.append('RIPE повідомив про відключення понад 2 хв тому; нових ping після нього немає.')
    else:lines.append(f'Проблемні зонди: <b>{d["affected"]}/{d["observed"]} ({d["percentage"]}%)</b> за 15 хв.\nЦе підозра за спостережуваною вибіркою, а не підтверджена аварія всього провайдера чи регіону.')
    if d.get('msm_id'):lines.append(f'Вимірювання: {d["msm_id"]}, IPv{d["af"]}. Проблема спостерігається на шляху до цілі цього вимірювання.')
    lines.append(datetime.fromtimestamp(incident.timestamp,timezone.utc).astimezone(ZoneInfo('Europe/Kyiv')).strftime('%d.%m.%Y %H:%M:%S · Київ'))
    lines.append('Інцидент: <code>'+escape(incident.id[:12])+'</code>')
    return '\n'.join(lines)
