import tempfile,unittest
from datetime import datetime,timezone,timedelta
from app.retention_clickhouse import Store,hour_key
class FakeClickHouse:
    def __init__(self):self.raw={};self.hours={};self.fail_raw=False
    def __call__(self,sql,rows=None):
        if sql.startswith('SELECT event_id'):return [{'event_id':k} for k in self.raw]
        if sql.startswith('SELECT probe_id,asn'):return [{'probe_id':1,'asn_v4':123,'asn_v6':456}]
        if sql.startswith('SELECT * FROM monitoring.hourly'):return list(self.hours.values())
        if sql=='INSERT INTO monitoring.hourly_metrics':
            for row in rows:self.hours[hour_key(row)]=row
        elif sql=='INSERT INTO monitoring.ping_results':
            if self.fail_raw:self.fail_raw=False;raise RuntimeError('simulated failure after aggregate write')
            for row in rows:self.raw[row['event_id']]=row
        return []
class ClickHouseOnlyTests(unittest.TestCase):
    def event(self,identity='test-a',rtt=10):
        return dict(event_id=identity,prb_id=1,msm_id=1001,af=4,event_time=self.now.isoformat(),sent=3,rcvd=3,rtt_avg=rtt,rtt_min=rtt,rtt_max=rtt,source_mode='stream')
    def setUp(self):self.now=datetime(2026,10,31,0,0,tzinfo=timezone.utc)
    def test_replay_after_partial_write_does_not_double_count(self):
        backend=FakeClickHouse()
        with tempfile.TemporaryDirectory() as folder:
            store=Store(backend,folder);backend.fail_raw=True
            with self.assertRaises(RuntimeError):store.ingest([self.event()],'ping_results',self.now)
            self.assertTrue(store.path.exists())
            store=Store(backend,folder)
            self.assertEqual(store.ingest([self.event()],'ping_results',self.now)['accepted'],0)
            self.assertEqual(next(iter(backend.hours.values()))['samples'],1)
            self.assertEqual(len(backend.raw),1);self.assertFalse(store.path.exists())
    def test_duplicates_and_weighted_state(self):
        backend=FakeClickHouse()
        with tempfile.TemporaryDirectory() as folder:
            store=Store(backend,folder)
            self.assertEqual(store.ingest([self.event(),self.event()],'ping_results',self.now)['accepted'],1)
            store.ingest([self.event('test-b',20)],'ping_results',self.now)
            total=next(iter(backend.hours.values()))
            self.assertEqual(total['samples'],2);self.assertEqual(total['rtt_sum']/total['rtt_count'],15)
            self.assertEqual((total['rtt_min'],total['rtt_max']),(10,20))
    def test_old_data_not_reintroduced(self):
        backend=FakeClickHouse()
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(Store(backend,folder).ingest([self.event()],'ping_results',self.now+timedelta(hours=6))['ignored_older_than_5h'],1)
            self.assertEqual(backend.raw,{})
