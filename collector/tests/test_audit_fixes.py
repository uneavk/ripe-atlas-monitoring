import unittest
from app.models import normalize_ping,validate_minimum
from app.alert_rules import detect,Incident,format_message
from app.incident_state import recovered,key
from app.retention_clickhouse import values

NOW=1800000000
def ping(ts,loss=0,rtt=20):
    return dict(event_id=str(ts),prb_id=1,msm_id=1001,af=4,timestamp=ts,source_mode='stream',loss_pct=loss,rtt_avg=rtt)

class AuditFixes(unittest.TestCase):
    def test_full_loss_has_no_rtt(self):
        e=normalize_ping(dict(prb_id=1,msm_id=1001,af=4,timestamp=NOW,sent=3,rcvd=0,avg=140,min=130,max=150),'stream')
        self.assertIsNone(e['rtt_avg']);self.assertEqual(validate_minimum(e),(True,None))
    def test_gateway_rejects_inconsistent_metrics(self):
        e=dict(event_id='abc',prb_id=1,msm_id=1001,af=4,event_time=NOW,sent=3,rcvd=0,loss_pct=100,rtt_min=1,rtt_avg=2,rtt_max=3)
        with self.assertRaisesRegex(ValueError,'RTT_WITHOUT_REPLY'):values(e,'ping_results')
    def test_ten_minute_confirmation_with_fresh_latest(self):
        self.assertTrue(detect([ping(NOW-400,100),ping(NOW-160,100)],{},{},{},NOW))
        self.assertFalse(detect([ping(NOW-640,100),ping(NOW-400,100)],{},{},{},NOW))
    def test_long_disconnect_remains_open(self):
        self.assertEqual(detect([],{},{1:dict(timestamp=NOW-36000,event='disconnect')},{},NOW)[0].kind,'PROBE_DOWN')
    def test_silence_is_not_recovery(self):
        episode=('PACKET_LOSS','probe:1',dict(probe_id=1,msm_id=1001,af=4),NOW-500)
        self.assertFalse(recovered(episode,[],{},NOW))
        self.assertFalse(recovered(episode,[ping(NOW-10)],{},NOW))
        self.assertTrue(recovered(episode,[ping(NOW-250),ping(NOW-10)],{},NOW))
    def test_only_new_connection_resolves_disconnect(self):
        episode=('PROBE_DOWN','probe:1',dict(probe_id=1),NOW-500)
        self.assertFalse(recovered(episode,[],{1:dict(timestamp=NOW-600,event='connect')},NOW))
        self.assertTrue(recovered(episode,[],{1:dict(timestamp=NOW-10,event='connect')},NOW))
    def test_recovery_and_health_messages(self):
        self.assertIn('RIPE Atlas',format_message(Incident('RECOVERED','probe:1',NOW,dict(original_kind='PACKET_LOSS'))))
        self.assertIn('RIPE Atlas',format_message(Incident('PIPELINE_STALE','measurement:1001',NOW,dict(msm_id=1001,af=4))))
    def test_episode_separates_measurement_and_kind(self):
        a=Incident('HIGH_RTT','probe:1',NOW,dict(msm_id=1001,af=4))
        b=Incident('PACKET_LOSS','probe:1',NOW,dict(msm_id=1001,af=4))
        self.assertNotEqual(key(a),key(b))
