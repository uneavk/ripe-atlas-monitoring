"""Telegram transport. Never log request URLs or exceptions containing the token."""
import requests

class DeliveryError(Exception):
    def __init__(self,code,retry_after=0):
        self.code=code;self.retry_after=retry_after
        super().__init__(str(code))

def call(token,method,body,session=None):
    session=session or requests.Session()
    try:
        response=session.post('https://api.telegram.org/bot'+token+'/'+method,json=body,timeout=(5,15))
        payload=response.json()
    except (requests.RequestException,ValueError):
        raise DeliveryError('NETWORK_OR_INVALID_RESPONSE') from None
    if response.status_code!=200 or not payload.get('ok'):
        raise DeliveryError(payload.get('error_code',response.status_code),int((payload.get('parameters') or {}).get('retry_after',0)))
    return payload['result']

def send(token,chat_id,text,session=None):
    return call(token,'sendMessage',{'chat_id':chat_id,'text':text,'parse_mode':'HTML','link_preview_options':{'is_disabled':True}},session)['message_id']
