# Повне пояснення кінцевої аналітики

[Карта документації](../README.md) · [Схема й усі стовпці](DATABASE.md) · [Правила детектора](ARCHITECTURE.md)

## 1. Запитання, на які відповідає система

Чи надходять свіжі дані кожної цілі та IP-версії? Як змінюються RTT і втрати за 5 хвилин, годину й день? Чи проблема спільна для кількох ASN, обох цілей або одного протоколу? Які зонди потребують перевірки? Скільки нових епізодів зафіксовано та які відновилися? Чи є помилки конвеєра й чи доставлені повідомлення?

Аналітичні в’ю є джерелами трьох готових дашбордів Metabase: поточний стан, історія/провайдери та інциденти/якість потоку. 26 SQL-карток і візуальні налаштування збережені у bi/dashboards.py та bi/dashboard_spec.json. Bootstrap налаштовує інтерфейс автоматично. [Вхід і відтворення BI](SETUP.md#metabase).

## 2. Зерно рядка та рівні деталізації

| View | Один рядок широкої форми | Час |
|---|---|---|
| measurements_live | Серія одного зонда до measurement | measured_at, останні 5 годин |
| network_5minutes | 5 хв × measurement × IP-версія | period_start; поточний інтервал може бути неповним |
| providers_5minutes | Те саме × ASN | Останні 5 годин raw |
| network_hourly / network_daily | Година / день × measurement × IP-версія | Завершені години / збережені дні |
| providers_hourly / providers_daily | Те саме × ASN | Години — останні 48 годин, дні — безстроково |
| probes_hourly / probes_daily | Те саме × ASN × probe_id | Окремий зонд |
| *_kpi | Рядок широкого view × один kpi_code | Час відповідного періоду |

Hourly не показує незавершену поточну годину. Daily читає лише збережені поденні результати після фіналізації, а не домальовує поточний день. period_start в analytics має зону Europe/Kyiv. Ключі годин у сховищі — UTC; day — київська календарна дата. При переході літнього часу зберігайте timestamp із зоною: однакові текстові «03:00» можуть бути різними годинами.

## 3. Виміри групування

- measurement_id: 1001/2001 — K-root, 1004/2004 — F-root.
- target_name: назва цілі для легенди.
- ip_version: IPv4/IPv6; не змішувати їх у довільне середнє.
- provider_asn: ASN протоколу конкретного результату; 0 означає невідомий ASN.
- provider_name: підпис ASномер, а не комерційна назва оператора.
- probe_id: конкретний зонд; він може вимірювати кілька цілей.
- country_code: UA із довідника. Координати не є готовою класифікацією за областями.

Для порівняння провайдерів спочатку фіксуйте ціль і протокол. Для порівняння цілей обирайте однаковий час та враховуйте можливі відмінності наборів зондів. IPv4 та IPv6 можуть мати різні ASN того самого зонда.

## 4. Усі публічні мережеві KPI

| Код | Зміст | Одиниця | Розрахунок |
|---|---|---|---|
| measurement_count | Унікальні серії ping | шт. | COUNT raw або SUM(samples) |
| probes_observed | Різні зонди з результатами | зондів | DISTINCT за всім періодом |
| packets_sent | Надіслано пакетів | пакетів | SUM(sent) |
| packets_received | Отримано відповідей | пакетів | SUM(received) |
| packets_lost | Пакети без відповіді | пакетів | SUM(sent) − SUM(received) |
| packet_loss_pct | Частка втрачених пакетів | % | 100 × packets_lost / packets_sent |
| avg_rtt_ms | Середня RTT валідних серій | мс | SUM(rtt_sum) / SUM(rtt_count) |
| min_rtt_ms | Найменша валідна RTT | мс | MIN мінімумів серій |
| max_rtt_ms | Найбільша валідна RTT | мс | MAX максимумів серій |
| successful_measurements_pct | Серії хоча б з однією відповіддю | % | 100 × (серії − серії без відповідей) / серії |
| high_loss_measurements | Серії з loss>50% | шт. | Сума відповідного лічильника |
| no_reply_measurements | Серії з received=0 | шт. | Сума лічильника повної втрати |

Широкі hourly/daily містять цей набір. У широких п’ятихвилинних views немає окремих packets_lost і high_loss_measurements; є суми пакетів, відсоток втрат і no_reply_measurements. Довгі probes_*_kpi не повторюють probes_observed окремим KPI. Точні колонки кожного view наведені в довіднику БД.

Внутрішні rtt_sum/rtt_count зберігають чисельник і знаменник середнього, normal_rtt_sum/normal_rtt_count — статистики baseline. Це не додаткові готові середні. Повний каталог 25 внутрішніх і публічних кодів: [ANALYTICS.md](#kpi-catalog). Формули є в документації; у готових views формульних стовпців немає.

## 5. Приклади правильного агрегування

### Втрата пакетів — співвідношення сум

Перша серія: sent=3, received=0, loss=100%. Друга: sent=9, received=9, loss=0%. Разом втрачено 3 із 12 пакетів: правильне значення 25%. Середнє двох відсотків дало б неправильні 50%.

### RTT — середнє за валідними серіями

За першу годину є 100 серій зі середнім 10 мс, за другу — 1 серія 100 мс. День: (100×10+1×100)/101 ≈ 10,89 мс. Середнє двох годинних середніх 55 мс неправильне. Вага тут — кількість серій з валідним rtt_avg, а не кількість пакетів. Для точного середнього всіх окремих ICMP-відповідей потрібні інші достатні статистики.

### NULL не замінюється нулем

Серія без відповідей збільшує sent, втрати й no_reply_measurements, але не додає 0 мс до RTT. NULL означає відсутність валідного значення, а 0 означав би миттєву відповідь. Якщо всі серії без відповідей, avg_rtt_ms має бути NULL при loss=100%.

### DISTINCT не підсумовується

У першій годині є зонди A і B, у другій B і C. За годинами — 2 та 2, за днем — 3, не 4. Так само не можна додавати probes_observed між цілями: один зонд вимірює кілька цілей.

### Успішна серія може мати великі втрати

Якщо з трьох пакетів отримано один, серія має відповідь та рахується успішною, але loss=66,67%. successful_measurements_pct і packet_loss_pct відповідають на різні запитання. Перший не є часткою часу доступності чи відсотком населення з Інтернетом.

## 6. Перевірка свіжості та повноти

```sql
SELECT measurement_id, target_name, ip_version, latest_measurement_at,
       data_age_seconds, measurements_last_5h, probes_observed_last_5h, data_status
FROM analytics.data_freshness
ORDER BY measurement_id;
```

Без raw за 5 годин показується «Немає даних» і NULL замість дати. Якщо останній результат старший 900 секунд — «Дані застаріли», інакше «Дані надходять». Використовується час самої події, тому під час розбору backlog статус може бути застарілим. Враховуються і stream, і backfill: це не окремий heartbeat WebSocket.

Свіжий останній результат не доводить повноту вибірки. Система не має повної моделі очікуваних активних зондів для кожного measurement. probes_observed — фактичне спостережуване покриття, а не гарантований відсоток від очікуваного.

## 7. Кінцевий набір панелей дашборда

[Повний довідник 3 дашбордів та всіх 26 фактично налаштованих карток](#dashboard-cards) містить джерела даних, тип кожної візуалізації, фільтри й пояснення. Нижче - принципи групування панелей та приклади SQL.

| Панель | Джерело | X / категорія | Y | Серії / фільтри |
|---|---|---|---|---|
| Свіжість | data_freshness | target_name + ip_version | data_age_seconds | measurement_id |
| Поточна затримка | network_5minutes | period_start | avg_rtt_ms | ціль + протокол |
| Поточні втрати | network_5minutes | period_start | packet_loss_pct | ціль + протокол |
| Погодинний тренд | network_hourly | period_start | avg_rtt_ms / packet_loss_pct | ціль + протокол |
| Поденний тренд | network_daily | period_start | avg_rtt_ms / packet_loss_pct | ціль + протокол |
| Провайдери | providers_hourly | period_start | packet_loss_pct | provider_name; одна ціль й AF |
| Покриття | network_hourly | period_start | probes_observed | ціль + протокол |
| Повна втрата | network_hourly | period_start | no_reply_measurements | ціль + протокол |
| Конкретний зонд | probes_hourly | period_start | avg_rtt_ms / packet_loss_pct | probe_id, ціль, AF |
| Карта | measurements_live | longitude, latitude | Колір loss/RTT | Остання серія на зонд/ціль/AF |
| Нові інциденти | reporting.incidents_daily | day | incident_count | тип, AF |
| Помилки конвеєра | reporting.processing_errors_hourly | period_start | rejected_events | stage, reason |
| Доставка | reporting.telegram_deliveries_daily | day | delivery_count | delivery_status |

RTT у мс і втрати у % краще показувати на окремих панелях. При високих втратах низьке середнє RTT може стосуватися лише небагатьох успішних відповідей; одночасно показуйте sent/received і кількість серій. Графік серій без відповідей не дорівнює графіку унікальних аварій.

## 8. Готові SQL-запити ClickHouse

### Порівняння цілей та протоколів

```sql
SELECT period_start, target_name, ip_version, avg_rtt_ms,
       packet_loss_pct, measurement_count, probes_observed
FROM analytics.network_hourly
ORDER BY period_start, target_name, ip_version;
```

### Провайдери для K-root IPv4

```sql
SELECT period_start, provider_name, avg_rtt_ms, packet_loss_pct, probes_observed
FROM analytics.providers_hourly
WHERE measurement_id = 1001
ORDER BY period_start, provider_name;
```

### Рейтинг останньої завершеної години

```sql
SELECT provider_asn, provider_name, packet_loss_pct, avg_rtt_ms, probes_observed
FROM analytics.providers_hourly
WHERE measurement_id = 1001
  AND period_start = (
    SELECT max(period_start)
    FROM analytics.providers_hourly WHERE measurement_id = 1001
  )
  AND probes_observed >= 4
ORDER BY packet_loss_pct DESC;
```

Поріг 4 у запиті — фільтр розміру вибірки, а не зміна детектора. Низький loss при одному зонді не доводить кращу якість усього ASN.

### Поденний IPv6

```sql
SELECT period_start, target_name, avg_rtt_ms, packet_loss_pct,
       successful_measurements_pct, probes_observed
FROM analytics.network_daily
WHERE ip_version = 'IPv6'
ORDER BY period_start, target_name;
```

### Довга форма однієї метрики

```sql
SELECT period_start, target_name, ip_version, kpi_name, unit, value
FROM analytics.network_hourly_kpi
WHERE kpi_code = 'packet_loss_pct'
ORDER BY period_start, target_name, ip_version;
```

Широка й довга форми представляють ті самі розрахунки. Їхній JOIN для підсумовування може помножити рядки на кількість KPI. Не додавайте середні та відсотки з довільних груп: обирайте потрібний готовий рівень.

### Карта останніх втрат

```sql
SELECT probe_id, target_name, ip_version,
       argMax(latitude, measured_at) AS latitude,
       argMax(longitude, measured_at) AS longitude,
       argMax(packet_loss_pct, measured_at) AS packet_loss_pct,
       max(measured_at) AS last_measured_at
FROM analytics.measurements_live
GROUP BY probe_id, target_name, ip_version;
```

Для RTT враховуйте NULL: простий argMax(nullable RTT,time) може пропускати NULL і показати стару успішну відповідь замість останньої серії. Не відображайте такий результат як гарантовано поточний.

## 9. Операційна аналітика PostgreSQL

reporting.incidents містить один рядок на episode_id: перший час початку та останній контекст/критичність. Після ескалації групування історії за severity може уточнитися. Первісні події зберігаються в monitoring_incidents.

```sql
SELECT day, incident_type, ip_version, measurement_id, incident_count
FROM reporting.incidents_daily ORDER BY day, incident_type;

SELECT started_at, incident_type, severity, incident_status,
       probe_id, provider_asn, measurement_id, ip_version, resolved_at
FROM reporting.incidents ORDER BY started_at DESC;
```

incident_count показує нові епізоди за часом початку, а не число активних інцидентів у кожну годину. Для активних на момент T потрібне окреме розгортання інтервалів started_at…resolved_at; готове hourly-view цього не виконує. Тривалий збій через північ не додається щодня як новий.

```sql
SELECT kind, count(*) AS completed_episodes,
       avg(duration_seconds) AS mean_observed_duration_seconds
FROM public.incident_history_metrics
WHERE resolved_at IS NOT NULL
  AND kind IN ('HIGH_RTT','PACKET_LOSS','PROBE_DOWN','ASN_OUTAGE','REGION_OUTAGE')
GROUP BY kind;
```

Це середня спостережувана тривалість завершених епізодів, не гарантований MTTR від фактичної аварії до ремонту. Виявлення залежить від інтервалу й підтвердження. Незавершені епізоди не мають нульової тривалості.

```sql
SELECT period_start, stage, reason, rejected_events
FROM reporting.processing_errors_hourly ORDER BY period_start;

SELECT day, delivery_status, delivery_count
FROM reporting.telegram_deliveries_daily ORDER BY day, delivery_status;
```

Діагностика групується за часом її запису, тому читання старого DLQ може створити поточний пік. Telegram-графік групується за датою створення outbox; стани можуть пізніше змінитися. Один епізод із трьома адресатами дає три доставки, не три аварії.

## 10. Інтерпретація ситуацій

| Спостереження | Допустимий висновок | Наступна перевірка |
|---|---|---|
| Одна ціль гірша у багатьох ASN | Можлива проблема цілі/спільного маршруту | Друга ціль, AF, покриття й свіжість |
| Обидві цілі гірші в одному ASN | Сильніший сигнал проблеми шляхів цієї вибірки | Кількість зондів та інші ASN |
| IPv6 гірший за IPv4 | Відмінність виміряних шляхів протоколів | ASN і набори зондів можуть відрізнятися |
| Менше probes_observed | Зменшилась вибірка | Collector, Kafka/NiFi, RIPE та час |
| Немає інцидентів, дані старі | Немає свіжого підтвердження стану | Перевірити конвеєр |
| RTT низький, loss високий | Частина відповідей швидка, частина відсутня | Кількість відповідей і кілька серій |
| PROBE_DOWN | Відомий стан Atlas потребує перевірки | Останній connect/ping, не весь ASN |

Детектор розділяє масові ping-підозри за measurement та AF, але автоматично не доводить одночасну проблему обох цілей. Кореляція цілей — окремий висновок за графіками.

## 11. Межі кінцевої аналітики

Поточні дані не дають точного відсотка населення/абонентів без Інтернету, повної доступності всіх сервісів провайдера або областей без додаткового довідника. Старі денні суми не дозволяють відновити точні p95/p99, медіану, jitter чи розподіл пакетних RTT — відповідні агрегатні стани не збережено. Частка успішних серій не є безперервною часовою availability. Порожня година не означає нульові втрати.

## 12. Перевірка перед демонстрацією

Перевірити свіжість чотирьох джерел і кількість зондів. Обрати один measurement, порівняти hourly з кількома raw-серіями, пояснити loss через суми та RTT через валідні серії. Відкрити один episode_id і окремі доставки. Виконати `python tools/verify_analytics_views.py`: він перевіряє запити й наявні денні підсумки; у новій системі перевірених поденних груп може бути 0.


<a id="view-guide"></a>

## Відповідність в’ю та осям графіків

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

<!-- GENERATED_KPI_BEGIN -->

<a id="kpi-catalog"></a>

## Повний словник внутрішніх KPI

Внутрішні коди зберігаються в monitoring.kpi_dictionary. Публічні назви колонок analytics пояснені вище. Формули є в документації, а готові в’ю містять числові значення.

| Код | Назва | Одиниця | Агрегація | Формула | Пояснення |
|---|---|---|---|---|---|
| samples | Кількість вимірювань | шт. | COUNT → SUM | Кількість унікальних ping-вимірювань; день = сума годин | Одне вимірювання — одна серія ping, а не один пакет. |
| sent | Надіслано пакетів | пакетів | SUM | SUM(sent) | Сумарна кількість надісланих пакетів. |
| received | Отримано пакетів | пакетів | SUM | SUM(received) | Кількість відповідей на надіслані пакети. |
| packets_lost | Втрачено пакетів | пакетів | SUM / різниця сум | SUM(sent) − SUM(received) | Не усереднюється. |
| packet_loss_pct | Втрата пакетів | % | Відношення сум | 100 × (SUM(sent) − SUM(received)) / SUM(sent) | Зважено кількістю пакетів; не AVG погодинних відсотків. |
| avg_rtt_ms | Середня затримка вимірювань | мс | Зважене AVG | SUM(rtt_sum) / SUM(rtt_count) | Кожна серія з коректним rtt_avg має однакову вагу. Години зважуються кількістю таких серій, а не кількістю пакетів. |
| min_rtt_ms | Мінімальна затримка | мс | MIN | MIN(rtt_min) | Мінімум із мінімумів серій; день = MIN годин. |
| max_rtt_ms | Максимальна затримка | мс | MAX | MAX(rtt_max) | Максимум із максимумів серій; день = MAX годин. |
| measurement_success_pct | Вимірювання з відповіддю | % | Відношення сум | 100 × (SUM(samples) − SUM(full_loss_samples)) / SUM(samples) | Частка серій із хоча б однією відповіддю; не доступність усіх зондів провайдера. |
| loss_samples | Вимірювання з великими втратами | шт. | COUNT IF → SUM | COUNT(серії з втратою > 50%) | День = сума погодинних кількостей. |
| full_loss_samples | Вимірювання без відповідей | шт. | COUNT IF → SUM | COUNT(серії з received = 0) | Повна втрата пакетів у серії. |
| observed_probes | Спостережувані зонди | зондів | COUNT DISTINCT | COUNT(DISTINCT probe_id) у відповідному періоді | Для дня кількість рахується заново за зондами, а не сумою погодинних кількостей. |
| connects | Підключення зондів | подій | COUNT IF → SUM | COUNT(connect або connected) | Події зміни статусу, окремо від ping. |
| disconnects | Відключення зондів | подій | COUNT IF → SUM | COUNT(disconnect, disconnected або down) | Кількість подій, не тривалість простою. |
| rtt_sum | Сума середніх затримок серій | мс | SUM | SUM(rtt_avg для серій із відповіддю) | Службовий чисельник для середнього; сам по собі не є середньою затримкою. |
| rtt_count | Вимірювання з коректною RTT | шт. | COUNT IF → SUM | COUNT(rtt_avg IS NOT NULL) | Службовий знаменник середньої RTT; серія без відповіді не вносить нуль. |
| rtt_min | Внутрішній мінімум RTT | мс | MIN | MIN(rtt_min) | Внутрішня назва поля, що видається як min_rtt_ms. |
| rtt_max | Внутрішній максимум RTT | мс | MAX | MAX(rtt_max) | Внутрішня назва поля, що видається як max_rtt_ms. |
| normal_rtt_sum | Сума затримок для історичної норми | мс | SUM IF | SUM(rtt_avg за втрат ≤ 50% та RTT > 0) | Службовий чисельник baseline. |
| normal_rtt_count | Вимірювання для історичної норми | шт. | COUNT IF → SUM | COUNT(втрати ≤ 50% та RTT > 0) | Службовий знаменник baseline. |
| baseline_rtt_ms | Історична норма затримки | мс | Зважене AVG | SUM(normal_rtt_sum) / SUM(normal_rtt_count) | Окремо за зондом, вимірюванням і IP-протоколом; приблизно 24 год, остання хвилина виключена. |
| incidents | Кількість інцидентів | інцидентів | COUNT | COUNT унікальних incident_id за період | Групування також за типом і критичністю. |
| rtt_avg | Середня RTT однієї серії | мс | AVG усередині серії | Середнє коректних відповідей у одному RIPE вимірюванні | Назва в сирих подіях; у звітах середнє багатьох серій має код avg_rtt_ms. |
| loss_pct | Втрата пакетів однієї серії | % | Відношення | 100 × (sent − rcvd) / sent | Назва в сирих подіях; у звітах packet_loss_pct обчислюється з сум. |
| rcvd | Отримано пакетів у сирій серії | пакетів | SUM | Кількість відповідей у серії | У звітах це поле перейменовано на received. |

## Назви внутрішніх вимірів

| Поле | Назва |
|---|---|
| probe_id | Ідентифікатор зонда |
| prb_id | Ідентифікатор зонда у сирих подіях |
| msm_id | Ідентифікатор RIPE-вимірювання / цілі |
| af | Версія IP: 4 або 6; 0 — події статусу |
| asn | Номер автономної системи провайдера |
| hour_start | Початок години в UTC — унікальний ключ |
| local_hour | Година для відображення за Києвом |
| day | Календарна дата за Києвом |
| event_time | Час події в UTC |
| period_label | Назва конкретної години або дня |
| period_name_uk | Тип періоду українською |
| kpi_name_uk | Зрозуміла назва KPI українською |
| kpi_value | Числове значення KPI |
| source_mode | Джерело: живий потік або історія |

<!-- GENERATED_KPI_END -->

<!-- GENERATED_DASHBOARDS_BEGIN -->

<a id="dashboard-cards"></a>

## Кожна картка Metabase

Специфікація: [bi/dashboards.py](../bi/dashboards.py). Переносимий експорт: [bi/dashboard_spec.json](../bi/dashboard_spec.json). Локальні ID залежать від інсталяції.

Фільтр measurement: 1001 K-root IPv4, 2001 K-root IPv6, 1004 F-root IPv4, 2004 F-root IPv6. Він впливає тільки на картки з параметром. Порівняльні графіки залишають чотири серії.

### 01 · Поточний стан мережі

Оновлення щохвилини. Дві цілі та два протоколи аналізуються окремо; карта і таблиця зондів залежать від вибраного measurement.

#### `freshness` - Свіжість чотирьох джерел

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.data_freshness` |
| Відображення | Таблиця |
| Фільтр measurement | Ні |

Давність >15 хв означає застарілі дані. Під час backfill стан може тимчасово бути застарілим.

#### `ipv4_probes` - Зондів IPv4 · останні 15 хв

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurements_live` |
| Відображення | Одне число |
| Фільтр measurement | Ні |

DISTINCT між обома цілями: зонд рахується один раз.

#### `ipv6_probes` - Зондів IPv6 · останні 15 хв

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurements_live` |
| Відображення | Одне число |
| Фільтр measurement | Ні |

Менша вибірка IPv6 не означає автоматично проблему IPv6.

#### `series_15m` - Серій ping · останні 15 хв

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurements_live` |
| Відображення | Одне число |
| Фільтр measurement | Ні |

Серія містить декілька пакетів. Це кількість результатів, не пакетів.

#### `live_rtt` - Затримка · мс

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurement_directory`, `analytics.network_5minutes` |
| Відображення | Лінійний графік |
| Фільтр measurement | Ні |

Середнє валідних RTT серій; NULL без відповідей. Кожна ціль та IP-версія — окрема лінія. Розриви ліній означають відсутні спостереження, не нуль.

#### `live_loss` - Втрати пакетів · %

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurement_directory`, `analytics.network_5minutes` |
| Відображення | Лінійний графік |
| Фільтр measurement | Ні |

Втрата зі співвідношення сум пакетів. Останній 5-хвилинний інтервал може бути неповним. Розриви ліній означають відсутні спостереження, не нуль.

#### `live_probes` - Покриття · різні зонди

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurement_directory`, `analytics.network_5minutes` |
| Відображення | Лінійний графік |
| Фільтр measurement | Ні |

Різні зонди кожної цілі/AF у періоді. Це не відсоток населення. Розриви ліній означають відсутні спостереження, не нуль.

#### `live_success` - Серії з відповіддю · %

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurement_directory`, `analytics.network_5minutes` |
| Відображення | Лінійний графік |
| Фільтр measurement | Ні |

Хоча б один отриманий пакет робить серію успішною; це не часова availability. Розриви ліній означають відсутні спостереження, не нуль.

#### `probe_map` - Карта останніх втрат · обране вимірювання

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurements_live` |
| Відображення | Карта |
| Фільтр measurement | Так |

Остання серія на зонд. Оберіть measurement: 1001 K-root IPv4; 2001 K-root IPv6; 1004 F-root IPv4; 2004 F-root IPv6.

#### `latest_loss` - Зонди з найбільшими поточними втратами

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurements_live` |
| Відображення | Таблиця |
| Фільтр measurement | Так |

Останній результат, а не підтверджений інцидент. Перевірте повтори в журналі інцидентів.

### 02 · Історія та провайдери

Завершені години за 48 год і постійна поденна історія. Новій системі потрібен час для першої фіналізації.

#### `hour_rtt` - Завершені години · затримка, мс

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurement_directory`, `analytics.network_hourly` |
| Відображення | Лінійний графік |
| Фільтр measurement | Ні |

48 годин. Поточна незавершена година не показується. Розриви ліній означають відсутні спостереження, не нуль.

#### `hour_loss` - Завершені години · втрати, %

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurement_directory`, `analytics.network_hourly` |
| Відображення | Лінійний графік |
| Фільтр measurement | Ні |

Зважені packet-loss KPI, окремо за ціллю та AF. Розриви ліній означають відсутні спостереження, не нуль.

#### `day_rtt` - Поденна історія · затримка, мс

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurement_directory`, `analytics.network_daily` |
| Відображення | Лінійний графік |
| Фільтр measurement | Ні |

Зважене середнє за кількістю валідних серій. Доба фіналізується після 04:00 за Києвом. Розриви ліній означають відсутні спостереження, не нуль.

#### `day_loss` - Поденна історія · втрати, %

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurement_directory`, `analytics.network_daily` |
| Відображення | Лінійний графік |
| Фільтр measurement | Ні |

Дні з відсутніми спостереженнями не підміняються нульовими втратами. Розриви ліній означають відсутні спостереження, не нуль.

#### `day_probes` - Поденне покриття · зонди

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.measurement_directory`, `analytics.network_daily` |
| Відображення | Лінійний графік |
| Фільтр measurement | Ні |

DISTINCT за днем, а не сума годинних кількостей. Розриви ліній означають відсутні спостереження, не нуль.

#### `asn_rank` - Провайдери · остання завершена година

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.providers_hourly` |
| Відображення | Таблиця |
| Фільтр measurement | Так |

Не менше 4 спостережуваних зондів; рейтинг тільки одного measurement. ASN — не завжди комерційна назва провайдера.

#### `asn_trend` - Провайдери · погодинні втрати, %

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.providers_hourly` |
| Відображення | Лінійний графік |
| Фільтр measurement | Так |

До 8 ASN із найбільшою кількістю вимірювань; середні відсотки повторно не агрегуються.

#### `probe_deviation` - Зонди · відхилення від середнього вибірки

| Властивість | Значення |
|---|---|
| Сховище | ClickHouse |
| Джерела | `analytics.network_hourly`, `analytics.probes_hourly` |
| Відображення | Таблиця |
| Фільтр measurement | Так |

Порівняння з вибіркою тієї самої цілі. Це аналітичне відхилення, не baseline-правило HIGH_RTT.

### 03 · Інциденти та якість потоку

Відкриття/відновлення епізодів, діагностика й фактична доставка. Порожній журнал не є доказом здорової мережі: звіряйте свіжість.

#### `open_episodes` - Відкритих епізодів

| Властивість | Значення |
|---|---|
| Сховище | PostgreSQL |
| Джерела | `reporting.incidents` |
| Відображення | Одне число |
| Фільтр measurement | Ні |

Один episode_id рахується один раз; включає проблеми свіжості потоку.

#### `critical_open` - Критичних відкритих епізодів

| Властивість | Значення |
|---|---|
| Сховище | PostgreSQL |
| Джерела | `reporting.incidents` |
| Відображення | Одне число |
| Фільтр measurement | Ні |

Підозра за вибіркою не є доведеною аварією всього провайдера.

#### `episodes_daily` - Нові епізоди за днями

| Властивість | Значення |
|---|---|
| Сховище | PostgreSQL |
| Джерела | `reporting.incidents_daily` |
| Відображення | Стовпчиковий графік |
| Фільтр measurement | Ні |

Час початку епізоду. Тривала аварія не додається щодня як нова.

#### `incident_log` - Журнал інцидентів та відновлень

| Властивість | Значення |
|---|---|
| Сховище | PostgreSQL |
| Джерела | `reporting.incidents` |
| Відображення | Таблиця |
| Фільтр measurement | Ні |

Початок, остання критичність, відновлення й стан сповіщення. Telegram-доставка перевіряється окремо.

#### `observed_duration` - Завершені епізоди · спостережувана тривалість

| Властивість | Значення |
|---|---|
| Сховище | PostgreSQL |
| Джерела | `reporting.incidents` |
| Відображення | Таблиця |
| Фільтр measurement | Ні |

Хвилини за спостереженнями. Це не гарантований час ремонту від фактичного початку аварії.

#### `processing_errors` - Помилки обробки за годинами

| Властивість | Значення |
|---|---|
| Сховище | PostgreSQL |
| Джерела | `reporting.processing_errors_hourly` |
| Відображення | Стовпчиковий графік |
| Фільтр measurement | Ні |

Час запису діагностики, тому розбір старої черги може давати поточний пік.

#### `error_reasons` - Причини відхилення повідомлень

| Властивість | Значення |
|---|---|
| Сховище | PostgreSQL |
| Джерела | `reporting.processing_errors_hourly` |
| Відображення | Таблиця |
| Фільтр measurement | Ні |

Помилка валідації не означає аварію мережі.

#### `delivery_status` - Доставка Telegram за днями

| Властивість | Значення |
|---|---|
| Сховище | PostgreSQL |
| Джерела | `reporting.telegram_deliveries_daily` |
| Відображення | Стовпчиковий графік |
| Фільтр measurement | Ні |

Одна доставка = один адресат. Expired означає прострочене повідомлення, не здорову мережу.

Поточне вікно - до 5 годин, завершені години - 48 годин. Поденні графіки обмежують запит останнім роком, а денні підсумки в БД зберігаються безстроково. Нове встановлення починає без попередніх вимірювань. Скріншоти artifacts датовані 09.11.2026.

<!-- GENERATED_DASHBOARDS_END -->
