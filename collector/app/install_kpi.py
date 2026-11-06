"""Install analytical dictionaries and reporting views only in ClickHouse."""
import re
from .kpi_catalog import KPI,DIMENSIONS,DISPLAY
from .retention_clickhouse import ch,quote
def main():
    columns=['kpi_code','kpi_name_uk','unit_uk','description_uk']
    ch('CREATE TABLE IF NOT EXISTS monitoring.kpi_dictionary ('+','.join(c+' String' for c in columns)+') ENGINE=ReplacingMergeTree ORDER BY kpi_code')
    ch('INSERT INTO monitoring.kpi_dictionary',[dict(zip(columns,[r[0],r[1],r[2],r[5]])) for r in KPI])
    ch('CREATE TABLE IF NOT EXISTS monitoring.field_dictionary (field_code String,field_name_uk String) ENGINE=ReplacingMergeTree ORDER BY field_code')
    ch('INSERT INTO monitoring.field_dictionary',[dict(zip(['field_code','field_name_uk'],r)) for r in DIMENSIONS])
    for grain in ('hourly','daily'):
        hourly=grain=='hourly';name='Погодинні дані' if hourly else 'Поденні дані'
        start='q.hour_start' if hourly else "toDateTime(q.day,'Europe/Kyiv')"
        end='q.hour_start+INTERVAL 1 HOUR' if hourly else "toDateTime(addDays(q.day,1),'Europe/Kyiv')"
        for level,codes in [('network',DISPLAY),('provider',['observed_probes','samples','packet_loss_pct','avg_rtt_ms'])]:
            view=grain+'_'+level+'_metrics'
            definition=ch('SHOW CREATE TABLE monitoring.'+view+' FORMAT JSONEachRow')[0]['statement']
            if 'period_name_uk' not in definition:
                select=re.split(r'\bAS\s+(?=SELECT\b)',definition,maxsplit=1,flags=re.S)[1]
                label="formatDateTime(toTimeZone(q.hour_start,'Europe/Kyiv'),'%d.%m.%Y %H:%i %z')" if hourly else "formatDateTime(toDateTime(q.day),'%d.%m.%Y')"
                ch('CREATE OR REPLACE VIEW monitoring.'+view+' AS SELECT q.*,'+quote(name)+' AS period_name_uk,'+label+' AS period_label FROM ('+select+') q')
            source='SELECT * FROM monitoring.'+view
            if level=='network':
                keys='hour_start,probe_id,msm_id,af,asn' if hourly else 'day,probe_id,msm_id,af,asn'
                source='SELECT v.*,h.loss_samples,h.full_loss_samples FROM monitoring.'+view+' v INNER JOIN (SELECT * FROM monitoring.'+grain+'_metrics FINAL) h USING('+keys+')'
            pairs=','.join('tuple('+quote(c)+',toNullable(toFloat64('+(('(q.sent-q.received)') if c=='packets_lost' else 'q.'+c)+')))' for c in codes)
            dims='q.probe_id,q.msm_id,q.af,q.asn' if level=='network' else 'q.msm_id,q.af,q.asn'
            target=grain+('_kpi' if level=='network' else '_provider_kpi')
            ch('CREATE OR REPLACE VIEW monitoring.'+target+' AS SELECT '+start+' AS period_start,'+end+' AS period_end,q.period_name_uk,q.period_label,'+dims+',d.kpi_code,d.kpi_name_uk,tupleElement(metric,2) AS kpi_value,d.unit_uk FROM ('+source+') q ARRAY JOIN ['+pairs+'] AS metric INNER JOIN (SELECT * FROM monitoring.kpi_dictionary FINAL) d ON d.kpi_code=tupleElement(metric,1)')
    for column in ('formula_uk','aggregation'):
        ch('ALTER TABLE monitoring.kpi_dictionary DROP COLUMN IF EXISTS '+column)
    print('ClickHouse catalog:',len(KPI),'KPI definitions;',len(DIMENSIONS),'dimension definitions')
if __name__=='__main__':main()
