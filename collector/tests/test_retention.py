import unittest
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from app.retention import finalized_day,instant,values,seconds_to_next_run

class RetentionTests(unittest.TestCase):
    def test_scheduler_wakes_at_four_am_boundary(self):
        a=datetime(2026,10,31,3,59,59,tzinfo=ZoneInfo('Europe/Kyiv')).astimezone(timezone.utc)
        self.assertEqual(seconds_to_next_run(a),1)
    def test_kyiv_four_am_boundary(self):
        tz=ZoneInfo('Europe/Kyiv')
        a=datetime(2026,10,31,3,59,59,tzinfo=tz)
        b=a+timedelta(seconds=1)
        self.assertEqual(str(finalized_day(a)),'2026-10-29')
        self.assertEqual(str(finalized_day(b)),'2026-10-30')
    def test_dst_repeated_hours_keep_distinct_utc_keys(self):
        tz=ZoneInfo('Europe/Kyiv')
        a=datetime(2026,10,25,3,30,tzinfo=tz,fold=0).astimezone(timezone.utc)
        b=datetime(2026,10,25,3,30,tzinfo=tz,fold=1).astimezone(timezone.utc)
        self.assertEqual(b-a,timedelta(hours=1))
        self.assertNotEqual(a.replace(minute=0),b.replace(minute=0))
    def test_null_rtt_is_not_counted_as_zero_latency(self):
        p=dict(event_id='x',prb_id=1,msm_id=1001,af=4,event_time='2026-10-31T00:00:00Z',sent=3,rcvd=0,rtt_avg=None)
        v=values(p,'ping_results')[-1]
        self.assertEqual(v['rtt_count'],0)
        self.assertEqual(v['full_loss_samples'],1)
    def test_invalid_packet_counts_rejected(self):
        p=dict(event_id='x',prb_id=1,msm_id=1001,af=4,event_time='2026-10-31T00:00:00Z',sent=3,rcvd=4,rtt_avg=1)
        with self.assertRaises(ValueError):values(p,'ping_results')
