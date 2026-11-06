"""Install the RIPE processing branches in the existing local NiFi."""
from api_client import api,root
import atexit,time
types=api('/flow/processor-types')['processorTypes']
flow=api('/flow/process-groups/'+root)['processGroupFlow']['flow']
existing={x['component']['name']:x for x in flow['processors']}
managed={'RIPE invalid events','Describe rejected events'}|{'Read '+t for t in ('ripe.raw','ripe.probes','ripe.probe_status')}|{'Validate and transform '+t for t in ('ripe.raw','ripe.probes','ripe.probe_status')}|{'Store '+t for t in ('ping_results','probe_directory','probe_events')}
previously_running=[p for name,p in existing.items() if name in managed and p['component']['state']=='RUNNING']
def restore_running():
    for p in previously_running:
        try:
            current=api('/processors/'+p['id'])
            if current['component']['state']=='STOPPED' and not current['component'].get('validationErrors'):
                api('/processors/'+p['id']+'/run-status',{'revision':current['revision'],'state':'RUNNING'},'PUT')
        except Exception:pass
atexit.register(restore_running)
for p in previously_running:
    api('/processors/'+p['id']+'/run-status',{'revision':p['revision'],'state':'STOPPED'},'PUT')
for attempt in range(120):
    if all(api('/processors/'+p['id'])['status']['aggregateSnapshot']['activeThreadCount']==0 for p in previously_running):break
    time.sleep(.5)
else:raise RuntimeError('Existing NiFi tasks did not finish; configuration left intact')
def processor(name,kind,props,x,y,terminate=()):
    print('Configuring',name,flush=True)
    match=next(t for t in types if t['type'].endswith('.'+kind))
    ent=existing.get(name) or api('/process-groups/'+root+'/processors',{'revision':{'version':0},'component':{'name':name,'type':match['type'],'bundle':match['bundle'],'position':{'x':x,'y':y}}})
    ent=api('/processors/'+ent['id'])
    ent=api('/processors/'+ent['id'],{'revision':ent['revision'],'component':{'id':ent['id'],'position':{'x':x,'y':y},'config':{'properties':props,'autoTerminatedRelationships':list(terminate),'schedulingPeriod':'0 sec','concurrentlySchedulableTaskCount':16 if kind=='InvokeHTTP' else 1}}},'PUT')
    return ent
def connect(a,b,rels):
    for rel in rels:
        if any(c['component']['source']['id']==a['id'] and c['component']['destination']['id']==b['id'] and rel in c['component']['selectedRelationships'] for c in flow['connections']): continue
        api('/process-groups/'+root+'/connections',{'revision':{'version':0},'component':{'source':{'id':a['id'],'groupId':root,'type':'PROCESSOR'},'destination':{'id':b['id'],'groupId':root,'type':'PROCESSOR'},'selectedRelationships':[rel],'backPressureObjectThreshold':10000,'backPressureDataSizeThreshold':'1 GB'}})
prefix='''import groovy.json.*
import org.apache.nifi.processor.io.StreamCallback
def f=session.get(); if(!f)return
def text=''
try {
session.read(f,{ input -> text=input.getText('UTF-8') } as org.apache.nifi.processor.io.InputStreamCallback)
def e=new JsonSlurper().parseText(text)
'''
suffix='''
f=session.write(f,{input,out -> out.write(output.getBytes('UTF-8'))} as StreamCallback)
session.transfer(f,REL_SUCCESS)
} catch(Throwable ex) {
f=session.putAttribute(f,'ripe.error',ex.message ?: 'INVALID_EVENT')
def rejected=JsonOutput.toJson([schema_version:1,stage:'nifi_validation',reason:ex.message ?: 'INVALID_EVENT',payload:text])
f=session.write(f,{input,out -> out.write(rejected.getBytes('UTF-8'))} as StreamCallback)
session.transfer(f,REL_FAILURE)
}
'''
ping='''assert (e.prb_id instanceof Number && e.prb_id>0) : 'INVALID_PROBE_ID';
assert (e.timestamp instanceof Number && e.timestamp>0) : 'INVALID_TIMESTAMP';
assert (e.msm_id instanceof Number && e.sent>0 && e.rcvd>=0 && e.rcvd<=e.sent) : 'INVALID_PACKET_COUNTS';
assert (e.af in [4,6]) : 'INVALID_AF';
assert (e.loss_pct>=0 && e.loss_pct<=100 && Math.abs(e.loss_pct-100.0*(e.sent-e.rcvd)/e.sent)<0.001) : 'INVALID_LOSS';
assert ([e.rtt_min,e.rtt_avg,e.rtt_max].every{it==null || (it instanceof Number && Double.isFinite(it.doubleValue()) && it>=0 && it<10000)}) : 'INVALID_RTT';
assert (e.rcvd==0 ? [e.rtt_min,e.rtt_avg,e.rtt_max].every{it==null} : [e.rtt_min,e.rtt_avg,e.rtt_max].every{it!=null}) : 'INCONSISTENT_RTT';
assert (e.rtt_avg==null || (e.rtt_min<=e.rtt_avg && e.rtt_avg<=e.rtt_max)) : 'INCONSISTENT_RTT_ORDER';
def row=[:]; ['event_id','msm_id','prb_id','af','sent','rcvd','loss_pct','rtt_min','rtt_avg','rtt_max','dst_name','dst_addr','src_addr','source_mode'].each{row[it]=e[it]}
row.event_time=java.time.Instant.ofEpochSecond((e.timestamp as Number).longValue()).toString()
def output=JsonOutput.toJson(row)+'\\n'
'''
probe='''assert e.prb_id instanceof Number && e.prb_id>0 && e.country=='UA'
def output=JsonOutput.toJson([probe_id:e.prb_id,country:e.country,asn_v4:e.asn_v4,asn_v6:e.asn_v6,latitude:e.latitude,longitude:e.longitude,status:e.status])+'\\n'
'''
status='''assert e.prb_id instanceof Number && e.prb_id>0 && e.timestamp>0
def output=JsonOutput.toJson([event_id:e.event_id,prb_id:e.prb_id,event_time:java.time.Instant.ofEpochSecond((e.timestamp as Number).longValue()).toString(),event:e.event])+'\\n'
'''
dlq=processor('RIPE invalid events','PublishKafka_2_6',{'bootstrap.servers':'kafka:9092','topic':'ripe.dead_letter'},1450,800,('success',))
connect(dlq,dlq,['failure'])
envelope=processor('Describe rejected events','ExecuteScript',{'Script Engine':'Groovy','Script Body':prefix+'''def output=JsonOutput.toJson(e.stage ? e : [schema_version:1,stage:'nifi_http_sink',reason:f.getAttribute('ripe.error') ?: ('HTTP_'+(f.getAttribute('invokehttp.status.code') ?: 'REJECTED')),received_at:java.time.Instant.now().toString(),payload:e])+'\\n'
'''+suffix},1200,800)
connect(envelope,dlq,['success','failure'])
all_processors=[dlq,envelope]
for idx,(topic,body,table) in enumerate([('ripe.raw',ping,'ping_results'),('ripe.probes',probe,None),('ripe.probe_status',status,'probe_events')]):
    y=idx*300
    consume=processor('Read '+topic,'ConsumeKafka_2_6',{'bootstrap.servers':'kafka:9092','topic':topic,'group.id':'nifi-ripe-v2-'+topic,'auto.offset.reset':'earliest','max.poll.records':'500'},100,y)
    transform=processor('Validate and transform '+topic,'ExecuteScript',{'Script Engine':'Groovy','Script Body':prefix+body+suffix},550,y)
    if table:
        url='http://analytics:8082/ingest/'+table
        sink=processor('Store '+table,'InvokeHTTP',{'HTTP Method':'POST','Remote URL':url,'Content-Type':'application/x-ndjson'},1000,y,('Original','Response'))
        connect(sink,sink,['Retry','Failure']); connect(sink,envelope,['No Retry'])
    else:
        sink=processor('Store probe_directory','InvokeHTTP',{'HTTP Method':'POST','Remote URL':'http://analytics:8082/ingest/probe_directory','Content-Type':'application/x-ndjson'},1000,y,('Original','Response'))
        connect(sink,sink,['Retry','Failure']);connect(sink,envelope,['No Retry'])
    connect(consume,transform,['success']);connect(transform,sink,['success']);connect(transform,envelope,['failure'])
    all_processors += [consume,transform,sink]
for p in reversed(all_processors):
    current=api('/processors/'+p['id'])
    errors=current['component'].get('validationErrors',[])
    if errors: print(current['component']['name'],errors)
    else: api('/processors/'+p['id']+'/run-status',{'revision':current['revision'],'state':'RUNNING'},'PUT');print('Started',current['component']['name'])
