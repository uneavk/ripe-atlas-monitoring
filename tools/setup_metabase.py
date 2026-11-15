"""Provision local Metabase dashboards through its API, using read-only data users."""
from pathlib import Path
import argparse,json,secrets,subprocess,sys,time,urllib.request,urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bi'))
from dashboards import build

class API:
    def __init__(self,url,private):self.url=url;self.session=None;self.private=private
    def call(self,path,data=None,method=None):
        headers={'Content-Type':'application/json'}
        if self.session:headers['X-Metabase-Session']=self.session
        request=urllib.request.Request(self.url+'/api'+path,data=json.dumps(data).encode() if data is not None else None,headers=headers,method=method)
        try:
            with urllib.request.urlopen(request,timeout=180) as response:raw=response.read().decode()
        except urllib.error.HTTPError as error:
            (self.private/'last_api_error.json').write_bytes(error.read())
            raise RuntimeError(f'Metabase HTTP {error.code} at {path}; diagnostic saved privately') from None
        return json.loads(raw) if raw else {}

def inspect(project,service):
    ids=subprocess.check_output(['docker','ps','-aq','--filter',f'label=com.docker.compose.project={project}','--filter',f'label=com.docker.compose.service={service}'],text=True).split()
    if len(ids)!=1:raise RuntimeError('Expected one '+service+' container for project '+project)
    return json.loads(subprocess.check_output(['docker','inspect',ids[0]],text=True,encoding='utf-8'))[0]

def container_python(container,code,payload):
    result=subprocess.run(['docker','exec','-i',container['Id'],'python','-c',code],input=json.dumps(payload),text=True,capture_output=True,encoding='utf-8')
    if result.returncode:raise RuntimeError('Database permission setup failed; no credentials printed')

def configure_readers(project,password):
    analytics=inspect(project,'analytics');alerts=inspect(project,'alerts')
    container_python(analytics,"""import sys,json
from app.retention_clickhouse import ch,quote
p=json.load(sys.stdin)['password']
ch('CREATE USER IF NOT EXISTS bi_reader IDENTIFIED WITH sha256_password BY '+quote(p))
ch('ALTER USER bi_reader IDENTIFIED WITH sha256_password BY '+quote(p))
ch('GRANT SELECT ON analytics.* TO bi_reader')
ch('GRANT SELECT ON monitoring.* TO bi_reader')""",{'password':password})
    container_python(alerts,"""import sys,json,os,psycopg
from psycopg import sql
p=json.load(sys.stdin)['password']
with psycopg.connect(os.environ['POSTGRES_DSN']) as c:
 if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='bi_reader'").fetchone():c.execute('CREATE ROLE bi_reader LOGIN')
 c.execute(sql.SQL('ALTER ROLE bi_reader PASSWORD {}').format(sql.Literal(p)))
 c.execute('GRANT USAGE ON SCHEMA public,reporting TO bi_reader')
 c.execute('GRANT SELECT ON ALL TABLES IN SCHEMA reporting TO bi_reader')
 c.execute('GRANT SELECT ON public.incident_history_metrics TO bi_reader')""",{'password':password})

def items(value):return value.get('data',[]) if isinstance(value,dict) else value

def layout(dashboard,cards):
    result=[];row=0;col=0;row_height=0
    for index,(spec,saved) in enumerate(cards):
        scalar=spec['display']=='scalar'
        full=spec['key'] in ('freshness','incident_log','probe_map')
        width=8 if scalar and dashboard['key']=='live' else 12 if scalar or not full else 24
        height=3 if scalar else 8 if spec['display']=='map' else 5 if spec['display']=='table' else 6
        if col+width>24:row+=row_height;col=0;row_height=0
        if full and col:row+=row_height;col=0;row_height=0
        mapping=[{'parameter_id':'measurement','card_id':saved['id'],'target':['variable',['template-tag','measurement']]}] if spec['measurement'] else []
        result.append({'id':-(index+1),'card_id':saved['id'],'row':row,'col':col,'size_x':width,'size_y':height,'parameter_mappings':mapping,'visualization_settings':{}})
        row_height=max(row_height,height)
        col+=width
        if col==24:row+=row_height;col=0;row_height=0
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project');args=parser.parse_args()
    env={}
    if (ROOT/'.env').exists():env=dict(line.split('=',1) for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines() if '=' in line and not line.startswith('#'))
    project=args.project or env.get('COMPOSE_PROJECT_NAME','ripe-monitoring')
    private=ROOT/'.secrets/metabase';private.mkdir(parents=True,exist_ok=True)
    config_path=private/'admin.json'
    if config_path.exists():config=json.loads(config_path.read_text(encoding='utf-8'))
    else:
        config={'email':'admin@ripe.local','password':secrets.token_urlsafe(30),'data_password':secrets.token_hex(24)}
        config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    container=inspect(project,'metabase');port=container['NetworkSettings']['Ports']['3000/tcp'][0]['HostPort']
    api=API('http://127.0.0.1:'+port,private)
    for attempt in range(180):
        try:
            health=api.call('/health')
            if health.get('status')=='ok':break
        except (OSError,RuntimeError):pass
        if attempt%10==0:print('Waiting for Metabase...',flush=True)
        time.sleep(2)
    else:raise RuntimeError('Metabase did not become ready')
    properties=api.call('/session/properties')
    if properties.get('setup-token'):
        api.call('/setup',{'token':properties['setup-token'],'user':{'first_name':'RIPE','last_name':'Admin','email':config['email'],'password':config['password']},'prefs':{'site_name':'RIPE Atlas · Україна','allow_tracking':False}})
    api.session=api.call('/session',{'username':config['email'],'password':config['password']})['id']
    api.call('/setting/report-timezone',{'value':'Europe/Kyiv'},'PUT')
    configure_readers(project,config['data_password'])
    alerts=inspect(project,'alerts');aenv=dict(v.split('=',1) for v in alerts['Config']['Env'] if '=' in v)
    from urllib.parse import urlparse
    pgname=urlparse(aenv['POSTGRES_DSN']).path.lstrip('/')
    databases={}
    existing=items(api.call('/database'))
    for key,name,engine,details in [
        ('ch','RIPE · ClickHouse analytics','clickhouse',{'host':'clickhouse','port':8123,'dbname':'analytics','user':'bi_reader','password':config['data_password'],'ssl':False}),
        ('pg','RIPE · PostgreSQL reporting','postgres',{'host':'postgres','port':5432,'dbname':pgname,'user':'bi_reader','password':config['data_password'],'ssl':False})]:
        payload={'name':name,'engine':engine,'details':details,'is_full_sync':False,'auto_run_queries':True}
        old=next((d for d in existing if d['name']==name),None)
        saved=api.call('/database/'+str(old['id']),payload,'PUT') if old else api.call('/database',payload)
        databases[key]=saved['id']
    collection_name='RIPE Atlas · Лабораторна СТП'
    collections=items(api.call('/collection'))
    collection=next((c for c in collections if c.get('name')==collection_name),None) or api.call('/collection',{'name':collection_name,'description':'Відтворювана аналітика реальних вимірювань України'})
    existing_cards=items(api.call('/card?f=all'));existing_dashboards=items(api.call('/dashboard'))
    manifest={'url':api.url,'collection_id':collection['id'],'dashboards':[]}
    specifications=build()
    for dashboard in specifications:
        saved_cards=[]
        for spec in dashboard['cards']:
            tags={'measurement':{'id':'measurement','name':'measurement','display-name':'Вимірювання','type':'number','default':1001,'required':True}} if spec['measurement'] else {}
            query={'database':databases[spec['source']],'type':'native','native':{'query':spec['sql'],'template-tags':tags}}
            payload={'name':spec['name'],'description':spec['description'],'display':spec['display'],'dataset_query':query,'visualization_settings':spec['settings'],'collection_id':collection['id']}
            old=next((c for c in existing_cards if c.get('collection_id')==collection['id'] and c['name']==spec['name']),None)
            saved=api.call('/card/'+str(old['id']),payload,'PUT') if old else api.call('/card',payload)
            saved_cards.append((spec,saved))
            print('Question ready:',spec['key'],flush=True)
        old=next((d for d in existing_dashboards if d.get('collection_id')==collection['id'] and d['name']==dashboard['name']),None)
        saved=old or api.call('/dashboard',{'name':dashboard['name'],'description':dashboard['description'],'collection_id':collection['id']})
        parameters=[{'id':'measurement','name':'Вимірювання · 1001/2001/1004/2004','slug':'measurement','type':'number/=','default':['1001']}] if any(s['measurement'] for s in dashboard['cards']) else []
        api.call('/dashboard/'+str(saved['id']),{'name':dashboard['name'],'description':dashboard['description'],'parameters':parameters,'dashcards':layout(dashboard,saved_cards)},'PUT')
        manifest['dashboards'].append({'key':dashboard['key'],'id':saved['id'],'name':dashboard['name'],'url':api.url+'/dashboard/'+str(saved['id'])+'#refresh=60','cards':[{'id':c['id'],'key':s['key']} for s,c in saved_cards]})
    (private/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'bi/dashboard_spec.json').write_text(json.dumps(specifications,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Metabase ready. Credentials are local in .secrets/metabase/admin.json; do not publish this file.')
    for d in manifest['dashboards']:print(d['name'],d['url'])

if __name__=='__main__':main()
