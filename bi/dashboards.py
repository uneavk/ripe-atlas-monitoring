"""Versioned Metabase questions and layout; contains no credentials or data."""
COLORS=['#2563eb','#ea580c','#16a34a','#9333ea','#dc2626','#0891b2']

def card(key,name,sql,display='table',source='ch',description='',settings=None,measurement=False):
    style={'graph.colors':COLORS,'table.pivot':False}
    if display in ('line','area','bar'):
        style.update({'graph.dimensions':['period_start','series'],'graph.metrics':['value'],'graph.show_values':False,'graph.show_trendline':False,'graph.x_axis.title_text':'Час · Київ','graph.y_axis.title_text':name,'graph.show_goal':False,'graph.missing_value':'none'})
    labels={'target_name':'Ціль','ip_version':'Протокол','latest_measurement_at':'Останні дані','data_age_seconds':'Давність, с','measurements_last_5h':'Серії за 5 год','probes_observed_last_5h':'Зондів за 5 год','data_status':'Стан','probe_id':'Зонд','provider_name':'Провайдер (ASN)','packet_loss_pct':'Втрати, %','avg_rtt_ms':'RTT, мс','last_measured_at':'Час результату','probes_observed':'Зондiв','measurement_count':'Серій','period_start':'Період','network_rtt_ms':'RTT вибірки, мс','deviation_ms':'Відхилення, мс','started_at':'Початок','incident_type':'Тип інциденту','severity':'Критичність','incident_status':'Стан епізоду','provider_asn':'ASN','measurement_id':'Вимірювання','resolved_at':'Відновлення','notification_status':'Сповіщення','episodes':'Епізодів','mean_minutes':'Середня тривалість, хв','stage':'Стадія','reason':'Причина','rejected_events':'Відхилених записів'}
    style['column_settings']={'["name",'+__import__('json').dumps(k)+']':{'column_title':v} for k,v in labels.items()}
    for k in ('probe_id','provider_asn','measurement_id'):
        style['column_settings']['["name",'+__import__('json').dumps(k)+']'].update({'number_separators':'.','decimals':0})
    if display=='line':
        style['series_settings']={name:{'line.missing':'none'} for name in ('K-root · IPv4','K-root · IPv6','F-root · IPv4','F-root · IPv6')}
    style.update(settings or {})
    return dict(key=key,name=name,sql=sql,display=display,source=source,description=description,settings=style,measurement=measurement)

def trend(key,name,view,metric,description):
    if view.endswith('_5minutes'):
        start="toStartOfFiveMinutes(now()-INTERVAL 5 HOUR)"
        slots='61';period=f'{start}+toIntervalMinute(n.number*5)'
        prefix=''
    elif view.endswith('_hourly'):
        slots='48';period='toStartOfHour(now())-toIntervalHour(48-n.number)';prefix=''
    else:
        prefix="WITH (SELECT if(count()=0,today()-7,greatest(ifNull(min(toDate(period_start)),today()-7),today()-365)) FROM analytics.network_daily) AS first_day "
        slots="assumeNotNull(toUInt64(greatest(1,dateDiff('day',first_day,today()))))"
        period="toDateTime(addDays(first_day,n.number),'Europe/Kyiv')"
    sql=prefix+f"SELECT {period} AS period_start,concat(m.target_name,' · ',m.ip_version) AS series,if(v.measurement_count=0,NULL,v.{metric}) AS value FROM numbers({slots}) n CROSS JOIN analytics.measurement_directory m LEFT JOIN analytics.{view} v ON v.period_start={period} AND v.measurement_id=m.measurement_id ORDER BY period_start,series"
    return card(key,name,sql,'line',description=description+' Розриви ліній означають відсутні спостереження, не нуль.')

def build():
    live=[
        card('freshness','Свіжість чотирьох джерел',"SELECT target_name,ip_version,latest_measurement_at,data_age_seconds,measurements_last_5h,probes_observed_last_5h,data_status FROM analytics.data_freshness ORDER BY measurement_id",description='Давність >15 хв означає застарілі дані. Під час backfill стан може тимчасово бути застарілим.'),
        card('ipv4_probes','Зондів IPv4 · останні 15 хв',"SELECT uniqExact(probe_id) AS value FROM analytics.measurements_live WHERE ip_version='IPv4' AND measured_at>=now()-INTERVAL 15 MINUTE",'scalar',description='DISTINCT між обома цілями: зонд рахується один раз.'),
        card('ipv6_probes','Зондів IPv6 · останні 15 хв',"SELECT uniqExact(probe_id) AS value FROM analytics.measurements_live WHERE ip_version='IPv6' AND measured_at>=now()-INTERVAL 15 MINUTE",'scalar',description='Менша вибірка IPv6 не означає автоматично проблему IPv6.'),
        card('series_15m','Серій ping · останні 15 хв',"SELECT count() AS value FROM analytics.measurements_live WHERE measured_at>=now()-INTERVAL 15 MINUTE",'scalar',description='Серія містить декілька пакетів. Це кількість результатів, не пакетів.'),
        trend('live_rtt','Затримка · мс','network_5minutes','avg_rtt_ms','Середнє валідних RTT серій; NULL без відповідей. Кожна ціль та IP-версія — окрема лінія.'),
        trend('live_loss','Втрати пакетів · %','network_5minutes','packet_loss_pct','Втрата зі співвідношення сум пакетів. Останній 5-хвилинний інтервал може бути неповним.'),
        trend('live_probes','Покриття · різні зонди','network_5minutes','probes_observed','Різні зонди кожної цілі/AF у періоді. Це не відсоток населення.'),
        trend('live_success','Серії з відповіддю · %','network_5minutes','successful_measurements_pct','Хоча б один отриманий пакет робить серію успішною; це не часова availability.'),
        card('probe_map','Карта останніх втрат · обране вимірювання',"""SELECT probe_id,any(target_name) AS target_name,any(ip_version) AS ip_version,
argMax(q.latitude,q.measured_at) AS latitude,argMax(q.longitude,q.measured_at) AS longitude,
argMax(packet_loss_pct,measured_at) AS packet_loss_pct,max(measured_at) AS last_measured_at
FROM analytics.measurements_live q WHERE q.measurement_id={{measurement}} AND q.latitude IS NOT NULL AND q.longitude IS NOT NULL
GROUP BY probe_id""",'map',description='Остання серія на зонд. Оберіть measurement: 1001 K-root IPv4; 2001 K-root IPv6; 1004 F-root IPv4; 2004 F-root IPv6.',measurement=True,settings={'map.type':'pin','map.latitude_column':'latitude','map.longitude_column':'longitude','map.metric_column':'packet_loss_pct','map.pin_type':'markers','map.center_latitude':48.5,'map.center_longitude':31.3,'map.zoom':5}),
        card('latest_loss','Зонди з найбільшими поточними втратами',"""SELECT probe_id,any(provider_name) AS provider_name,
argMax(packet_loss_pct,measured_at) AS packet_loss_pct,max(measured_at) AS last_measured_at
FROM analytics.measurements_live WHERE measurement_id={{measurement}}
GROUP BY probe_id ORDER BY packet_loss_pct DESC,last_measured_at DESC LIMIT 20""",description='Останній результат, а не підтверджений інцидент. Перевірте повтори в журналі інцидентів.',measurement=True),
    ]
    history=[
        trend('hour_rtt','Завершені години · затримка, мс','network_hourly','avg_rtt_ms','48 годин. Поточна незавершена година не показується.'),
        trend('hour_loss','Завершені години · втрати, %','network_hourly','packet_loss_pct','Зважені packet-loss KPI, окремо за ціллю та AF.'),
        trend('day_rtt','Поденна історія · затримка, мс','network_daily','avg_rtt_ms','Зважене середнє за кількістю валідних серій. Доба фіналізується після 04:00 за Києвом.'),
        trend('day_loss','Поденна історія · втрати, %','network_daily','packet_loss_pct','Дні з відсутніми спостереженнями не підміняються нульовими втратами.'),
        trend('day_probes','Поденне покриття · зонди','network_daily','probes_observed','DISTINCT за днем, а не сума годинних кількостей.'),
        card('asn_rank','Провайдери · остання завершена година',"""SELECT provider_name,packet_loss_pct,avg_rtt_ms,probes_observed,measurement_count,period_start
FROM analytics.providers_hourly
WHERE measurement_id={{measurement}} AND probes_observed>=4
AND period_start=(SELECT max(period_start) FROM analytics.providers_hourly WHERE measurement_id={{measurement}})
ORDER BY packet_loss_pct DESC,avg_rtt_ms DESC LIMIT 15""",description='Не менше 4 спостережуваних зондів; рейтинг тільки одного measurement. ASN — не завжди комерційна назва провайдера.',measurement=True),
        card('asn_trend','Провайдери · погодинні втрати, %',"""SELECT period_start,provider_name AS series,packet_loss_pct AS value
FROM analytics.providers_hourly WHERE measurement_id={{measurement}} AND probes_observed>=4
AND provider_asn IN (SELECT provider_asn FROM analytics.providers_hourly WHERE measurement_id={{measurement}} GROUP BY provider_asn ORDER BY sum(measurement_count) DESC LIMIT 8)
ORDER BY period_start,series""",'line',description='До 8 ASN із найбільшою кількістю вимірювань; середні відсотки повторно не агрегуються.',measurement=True),
        card('probe_deviation','Зонди · відхилення від середнього вибірки',"""SELECT p.probe_id,p.provider_name,p.avg_rtt_ms,n.avg_rtt_ms AS network_rtt_ms,
p.avg_rtt_ms-n.avg_rtt_ms AS deviation_ms,p.packet_loss_pct,p.measurement_count,p.period_start
FROM analytics.probes_hourly p INNER JOIN analytics.network_hourly n ON p.period_start=n.period_start AND p.measurement_id=n.measurement_id
WHERE p.measurement_id={{measurement}} AND p.avg_rtt_ms IS NOT NULL
AND p.period_start=(SELECT max(period_start) FROM analytics.network_hourly WHERE measurement_id={{measurement}})
ORDER BY deviation_ms DESC LIMIT 20""",description='Порівняння з вибіркою тієї самої цілі. Це аналітичне відхилення, не baseline-правило HIGH_RTT.',measurement=True),
    ]
    ops=[
        card('open_episodes','Відкритих епізодів',"SELECT count(*) AS value FROM reporting.incidents WHERE resolved_at IS NULL",'scalar','pg','Один episode_id рахується один раз; включає проблеми свіжості потоку.'),
        card('critical_open','Критичних відкритих епізодів',"SELECT count(*) AS value FROM reporting.incidents WHERE resolved_at IS NULL AND severity='critical'",'scalar','pg','Підозра за вибіркою не є доведеною аварією всього провайдера.'),
        card('episodes_daily','Нові епізоди за днями',"SELECT day AS period_start,incident_type AS series,sum(incident_count) AS value FROM reporting.incidents_daily GROUP BY day,incident_type ORDER BY day,incident_type",'bar','pg','Час початку епізоду. Тривала аварія не додається щодня як нова.'),
        card('incident_log','Журнал інцидентів та відновлень',"SELECT started_at,incident_type,severity,incident_status,probe_id,provider_asn,measurement_id,ip_version,resolved_at,notification_status FROM reporting.incidents ORDER BY started_at DESC LIMIT 100",source='pg',description='Початок, остання критичність, відновлення й стан сповіщення. Telegram-доставка перевіряється окремо.'),
        card('observed_duration','Завершені епізоди · спостережувана тривалість',"SELECT incident_type,count(*) AS episodes,round(avg(extract(epoch FROM(resolved_at-started_at)))/60.0,2) AS mean_minutes FROM reporting.incidents WHERE resolved_at IS NOT NULL AND incident_type<>'PIPELINE_STALE' GROUP BY incident_type ORDER BY mean_minutes DESC",source='pg',description='Хвилини за спостереженнями. Це не гарантований час ремонту від фактичного початку аварії.'),
        card('processing_errors','Помилки обробки за годинами',"SELECT period_start,stage AS series,sum(rejected_events) AS value FROM reporting.processing_errors_hourly GROUP BY period_start,stage ORDER BY period_start,stage",'bar','pg','Час запису діагностики, тому розбір старої черги може давати поточний пік.'),
        card('error_reasons','Причини відхилення повідомлень',"SELECT stage,reason,sum(rejected_events) AS rejected_events FROM reporting.processing_errors_hourly GROUP BY stage,reason ORDER BY rejected_events DESC LIMIT 20",source='pg',description='Помилка валідації не означає аварію мережі.'),
        card('delivery_status','Доставка Telegram за днями',"SELECT day AS period_start,delivery_status AS series,delivery_count AS value FROM reporting.telegram_deliveries_daily ORDER BY day,delivery_status",'bar','pg','Одна доставка = один адресат. Expired означає прострочене повідомлення, не здорову мережу.'),
    ]
    return [
        dict(key='live',name='01 · Поточний стан мережі',description='Оновлення щохвилини. Дві цілі та два протоколи аналізуються окремо; карта і таблиця зондів залежать від вибраного measurement.',cards=live),
        dict(key='history',name='02 · Історія та провайдери',description='Завершені години за 48 год і постійна поденна історія. Новій системі потрібен час для першої фіналізації.',cards=history),
        dict(key='operations',name='03 · Інциденти та якість потоку',description='Відкриття/відновлення епізодів, діагностика й фактична доставка. Порожній журнал не є доказом здорової мережі: звіряйте свіжість.',cards=ops),
    ]
