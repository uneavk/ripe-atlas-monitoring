"""Durable opt-in private-chat subscriptions and independent recipient delivery."""
from datetime import datetime,timezone,timedelta
import time
from .telegram_sender import call,send,DeliveryError

def command(update):
    message=update.get('message') or {}
    chat=message.get('chat') or {};sender=message.get('from') or {}
    if chat.get('type')!='private' or sender.get('is_bot') or chat.get('id')!=sender.get('id'):return None
    text=message.get('text','').strip().split()
    if not text:return None
    name=text[0].lower().split('@')[0]
    return (int(chat['id']),name) if name in ('/start','/stop','/status','/help') else None

def apply_updates(conn,updates):
    with conn.transaction():
        offset=conn.execute('SELECT next_update_id FROM telegram_poll_state WHERE id=1 FOR UPDATE').fetchone()[0]
        for update in sorted(updates,key=lambda u:u['update_id']):
            uid=int(update['update_id'])
            if uid<offset:continue
            cmd=command(update)
            if cmd:
                chat_id,name=cmd
                if name=='/start':
                    conn.execute('INSERT INTO telegram_subscribers(chat_id) VALUES (%s) ON CONFLICT(chat_id) DO UPDATE SET active=true,subscribed_at=CASE WHEN telegram_subscribers.active THEN telegram_subscribers.subscribed_at ELSE now() END,updated_at=now()',(chat_id,))
                    reply='✅ Підписку ввімкнено. Ви автоматично отримуватимете нові підтверджені інциденти RIPE Atlas.\n/stop — відписатися\n/status — стан підписки'
                elif name=='/stop':
                    conn.execute('INSERT INTO telegram_subscribers(chat_id,active) VALUES (%s,false) ON CONFLICT(chat_id) DO UPDATE SET active=false,updated_at=now()',(chat_id,))
                    conn.execute("UPDATE telegram_deliveries SET status='cancelled' WHERE chat_id=%s AND status='pending'",(chat_id,))
                    reply='🔕 Підписку вимкнено. Для поновлення надішліть /start.'
                elif name=='/status':
                    row=conn.execute('SELECT active FROM telegram_subscribers WHERE chat_id=%s',(chat_id,)).fetchone()
                    reply='✅ Підписка активна.' if row and row[0] else '🔕 Підписка неактивна. Надішліть /start.'
                else:reply='/start — підписатися на інциденти\n/stop — відписатися\n/status — стан підписки'
                conn.execute('INSERT INTO telegram_command_replies(update_id,chat_id,message) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING',(uid,chat_id,reply))
            offset=uid+1
        conn.execute('UPDATE telegram_poll_state SET next_update_id=%s WHERE id=1',(offset,))

def poll(conn,config):
    if not config.get('token'):return
    # Keep the previously configured recipient without overriding /stop.
    if str(config.get('chat_id','')).lstrip('-').isdigit():
        conn.execute('INSERT INTO telegram_subscribers(chat_id) VALUES (%s) ON CONFLICT DO NOTHING',(int(config['chat_id']),))
    offset=conn.execute('SELECT next_update_id FROM telegram_poll_state WHERE id=1').fetchone()[0]
    updates=call(config['token'],'getUpdates',{'offset':offset,'timeout':0,'limit':100,'allowed_updates':['message']})
    apply_updates(conn,updates)

def retry(conn,table,key_where,key_values,error,attempts):
    permanent=error.code in (400,401,403,404)
    delay=max(error.retry_after,min(3600,15*2**min(attempts,8)))
    conn.execute(f"UPDATE {table} SET status=%s,attempts=attempts+1,last_error=%s,next_attempt_at=now()+(%s * interval '1 second') WHERE {key_where}",('failed' if permanent else 'pending',str(error.code),delay,*key_values))
    if error.code==429:
        conn.execute("UPDATE telegram_poll_state SET pause_until=now()+(%s * interval '1 second') WHERE id=1",(max(1,delay),))
    return permanent

def dispatch(conn,config):
    if not config.get('token'):return
    pause=conn.execute('SELECT pause_until FROM telegram_poll_state WHERE id=1').fetchone()[0]
    if pause>datetime.now(timezone.utc):return
    for _ in range(10):
        with conn.transaction():
            reply=conn.execute("SELECT update_id,chat_id,message,attempts FROM telegram_command_replies WHERE status='pending' AND next_attempt_at<=now() ORDER BY update_id FOR UPDATE SKIP LOCKED LIMIT 1").fetchone()
            if not reply:break
            uid,chat,message,attempts=reply
            try:send(config['token'],str(chat),message)
            except DeliveryError as error:
                retry(conn,'telegram_command_replies','update_id=%s',(uid,),error,attempts)
                if error.code==429:return
            else:conn.execute("UPDATE telegram_command_replies SET status='sent',attempts=attempts+1,last_error=NULL WHERE update_id=%s",(uid,))
        time.sleep(.1)
    # Fan-out is recorded when the incident is created: a new subscriber gets
    # future incidents, and never an unsolicited historical backlog.
    for _ in range(20):
        with conn.transaction():
            row=conn.execute("SELECT d.outbox_id,d.chat_id,o.message,d.attempts,o.created_at,s.active FROM telegram_deliveries d JOIN telegram_outbox o ON o.id=d.outbox_id JOIN telegram_subscribers s ON s.chat_id=d.chat_id WHERE d.status='pending' AND d.next_attempt_at<=now() ORDER BY d.outbox_id,d.chat_id FOR UPDATE OF d SKIP LOCKED LIMIT 1").fetchone()
            if not row:break
            oid,chat,message,attempts,created,active=row
            if not active or datetime.now(timezone.utc)-created>timedelta(minutes=15):
                conn.execute('UPDATE telegram_deliveries SET status=%s WHERE outbox_id=%s AND chat_id=%s',('cancelled' if not active else 'expired',oid,chat));continue
            try:mid=send(config['token'],str(chat),message)
            except DeliveryError as error:
                retry(conn,'telegram_deliveries','outbox_id=%s AND chat_id=%s',(oid,chat),error,attempts)
                if error.code==403:conn.execute('UPDATE telegram_subscribers SET active=false,updated_at=now() WHERE chat_id=%s',(chat,))
                if error.code==429:return
            else:
                conn.execute("UPDATE telegram_deliveries SET status='sent',attempts=attempts+1,sent_at=now(),telegram_message_id=%s,last_error=NULL WHERE outbox_id=%s AND chat_id=%s",(mid,oid,chat))
        time.sleep(.1)
    conn.execute("UPDATE telegram_outbox o SET status=CASE WHEN NOT EXISTS(SELECT 1 FROM telegram_deliveries d WHERE d.outbox_id=o.id AND d.status<>'sent') THEN 'sent' ELSE 'completed_with_errors' END,sent_at=now() WHERE o.status='pending' AND EXISTS(SELECT 1 FROM telegram_deliveries d WHERE d.outbox_id=o.id) AND NOT EXISTS(SELECT 1 FROM telegram_deliveries d WHERE d.outbox_id=o.id AND d.status='pending')")
    conn.execute('UPDATE monitoring_incidents i SET notification_status=o.status FROM telegram_outbox o WHERE o.incident_id=i.incident_id AND o.status<>\'pending\' AND i.notification_status<>o.status')
