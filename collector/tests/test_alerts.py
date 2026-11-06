import unittest
from unittest.mock import Mock
from app.alert_rules import detect,format_message,Incident
from app.telegram_sender import send,DeliveryError

NOW=1800000000
def ping(probe,ts,loss=0,rtt=20,mode='stream',msm=1001,af=4):
    return dict(event_id=f'{probe}-{ts}-{msm}',prb_id=probe,msm_id=msm,af=af,timestamp=ts,loss_pct=loss,rtt_avg=rtt,source_mode=mode)
class RulesTests(unittest.TestCase):
    def test_single_sample_and_archive_do_not_alert(self):
        self.assertEqual(detect([ping(1,NOW-10,100)],{}, {},{},NOW),[])
        self.assertEqual(detect([ping(1,NOW-20,100,mode='backfill'),ping(1,NOW-10,100,mode='backfill')],{},{},{},NOW),[])
    def test_loss_requires_two_distinct_timestamps_strict_threshold(self):
        self.assertEqual(detect([ping(1,NOW-20,50),ping(1,NOW-10,50)],{},{},{},NOW),[])
        self.assertEqual(detect([ping(1,NOW-10,100)]*2,{},{},{},NOW),[])
        self.assertEqual(detect([ping(1,NOW-20,100),ping(1,NOW-10,100)],{},{},{},NOW)[0].kind,'PACKET_LOSS')
    def test_baseline_is_specific_to_measurement_and_af(self):
        rows=[ping(1,NOW-20,rtt=60),ping(1,NOW-10,rtt=60)]
        self.assertEqual(detect(rows,{(1,1002,6):{'value':10,'samples':100}},{},{},NOW),[])
        self.assertEqual(detect(rows,{(1,1001,4):{'value':10,'samples':9}},{},{},NOW),[])
        self.assertEqual(detect(rows,{(1,1001,4):{'value':10,'samples':10}},{},{},NOW)[0].kind,'HIGH_RTT')
    def test_new_ping_refutes_old_disconnect(self):
        status={1:dict(timestamp=NOW-180,event='disconnect')}
        self.assertEqual(detect([ping(1,NOW-10)],{},status,{},NOW),[])
        self.assertEqual(detect([],{},status,{},NOW)[0].kind,'PROBE_DOWN')
        self.assertEqual(detect([],{}, {1:dict(timestamp=NOW-10,event='disconnect')},{},NOW),[])
    def test_asn_requires_four_observed_and_two_bad(self):
        probes={p:{'asn_v4':123} for p in range(1,5)}
        rows=[ping(p,NOW-t,loss=100 if p<=2 else 0) for p in probes for t in (20,10)]
        incidents=detect(rows,{}, {},probes,NOW)
        self.assertEqual(sum(i.kind=='ASN_OUTAGE' for i in incidents),1)
        self.assertFalse(any(i.kind=='REGION_OUTAGE' for i in incidents))
        self.assertFalse(any(i.kind=='ASN_OUTAGE' for i in detect([r for r in rows if r['prb_id']<4],{},{},probes,NOW)))
    def test_region_denominator_is_observed_not_inventory(self):
        probes={p:{'asn_v4':p} for p in range(1,100)}
        rows=[ping(p,NOW-t,loss=100 if p<=6 else 0) for p in range(1,21) for t in (20,10)]
        event=next(i for i in detect(rows,{},{},probes,NOW) if i.kind=='REGION_OUTAGE')
        self.assertEqual(event.details['observed'],20)
        self.assertEqual(event.details['percentage'],30)
    def test_ipv6_outage_uses_ipv6_asn(self):
        probes={p:{'asn_v4':123,'asn_v6':456} for p in range(1,5)}
        rows=[ping(p,NOW-t,loss=100 if p<=2 else 0,af=6) for p in probes for t in (20,10)]
        outages=[i for i in detect(rows,{},{},probes,NOW) if i.kind=='ASN_OUTAGE']
        self.assertEqual([i.details['asn'] for i in outages],[456])
    def test_stale_data_does_not_alert(self):
        self.assertEqual(detect([ping(1,NOW-400,100),ping(1,NOW-350,100)],{},{},{},NOW),[])
    def test_stable_id_and_shared_probe_cooldown_scope(self):
        a=Incident('HIGH_RTT','probe:1',NOW,{'msm_id':1001,'value':50,'baseline':10,'probe_id':1,'af':4})
        self.assertEqual(a.id,Incident(a.kind,a.scope,a.timestamp,a.details).id)
        self.assertIn('RIPE Atlas',format_message(a))
        self.assertEqual(a.cooldown,300)
        self.assertEqual(Incident('ASN_OUTAGE','asn:1',NOW,{}).cooldown,1800)

class TelegramTests(unittest.TestCase):
    def test_success_and_no_secret_in_error(self):
        session=Mock();session.post.return_value.status_code=200
        session.post.return_value.json.return_value={'ok':True,'result':{'message_id':42}}
        self.assertEqual(send('private-token','123','hello',session),42)
        session.post.return_value.status_code=429
        session.post.return_value.json.return_value={'ok':False,'error_code':429,'parameters':{'retry_after':23}}
        with self.assertRaises(DeliveryError) as error:send('private-token','123','hello',session)
        self.assertEqual(error.exception.retry_after,23)
        self.assertNotIn('private-token',str(error.exception))
    def test_transport_exception_is_redacted(self):
        import requests
        session=Mock();session.post.side_effect=requests.ConnectionError('https://api.telegram.org/botprivate-token/sendMessage')
        with self.assertRaises(DeliveryError) as error:send('private-token','123','hello',session)
        self.assertNotIn('private-token',str(error.exception))

if __name__=='__main__':unittest.main()
