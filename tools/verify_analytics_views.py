"""Check live queryability and daily weighted aggregation against storage."""
try:
    from app.retention_clickhouse import ch
except ModuleNotFoundError:
    from pathlib import Path
    import subprocess
    script=Path(__file__).resolve()
    subprocess.run(['docker','compose','exec','-T','analytics','python','-c',script.read_text(encoding='utf-8')],cwd=script.parents[1],check=True)
    raise SystemExit(0)

views=ch("SELECT name FROM system.tables WHERE database='analytics' ORDER BY name FORMAT JSONEachRow")
for view in views:
    ch('SELECT * FROM analytics.'+view['name']+' LIMIT 1 FORMAT JSONEachRow')
expected=ch("SELECT toString(day) AS day,msm_id,af,sum(samples) AS n,sum(sent) AS sent,sum(received) AS received,sum(rtt_sum) AS rtt_sum,sum(rtt_count) AS rtt_count,uniqExact(probe_id) AS probes FROM monitoring.daily_metrics FINAL WHERE af IN (4,6) AND samples>0 GROUP BY day,msm_id,af FORMAT JSONEachRow")
actual=ch('SELECT toString(toDate(period_start)) AS day,* FROM analytics.network_daily FORMAT JSONEachRow')
lookup={(r['day'],r['measurement_id'],r['ip_version']):r for r in actual}
for r in expected:
    row=lookup[(r['day'],r['msm_id'],'IPv'+str(r['af']))]
    for source,target in [('n','measurement_count'),('sent','packets_sent'),('received','packets_received'),('probes','probes_observed')]:
        assert int(r[source])==int(row[target]),(source,r,row)
    if int(r['rtt_count']):assert abs(float(row['avg_rtt_ms'])-float(r['rtt_sum'])/int(r['rtt_count']))<1e-6
    if int(r['sent']):assert abs(float(row['packet_loss_pct'])-100*(int(r['sent'])-int(r['received']))/int(r['sent']))<1e-6
assert not ch("SELECT table,name FROM system.columns WHERE database IN ('analytics','monitoring') AND name LIKE '%formula%' FORMAT JSONEachRow")
print('PASS:',len(views),'views queried;',len(expected),'daily groups checked against stored weighted statistics; no formula columns')
print(ch('SELECT * FROM analytics.data_freshness ORDER BY measurement_id FORMAT JSONEachRow'))
