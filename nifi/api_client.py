"""Local NiFi REST client. Reads configured credentials without printing them."""
import json,ssl,subprocess,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path
project=Path(__file__).resolve().parents[1]
container=subprocess.check_output(['docker','compose','ps','-q','nifi'],cwd=project,text=True).strip()
if not container:raise RuntimeError('Start NiFi with docker compose before configuring the flow')
definition=json.loads(subprocess.check_output(['docker','inspect',container],text=True,encoding='utf-8'))[0]
env=dict(item.split('=',1) for item in definition['Config']['Env'] if '=' in item)
port=definition['NetworkSettings']['Ports']['8443/tcp'][0]['HostPort']
base='https://localhost:'+port+'/nifi-api'
context=ssl._create_unverified_context()  # NiFi's locally generated certificate, localhost only.
token=''

def api(path,data=None,method=None):
    headers={'Authorization':'Bearer '+token} if token else {}
    if isinstance(data,dict):data=json.dumps(data).encode();headers['Content-Type']='application/json'
    request=urllib.request.Request(base+path,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(request,context=context,timeout=30) as response:raw=response.read().decode()
    except urllib.error.HTTPError as error:
        raise RuntimeError('NiFi API HTTP '+str(error.code)) from None
    try:return json.loads(raw)
    except ValueError:return raw

for attempt in range(180):
    try:
        token=api('/access/token',urllib.parse.urlencode({'username':env['SINGLE_USER_CREDENTIALS_USERNAME'],'password':env['SINGLE_USER_CREDENTIALS_PASSWORD']}).encode())
        if not isinstance(token,str) or not token or any(c.isspace() for c in token) or '<' in token:
            token='';raise RuntimeError('NiFi returned an invalid token response; check proxy host configuration')
        root=api('/flow/process-groups/root')['processGroupFlow']['id'];break
    except (OSError,RuntimeError):
        if attempt%15==0:print('Waiting for NiFi initialization...',flush=True)
        time.sleep(2)
else:raise RuntimeError('NiFi did not become ready; inspect docker compose logs nifi')
