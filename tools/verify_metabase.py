"""Execute every provisioned question and check dashboard layout and the IPv6 filter."""
from pathlib import Path
import json,sys
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from setup_metabase import API

def main():
    private=ROOT/'.secrets/metabase'
    config=json.loads((private/'admin.json').read_text(encoding='utf-8'))
    manifest=json.loads((private/'manifest.json').read_text(encoding='utf-8'))
    api=API(manifest['url'],private)
    api.session=api.call('/session',{'username':config['email'],'password':config['password']})['id']
    results=[]
    for dashboard in manifest['dashboards']:
        saved=api.call('/dashboard/'+str(dashboard['id']))
        panels=saved['dashcards']
        for i,a in enumerate(panels):
            assert a['col']>=0 and a['col']+a['size_x']<=24
            for b in panels[i+1:]:
                overlap=a['col']<b['col']+b['size_x'] and b['col']<a['col']+a['size_x'] and a['row']<b['row']+b['size_y'] and b['row']<a['row']+a['size_y']
                assert not overlap,('Overlapping dashboard cards',a['id'],b['id'])
        for card in dashboard['cards']:
            answer=api.call('/card/'+str(card['id'])+'/query',{})
            status=answer.get('status');rows=len(answer.get('data',{}).get('rows',[]))
            if status!='completed':
                (private/'last_query_error.json').write_text(json.dumps(answer),encoding='utf-8')
                raise RuntimeError('Question failed: '+card['key']+'; diagnostic saved privately')
            results.append({'dashboard':dashboard['key'],'question':card['key'],'status':status,'rows':rows})
            print('PASS',card['key'],'rows=',rows,flush=True)
            if card['key']=='probe_map':
                answer=api.call('/card/'+str(card['id'])+'/query',{'parameters':[{'id':'measurement','type':'number','target':['variable',['template-tag','measurement']],'value':2001}]})
                assert answer.get('status')=='completed','IPv6 map filter failed'
                cols=[c['name'] for c in answer['data']['cols']]
                index=cols.index('ip_version')
                assert answer['data']['rows'] and all(r[index]=='IPv6' for r in answer['data']['rows']),'IPv6 filter returned wrong protocol'
                results.append({'question':'probe_map_ipv6_filter','status':'completed','rows':len(answer['data']['rows'])})
    (ROOT/'bi/validation.json').write_text(json.dumps({'recorded_at':datetime.now(timezone.utc).isoformat(),'checks':results,'layout':'no overlaps','ipv6_filter':'passed'},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('PASS all questions, IPv6 map filter and dashboard layouts')

if __name__=='__main__':main()
