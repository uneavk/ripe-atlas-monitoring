"""ClickHouse-only ingestion/rollups. A Docker-volume journal makes retries idempotent."""
from __future__ import annotations
import json,logging,os,threading,time,math,re
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from decimal import Decimal
import requests
import queue
from .models import validate_minimum

UTC=timezone.utc;KYIV=ZoneInfo('Europe/Kyiv');LOCK=threading.RLock()
log=logging.getLogger('analytics')
FIELDS=['samples','sent','received','rtt_sum','rtt_count','rtt_min','rtt_max','normal_rtt_sum','normal_rtt_count','loss_samples','full_loss_samples','connects','disconnects']
KEYS=['hour_start','probe_id','msm_id','af','asn']
FLOATS={'rtt_sum','normal_rtt_sum'}
def encode(x):
    if isinstance(x,Decimal):return int(x) if x==x.to_integral_value() else float(x)
    return x.isoformat()
def ch(sql,rows=None):
    body=''
    if rows is not None:
        if not rows:return []
        sql+=' FORMAT JSONEachRow'
        body='\n'.join(json.dumps(r,default=encode,allow_nan=False) for r in rows)
    r=requests.post(os.getenv('CLICKHOUSE_URL','http://clickhouse:8123/'),params={'query':sql,'date_time_input_format':'best_effort'},data=body.encode(),auth=(os.environ['CLICKHOUSE_USER'],os.environ['CLICKHOUSE_PASSWORD']),timeout=(5,120))
    if not r.ok:raise RuntimeError('ClickHouse '+str(r.status_code)+': '+r.text[:300])
    return [json.loads(line) for line in r.text.splitlines() if line]
def quote(s):return "'"+str(s).replace('\\','\\\\').replace("'","\\'")+"'"
def instant(value):
    if isinstance(value,(int,float)):return datetime.fromtimestamp(value,UTC)
    if isinstance(value,datetime):return value.astimezone(UTC)
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    return (d.replace(tzinfo=UTC) if d.tzinfo is None else d).astimezone(UTC)
def finalized_day(now):
    local=now.astimezone(KYIV)
    return local.date()-timedelta(days=1 if local.hour>=4 else 2)
def seconds_to_next_run(now):
    hour=now.replace(minute=0,second=0,microsecond=0)+timedelta(hours=1)
    local=now.astimezone(KYIV);four=local.replace(hour=4,minute=0,second=0,microsecond=0)
    if four<=local:four+=timedelta(days=1)
    return max(.01,min(15,(hour-now).total_seconds(),(four.astimezone(UTC)-now).total_seconds()))
def values(row,kind):
    ts=instant(row['event_time']);probe=int(row['prb_id'])
    if probe<=0 or not re.fullmatch(r'[A-Za-z0-9:_-]{1,128}',str(row.get('event_id',''))):raise ValueError('Invalid identity')
    v={f:0 for f in FIELDS};v['rtt_min']=v['rtt_max']=None
    if kind=='ping_results':
        check=dict(row,event_type='ping_result',timestamp=int(ts.timestamp()))
        check.setdefault('loss_pct',100*(row['sent']-row['rcvd'])/row['sent'] if row.get('sent') else -1)
        valid,reason=validate_minimum(check)
        if not valid:raise ValueError(reason)
        sent=int(row['sent']);received=int(row['rcvd']);rtt=row.get('rtt_avg')
        if sent<=0 or not 0<=received<=sent:raise ValueError('Invalid packet counts')
        if rtt is not None and (not math.isfinite(float(rtt)) or not 0<=rtt<10000):raise ValueError('Invalid RTT')
        loss=100*(sent-received)/sent
        v.update(samples=1,sent=sent,received=received,rtt_sum=float(rtt or 0),rtt_count=int(rtt is not None),rtt_min=row.get('rtt_min'),rtt_max=row.get('rtt_max'),normal_rtt_sum=float(rtt or 0) if loss<=50 else 0,normal_rtt_count=int(rtt is not None and rtt>0 and loss<=50),loss_samples=int(loss>50),full_loss_samples=int(received==0))
        msm=int(row['msm_id']);af=int(row['af'])
        if af not in (4,6):raise ValueError('Invalid IP version')
    else:
        event=str(row['event']).lower();v['connects']=int(event in ('connect','connected'));v['disconnects']=int(event in ('disconnect','disconnected','down'));msm=af=0
    return ts,probe,msm,af,v
def hour_key(row):return (instant(row['hour_start']).isoformat(),*(int(row[k]) for k in KEYS[1:]))
def combine(previous,delta):
    result={}
    for f in FIELDS:
        a=previous.get(f);b=delta[f]
        if f in ('rtt_min','rtt_max'):
            vals=[x for x in (a,b) if x is not None]
            result[f]=(min(vals) if f=='rtt_min' else max(vals)) if vals else None
        else:result[f]=(float(a or 0) if f in FLOATS else int(a or 0))+b
    return result

class Store:
    def __init__(self,query=ch,state=None):
        self.query=query;self.path=Path(state or os.getenv('ANALYTICS_STATE_DIR','/app/state'))/'pending-ingestion.json'
        self.path.parent.mkdir(parents=True,exist_ok=True)
    def recover(self,now=None):
        if not self.path.exists():return
        doc=json.loads(self.path.read_text());now=now or datetime.now(UTC)
        # Fixed versions and full snapshots make replay safe even if a previous
        # HTTP response was lost after ClickHouse committed the insertion.
        if doc.get('hours'):self.query('INSERT INTO monitoring.hourly_metrics',doc['hours'])
        rows=doc.get('rows',[])
        if doc['kind']!='probe_directory':rows=[r for r in rows if instant(r['event_time'])>=now-timedelta(hours=5)]
        if rows:self.query('INSERT INTO monitoring.'+doc['kind'],rows)
        self.path.unlink()
    def save(self,doc):
        temporary=self.path.with_suffix('.tmp')
        with temporary.open('w',encoding='utf-8') as out:
            json.dump(doc,out,default=encode,allow_nan=False);out.flush();os.fsync(out.fileno())
        os.replace(temporary,self.path)
    def ingest(self,rows,kind,now=None):
        now=now or datetime.now(UTC);self.recover(now);version=time.time_ns()
        if kind=='probe_directory':
            normalized=[]
            for p in rows:
                probe=int(p.get('probe_id') or p.get('prb_id') or 0)
                if probe<=0 or p.get('country')!='UA':raise ValueError('Invalid probe metadata')
                normalized.append({'probe_id':probe,'country':'UA','asn_v4':int(p.get('asn_v4') or 0),'asn_v6':int(p.get('asn_v6') or 0),'latitude':p.get('latitude'),'longitude':p.get('longitude'),'status':str(p.get('status') or ''),'version':version})
            self.save({'kind':kind,'rows':normalized,'hours':[]});self.recover(now)
            return {'accepted':len(normalized)}
        parsed={}
        ignored=0
        for row in rows:
            data=values(row,kind);ts=data[0]
            if ts>now+timedelta(seconds=30):raise ValueError('Future event')
            if ts<now-timedelta(hours=5):ignored+=1;continue
            parsed[row['event_id']]=(row,data)
        if not parsed:return {'accepted':0,'ignored_older_than_5h':ignored}
        known={r['event_id'] for r in self.query('SELECT event_id FROM monitoring.'+kind+' FINAL WHERE event_id IN ('+','.join(quote(k) for k in parsed)+') FORMAT JSONEachRow')}
        fresh=[v for k,v in parsed.items() if k not in known]
        if not fresh:return {'accepted':0,'ignored_older_than_5h':ignored}
        directory={int(r['probe_id']):r for r in self.query('SELECT probe_id,asn_v4,asn_v6 FROM monitoring.probe_directory FINAL FORMAT JSONEachRow')}
        cutoff=int((now-timedelta(hours=6)).timestamp())
        old={hour_key(r):r for r in self.query(f'SELECT * FROM monitoring.hourly_metrics FINAL WHERE hour_start>=toDateTime({cutoff}) FORMAT JSONEachRow')}
        targets={};raw=[]
        for row,(ts,probe,msm,af,delta) in fresh:
            # Metadata and measurements arrive on separate Kafka topics. Retry
            # while the directory catches up instead of silently inventing ASN 0.
            if probe not in directory:raise RuntimeError('Probe directory not ready')
            asn=int((directory.get(probe) or {}).get('asn_v6' if af==6 else 'asn_v4') or 0)
            hour=ts.replace(minute=0,second=0,microsecond=0).isoformat();key=(hour,probe,msm,af,asn)
            previous=targets.get(key) or old.get(key) or {}
            targets[key]=dict(zip(KEYS,key),**combine(previous,delta),version=version)
            raw.append(row)
        self.save({'kind':kind,'rows':raw,'hours':list(targets.values())});self.recover(now)
        return {'accepted':len(raw),'ignored_older_than_5h':ignored}
    def control(self,key,value):self.query('INSERT INTO monitoring.retention_runs',[{'key':key,'value':str(value),'version':time.time_ns()}])
    def maintenance(self,now=None):
        now=now or datetime.now(UTC);self.recover(now);day_limit=finalized_day(now)
        controls={r['key']:r['value'] for r in self.query('SELECT key,value FROM monitoring.retention_runs FINAL FORMAT JSONEachRow')}
        candidates=self.query("SELECT toDate(hour_start,'Europe/Kyiv') AS day,max(version) AS revision FROM monitoring.hourly_metrics FINAL WHERE toDate(hour_start,'Europe/Kyiv')<="+quote(day_limit)+' GROUP BY day FORMAT JSONEachRow')
        for item in candidates:
            day=item['day'];revision=int(item['revision']);key='day:'+day
            if int(controls.get(key,'0'))>=revision:continue
            aggregates=','.join(('min' if f=='rtt_min' else 'max' if f=='rtt_max' else 'sum')+'('+f+') AS '+f for f in FIELDS)
            data=self.query("SELECT toDate(hour_start,'Europe/Kyiv') AS day,probe_id,msm_id,af,asn,"+aggregates+" FROM monitoring.hourly_metrics FINAL WHERE toDate(hour_start,'Europe/Kyiv')="+quote(day)+' GROUP BY day,probe_id,msm_id,af,asn FORMAT JSONEachRow')
            version=time.time_ns()
            self.query('INSERT INTO monitoring.daily_metrics',[dict(r,version=version) for r in data])
            self.control(key,revision)
        for table,column,cutoff in [('ping_results','event_time',now-timedelta(hours=5)),('probe_events','event_time',now-timedelta(hours=5)),('hourly_metrics','hour_start',now-timedelta(days=2))]:
            condition=column+'<toDateTime('+str(int(cutoff.timestamp()))+")"
            if table=='hourly_metrics':condition+=" AND toDate(hour_start,'Europe/Kyiv')<="+quote(day_limit)
            found=self.query(f'SELECT count() AS n FROM (SELECT 1 FROM monitoring.{table} WHERE {condition} LIMIT 1) FORMAT JSONEachRow')
            if found and int(found[0]['n']):self.query(f'ALTER TABLE monitoring.{table} DELETE WHERE {condition} SETTINGS mutations_sync=1')
        self.control('last_maintenance',now.isoformat())

STORE=None
INGEST_QUEUE=queue.Queue(maxsize=2000)

def ingestion_worker():
    """Coalesce concurrent HTTP deliveries, acknowledging only durable batches."""
    while True:
        pending=[INGEST_QUEUE.get()]
        deadline=time.monotonic()+.05
        while len(pending)<500:
            try:pending.append(INGEST_QUEUE.get(timeout=max(.001,deadline-time.monotonic())))
            except queue.Empty:break
            if time.monotonic()>=deadline:break
        for kind in ('probe_directory','ping_results','probe_events'):
            group=[r for r in pending if r['kind']==kind]
            if not group:continue
            try:
                with LOCK:
                    STORE.ingest([row for r in group for row in r['rows']],kind)
                    STORE.maintenance()
                for r in group:r['code']=200
            except (ValueError,KeyError,TypeError):
                # Isolate malformed metadata instead of rejecting its neighbours.
                for r in group:
                    try:
                        with LOCK:STORE.ingest(r['rows'],kind);STORE.maintenance()
                        r['code']=200
                    except (ValueError,KeyError,TypeError):r['code']=400
                    except Exception:r['code']=503
            except Exception as error:
                log.error('ingest_batch_failed type=%s',type(error).__name__)
                for r in group:r['code']=503
            finally:
                for r in group:r['done'].set();INGEST_QUEUE.task_done()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path!='/health':self.send_error(404);return
        try:
            rows=ch("SELECT value FROM monitoring.retention_runs FINAL WHERE key='last_maintenance' FORMAT JSONEachRow")
            if not rows or (datetime.now(UTC)-instant(rows[0]['value'])).total_seconds()>90:raise RuntimeError('Maintenance overdue')
        except Exception:self.send_error(503);return
        self.send_response(200);self.end_headers();self.wfile.write(b'ClickHouse only: OK')
    def do_POST(self):
        kind=self.path.rsplit('/',1)[-1]
        if kind not in ('ping_results','probe_events','probe_directory'):self.send_error(404);return
        try:
            length=int(self.headers.get('Content-Length',0))
            if not 0<length<=10_000_000:raise ValueError('Invalid size')
            rows=[json.loads(s) for s in self.rfile.read(length).decode().splitlines() if s]
            if not rows or any(not isinstance(r,dict) for r in rows):raise ValueError('Invalid rows')
            if kind!='probe_directory':
                for row in rows:values(row,kind)
            request={'kind':kind,'rows':rows,'done':threading.Event(),'code':503}
            INGEST_QUEUE.put(request,timeout=5)
            if not request['done'].wait(110):raise RuntimeError('Ingestion pending; retry is safe')
            if request['code']!=200:self.send_error(request['code']);return
            self.send_response(200);self.end_headers();self.wfile.write(b'{"acknowledged":true}')
        except (ValueError,KeyError,TypeError):self.send_error(400,'Invalid event')
        except Exception as error:log.error('ingest_failed type=%s',type(error).__name__);self.send_error(503,'Retry: ClickHouse ingestion not acknowledged')
def worker():
    while True:
        try:
            with LOCK:STORE.maintenance()
        except Exception as error:log.error('maintenance_failed type=%s',type(error).__name__)
        time.sleep(seconds_to_next_run(datetime.now(UTC)))
def main():
    global STORE
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    STORE=Store();threading.Thread(target=worker,daemon=True).start()
    threading.Thread(target=ingestion_worker,daemon=True).start()
    log.info('clickhouse_only_started raw=5h hourly=48h daily=permanent')
    ThreadingHTTPServer(('0.0.0.0',8082),Handler).serve_forever()
if __name__=='__main__':main()
