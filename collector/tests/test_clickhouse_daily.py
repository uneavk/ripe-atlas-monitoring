import tempfile,unittest
from datetime import datetime,timezone
from app.retention_clickhouse import Store,FIELDS
class DailyBackend:
    def __init__(self):self.calls=[];self.controls={};self.revision=100;self.fail=False
    def __call__(self,sql,rows=None):
        self.calls.append((sql,rows))
        if sql.startswith('SELECT key,value'):return [{'key':k,'value':v} for k,v in self.controls.items()]
        if sql.startswith('SELECT toDate(hour_start') and 'max(version)' in sql:
            return [{'day':'2026-10-30','revision':self.revision}] if "<='2026-10-30'" in sql else []
        if sql.startswith('SELECT toDate(hour_start'):
            row={f:0 for f in FIELDS};row.update(day='2026-10-30',probe_id=1,msm_id=1001,af=4,asn=123,samples=101,sent=303,received=303,rtt_sum=1100,rtt_count=101,rtt_min=10,rtt_max=100)
            return [row]
        if sql=='INSERT INTO monitoring.daily_metrics' and self.fail:raise RuntimeError('simulated daily write failure')
        if sql=='INSERT INTO monitoring.retention_runs':
            for r in rows:self.controls[r['key']]=r['value']
        if sql.startswith('SELECT count()'):return [{'n':1}]
        return []
class DailyTests(unittest.TestCase):
    def test_four_am_daily_is_weighted_and_idempotent(self):
        backend=DailyBackend()
        with tempfile.TemporaryDirectory() as folder:
            store=Store(backend,folder)
            store.maintenance(datetime(2026,10,31,1,59,59,tzinfo=timezone.utc))
            self.assertFalse(any(s=='INSERT INTO monitoring.daily_metrics' for s,_ in backend.calls))
            store.maintenance(datetime(2026,10,31,2,0,0,tzinfo=timezone.utc))
            writes=[r for s,r in backend.calls if s=='INSERT INTO monitoring.daily_metrics']
            self.assertEqual(len(writes),1)
            row=writes[0][0];self.assertAlmostEqual(row['rtt_sum']/row['rtt_count'],1100/101)
            store.maintenance(datetime(2026,10,31,2,0,1,tzinfo=timezone.utc))
            self.assertEqual(sum(s=='INSERT INTO monitoring.daily_metrics' for s,_ in backend.calls),1)
            backend.revision+=1
            store.maintenance(datetime(2026,10,31,2,30,0,tzinfo=timezone.utc))
            self.assertEqual(sum(s=='INSERT INTO monitoring.daily_metrics' for s,_ in backend.calls),2)
    def test_failed_daily_write_prevents_hourly_deletion(self):
        backend=DailyBackend();backend.fail=True
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(RuntimeError):Store(backend,folder).maintenance(datetime(2026,10,31,2,0,0,tzinfo=timezone.utc))
        self.assertFalse(any(s.startswith('ALTER TABLE monitoring.hourly_metrics DELETE') for s,_ in backend.calls))
