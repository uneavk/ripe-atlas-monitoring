# Де знаходяться дані та як будувати графіки

## Дві схеми ClickHouse

`monitoring` — зберігання й обробка: сирі вимірювання, погодинні та поденні накопичувачі, довідники та службові маркери. Ці таблиці використовують збирач і детектор.

`analytics` — готові представлення для DBeaver і графіків. Views читають актуальні дані автоматично, не створюють їхніх додаткових копій і не потребують ручної заливки.

## IPv4 та IPv6

У сирій таблиці `monitoring.ping_results` поле `af=4` означає IPv4, `af=6` — IPv6. У погодинній і поденній таблицях таке саме поле. `msm_id` — номер вимірювання, а не версія IP.

У схемі `analytics` замість скорочень відображаються `ip_version` (IPv4/IPv6), `measurement_id` та `target_name`. Довідник `analytics.measurement_directory` пояснює всі чотири джерела:

| measurement_id | Ціль | ip_version |
|---|---|---|
| 1001 | K-root | IPv4 |
| 2001 | K-root | IPv6 |
| 1004 | F-root | IPv4 |
| 2004 | F-root | IPv6 |

Зонд може підтримувати лише один протокол. Відсутність IPv6-вимірювань не означає втрату IPv4 або доведену аварію IPv6. Довідник зондів містить окремі ASN для IPv4 та IPv6. У звітах `provider_asn` вибирається за протоколом конкретного вимірювання. ASN 0 позначений як невідомий.

## Представлення для користувача

| View у схемі analytics | Що показує |
|---|---|
| measurement_directory | Джерела, цілі, протоколи та інтервал вимірювань |
| probe_directory | Зонди, координати, статус Atlas, ASN за протоколами |
| measurements_live | Окремі вимірювання за останні 5 годин |
| network_5minutes / providers_5minutes | Живі KPI п’ятихвилинними інтервалами за останні 5 годин |
| network_hourly / network_daily | Мережеві KPI за ціллю та IP-версією |
| providers_hourly / providers_daily | KPI провайдера (ASN) за ціллю та IP-версією |
| probes_hourly / probes_daily | KPI окремого зонда за ціллю та IP-версією |
| *_kpi | Ті самі показники: один KPI на рядок, із назвою й одиницею |
| data_freshness | Час останнього вимірювання, давність, кількість зондів та стан надходження за кожним джерелом |
| probe_events_live | Події підключення та відключення, без штучного приписування їм IPv4/IPv6 |

Годинні views показують завершені години за останні 48 годин. Поденні — лише вже збережені поденні агрегати; вчорашній день з’являється після фіналізації о 04:00 за Києвом. Час `period_start` має тип DateTime із зоною Europe/Kyiv. Порядок рядків задає запит графіка, а не view.

## Налаштування графіків

| Графік | View | Вісь X | Вісь Y | Серії / фільтри |
|---|---|---|---|---|
| Затримка за годинами | network_hourly | period_start | avg_rtt_ms | target_name, ip_version |
| Втрати пакетів | network_hourly | period_start | packet_loss_pct | target_name, ip_version |
| Довгострокова динаміка | network_daily | period_start | avg_rtt_ms або packet_loss_pct | target_name, ip_version |
| Порівняння провайдерів | providers_hourly | period_start | packet_loss_pct | provider_name; обрати одну ціль та IP-версію |
| Кількість спостережуваних зондів | network_hourly | period_start | probes_observed | target_name, ip_version |
| Вимірювання без відповідей | network_hourly | period_start | no_reply_measurements | target_name, ip_version |
| Проблема конкретного зонда | probes_hourly | period_start | avg_rtt_ms / packet_loss_pct | probe_id, target_name, ip_version |
| Карта | measurements_live або probe_directory | longitude | latitude | probe_id; для live спершу обрати останній результат кожного зонда/цілі/IP |

Приклад готового запиту:

```sql
SELECT period_start, target_name, ip_version, avg_rtt_ms, packet_loss_pct
FROM analytics.network_hourly
ORDER BY period_start, target_name, ip_version;
```

У views немає стовпців формул. Числові KPI вже обчислені. NULL у RTT означає відсутність валідної відповіді, його не слід замінювати нулем. Порожній період не слід автоматично домальовувати нульовими втратами. `successful_measurements_pct` — частка серій із хоча б однією відповіддю, не відсоток населення з Інтернетом.

Не підсумовуйте відсотки або середні між рядками різних періодів/провайдерів. Оберіть відповідний готовий рівень агрегації. `probes_observed` рахується заново у кожному періоді; денний показник не є сумою годинних. Дві цілі й два протоколи навмисно залишаються окремими серіями.

У DBeaver: оновити підключення ClickHouse (Refresh), відкрити базу `analytics` → Views. Для оперативної перевірки джерел почати з `data_freshness`.

## PostgreSQL: окрема схема reporting

Вимірювання й мережеві KPI залишаються тільки у ClickHouse. Для операційних графіків PostgreSQL містить views `reporting.incidents`, `incidents_hourly`, `incidents_daily`, `processing_errors_hourly`, `telegram_deliveries_daily`. Тут можна побудувати кількість інцидентів за типом, причини відхилення записів і стан доставки повідомлень. `incidents` містить один рядок на епізод, із часом початку та останньою критичністю; повторні повідомлення не збільшують `incident_count`. Події відключення зонда без визначеного IP-протоколу позначені «Не застосовується».
