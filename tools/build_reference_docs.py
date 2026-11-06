"""Build complete file and schema references from versioned metadata."""
from pathlib import Path
import ast,json,subprocess
ROOT=Path(__file__).resolve().parents[1]

FILES={
'.env.example':'Шаблон адрес, портів і користувачів. Містить лише заглушки паролів. Bootstrap копіює його в локальний .env і генерує випадкові паролі.',
'.gitattributes':'Задає LF для текстових файлів і правила для двійкових зображень, щоб Windows та Linux однаково читали код.',
'.gitignore':'Виключає .env, секрети, локальні БД, журнали, кеші та томи з публікації Git.',
'.github/workflows/tests.yml':'GitHub Actions: після push або pull request встановлює Python 3.12, залежності, перевіряє компіляцію й виконує модульні тести.',
'README.md':'Головна сторінка: призначення, схема роботи, карта документації, короткий запуск і посилання на повні довідники.',
'compose.yaml':'Опис усіх Docker-сервісів, залежностей, мережі, портів, перевірок готовності та іменованих томів. Одноразовий kafka-init створює теми.',
'collector/.dockerignore':'Виключає кеші, локальний стан і секрети з контексту збірки образу Python.',
'collector/Dockerfile':'Будує спільний Python-образ для collector, analytics та alerts. Копіює код і тести, встановлює залежності, запускає процеси від користувача collector.',
'collector/requirements.txt':'Фіксує прямі залежності: kafka-python для Kafka, psycopg для PostgreSQL, requests для REST/HTTP і websocket-client для потоку RIPE.',
'collector/app/__init__.py':'Позначає каталог app як Python-пакет; самостійного сервісу не запускає.',
'collector/app/config.py':'Зчитує параметри середовища: країну, вимірювання, backfill, Kafka, checkpoint і рівень журналювання. Містить адреси RIPE API та межі reconnect.',
'collector/app/main.py':'Точка входу збирача. Завантажує довідник, перевіряє джерела, виконує REST-backfill, слухає WebSocket, фільтрує UA, публікує Kafka-повідомлення та відхилення. Checkpoint змінюється після завершеного REST-діапазону.',
'collector/app/ripe_client.py':'Клієнт RIPE: пагінація зондів, перевірка measurement, REST-запити 5-хвилинними частинами та підписки WebSocket. Некоректні JSON/envelope передає обробнику помилок.',
'collector/app/models.py':'Нормалізація ping і статусів, розрахунок loss, стабільні SHA-256 event_id, перевірка ідентифікаторів, AF, пакетів і RTT. При rcvd=0 очищує RTT до NULL.',
'collector/app/kafka_io.py':'Синхронний Kafka producer: acks=all, gzip, повтори та очікування підтвердження. Ключ повідомлення — probe ID або event ID.',
'collector/app/checkpoint.py':'Зберігає позиції завершеного backfill за measurement ID у JSON-файлі Docker-тому. Оновлює файл атомарною заміною; PostgreSQL не використовує.',
'collector/app/logging_config.py':'Налаштовує структуровані JSON-журнали: час, рівень, компонент, тип події та контекст обробки.',
'collector/app/retention.py':'Сумісна точка входу, що перенаправляє до retention_clickhouse. Це не другий обробник і не PostgreSQL-агрегація.',
'collector/app/retention_clickhouse.py':'HTTP-шлюз запису в ClickHouse. Валідує та дедуплікує записи, об’єднує HTTP-запити в пакети, веде короткий журнал незавершеної операції, оновлює години, фіналізує дні й очищує старі дані.',
'collector/app/kpi_catalog.py':'Семантичний каталог 25 кодів KPI та 14 полів: назви, одиниці, пояснення й правила розрахунку. Формули в коді/документації не є стовпцями готових в’ю.',
'collector/app/install_kpi.py':'Створює або оновлює словники ClickHouse та чотири сумісні довгі KPI-в’ю monitoring. Прибирає колонки formula_uk та aggregation із таблиці словника.',
'collector/app/analytics_views.py':'Генерує 20 користувацьких в’ю analytics: довідники, live, 5 хвилин, години, дні, зрізи мережі/ASN/зонда та свіжість. Тут визначені чотири measurement ID і зрозумілі назви полів.',
'collector/app/alert_rules.py':'Чисті правила детекції та форматування повідомлень. Не записує БД і не звертається до Telegram. Отримує готовий зріз і повертає Incident.',
'collector/app/incident_state.py':'Операційна схема, ключ епізоду та правила відновлення. Відсутність даних не вважається відновленням. Зберігає актуальний стан окремо від історії подій.',
'collector/app/alerts.py':'Цикл детектора: читає дані та baseline з ClickHouse, веде епізоди в PostgreSQL, приймає команди Telegram і запускає доставку. Підтримує --once для одного циклу.',
'collector/app/pipeline_errors.py':'Окремий Kafka consumer ripe.dead_letter. Після запису діагностики в PostgreSQL підтверджує offset; унікальний ключ topic/partition/offset захищає від повторів.',
'collector/app/telegram_sender.py':'HTTP-транспорт Telegram: виклики Bot API, HTML-повідомлення, повернення message_id, розбір помилок і retry_after. При помилці не виводить URL із токеном.',
'collector/app/telegram_subscriptions.py':'Обробляє /start, /stop, /status, /help у приватних чатах. Веде offsets команд, черги відповідей і доставки кожному підписнику; обробляє блокування, 429 та закінчення строку повідомлень.',
'collector/app/operational_views.py':'Створює 5 в’ю reporting у PostgreSQL. Формує один рядок на епізод, підсумки інцидентів, помилок та доставки.',
'collector/tests/test_models.py':'Перевіряє нормалізацію, відсоток втрат, стабільність event ID і події статусів.',
'collector/tests/test_alerts.py':'Перевіряє пороги й підтвердження аномалій, групування за ASN/AF, знаменники вибірки та транспорт Telegram на підставних відповідях.',
'collector/tests/test_audit_fixes.py':'Регресійні сценарії: повна втрата без RTT, тривалий disconnect, відновлення лише за новими даними, свіжість та відокремлення епізодів.',
'collector/tests/test_clickhouse_store.py':'Підставне сховище перевіряє повтор після часткового запису, відсутність подвійного підрахунку, накопичення статистик і відхилення старих даних.',
'collector/tests/test_clickhouse_daily.py':'Підставне сховище перевіряє добове згортання, порядок збереження й очищення та повтор після помилки запису дня.',
'collector/tests/test_retention.py':'Перевіряє межу 04:00 Europe/Kyiv, перехід літнього часу, часові ключі, NULL RTT і валідність пакетів.',
'collector/tests/test_subscriptions.py':'Перевіряє дозволені Telegram-команди та приватний характер підписки без реальних повідомлень.',
'clickhouse/init/001_schema.sql':'Первинні сирі таблиці ping_results і probe_events, їхні типи, сортування й версії.',
'clickhouse/init/002_analytics.sql':'Погодинні/поденні накопичувачі та початкові сумісні views. Автоматичний TTL не застосовується: порядок очищення контролює обробник.',
'clickhouse/init/003_reporting.sql':'Довідник зондів і сумісні live, country та activity views у monitoring.',
'clickhouse/init/004_clickhouse_only.sql':'Таблиця службових маркерів retention_runs і два materialized view, що фіксують факт вставки.',
'clickhouse/migrations/006_analytics_views.sql':'SQL-знімок визначень analytics для ручного перегляду/міграції. Чинний генератор — app.analytics_views; bootstrap використовує саме його.',
'postgres/init/001_schema.sql':'Навмисно мінімальний файл: фіксує, що вимірювання й довідник більше не створюються в PostgreSQL.',
'postgres/init/002_alerts.sql':'Базові інциденти, cooldown та outbox Telegram зі зв’язками й індексами.',
'postgres/init/003_telegram_subscriptions.sql':'Підписники, позиція getUpdates, відповіді на команди та доставки кожному адресату.',
'postgres/init/004_incident_state.sql':'Стан епізодів і підключення, зв’язок подій з епізодом, діагностика обробки та внутрішні операційні views.',
'postgres/migrations/008_reporting_views.sql':'SQL-знімок п’яти reporting-в’ю. Чинний генератор — app.operational_views.',
'nifi/api_client.py':'Локальний REST-клієнт NiFi. Знаходить контейнер і опублікований порт через Compose, читає налаштовані облікові дані з Docker, чекає готовності й отримує тимчасовий JWT без друку секретів.',
'nifi/build_pipeline.py':'Відтворює 11 процесорів і зв’язки. Налаштовує Kafka, Groovy-перевірки, HTTP sinks та відхилення; при повторі тимчасово зупиняє власні процесори й відновлює роботу.',
'tools/bootstrap.py':'Основна команда першого запуску. Створює локальні паролі, перевіряє Compose, збирає один спільний образ, запускає стек, налаштовує NiFi та обидва шари в’ю.',
'tools/configure_telegram.py':'Приховано запитує токен і записує його тільки в .secrets/telegram/config.json. Сам не надсилає повідомлень і не перевіряє токен через мережу.',
'tools/check_publication.py':'Перевіряє тільки файли, які відстежує Git: шукає типові токени, приватні ключі, локальні шляхи та файли стану. Не є заміною повного аудиту секретів.',
'tools/export_kpi_dictionary.py':'Оновлює Markdown та CSV-словник із app.kpi_catalog. CSV містить назви й пояснення; докладні формули залишаються в Markdown.',
'tools/verify_analytics_views.py':'Виконує SELECT до 20 analytics-в’ю, перевіряє відсутність формульних колонок і звіряє поденні суми, DISTINCT та зважені середні зі сховищем. На хості делегує перевірку Docker.',
'tools/export_schema_reference.py':'Зчитує лише метадані таблиць, в’ю, стовпців і обмежень із запущених БД та зберігає docs/schema_reference.json; рядки прикладних даних не експортує.',
'tools/build_reference_docs.py':'Будує цей пофайловий довідник і докладний каталог БД із версійованого JSON метаданих. Перевіряє, щоб кожен файл та кожна назва поля мали пояснення.',
'docs/ANALYTICS_GUIDE.md':'Коротка практична карта в’ю та відповідність полів осям графіків.',
'docs/CONNECTIONS.md':'Параметри DBeaver, JDBC, Docker DNS, доступ з іншого ПК, томи та типові проблеми підключення.',
'docs/KPI_DICTIONARY.md':'Каталог усіх 25 внутрішніх/публічних KPI з одиницями, формулами та правилами агрегації.',
'docs/KPI_DICTIONARY.csv':'Машиночитаний словник: код, українська назва, одиниця та пояснення; без колонки формул.',
'docs/VALIDATION.md':'Зафіксований результат перевірки публікаційного пакета: порожні томи, bootstrap, views і тести. Не є поточним live-статусом сервера.',
'docs/PROJECT_ANALYSIS.md':'Повний аналіз архітектури, потоків, контрактів, відновлення, відповідальності компонентів, реалізованих можливостей і обмежень.',
'docs/FINAL_ANALYTICS.md':'Повне пояснення кінцевої аналітики: зерно рядка, KPI, приклади розрахунків, готові графіки й обмеження висновків.',
'docs/START_HERE.md':'Послідовний запуск із нуля: підготовка, клонування, bootstrap, контрольні запити, DBeaver, Telegram, щоденна робота та діагностика.',
'docs/FILES_REFERENCE.md':'Повний перелік папок і файлів із призначенням та інтерфейсами Python-модулів.',
'docs/DATABASE_REFERENCE.md':'Повний каталог усіх таблиць, зв’язків і views обох СУБД, із типами та поясненнями кожного стовпця.',
'docs/schema_reference.json':'Версійований знімок структури: 44 об’єкти ClickHouse та 18 PostgreSQL, стовпці, SQL визначень і обмеження. Не містить вимірювань або даних підписників.',
}

FIELDS={
'active':'Чи ввімкнена підписка адресата.', 'address_family':'Числова версія IP у довіднику вимірювань: 4 або 6.', 'af':'4 — IPv4, 6 — IPv6; 0 у службових агрегатах подій підключення.',
'asn':'Номер автономної системи для конкретного IP-протоколу; 0 — невідомий або службовий.', 'asn_v4':'ASN IPv4 з довідника RIPE.', 'asn_v6':'ASN IPv6 з довідника RIPE.', 'atlas_status':'Статус зонда за останнім завантаженням довідника RIPE.',
'attempts':'Кількість зроблених спроб доставки.', 'avg_rtt_ms':'Середня RTT валідних серій, у мс; NULL без відповідей.', 'chat_id':'Ідентифікатор Telegram-чату; операційні дані, не для публікації.', 'connection_event':'Подія підключення/відключення зонда.',
'connects':'Кількість подій connect/connected.', 'country':'Код країни з довідника RIPE, у цьому потоці UA.', 'country_code':'Зрозуміла назва коду країни.', 'created_at':'Час створення операційного запису.', 'data_age_seconds':'Давність останнього вимірювання у секундах; NULL, якщо даних немає.',
'data_status':'Немає даних / Дані застаріли / Дані надходять; поріг старіння — 900 с.', 'day':'Дата календарного дня Europe/Kyiv.', 'delivery_count':'Кількість доставок адресатам; один outbox може дати багато доставок.', 'delivery_status':'Стан доставки окремому адресату.',
'description_uk':'Пояснення семантики KPI українською.', 'destination_address':'IP-адреса цілі вимірювання.', 'details':'JSONB-контекст інциденту: зонд, ASN, measurement, AF, значення, baseline, склад вибірки тощо.', 'disconnects':'Кількість подій disconnect/disconnected/down.',
'dst_addr':'IP-адреса цілі в сирому записі.', 'dst_name':'Назва цілі в сирому записі.', 'duration_seconds':'Час від початку до відновлення або до поточного моменту; оцінка за спостереженнями.', 'episode_id':'Ідентифікатор конкретного історичного епізоду; пов’язує початок та ескалацію.',
'episode_key':'Ключ поточного стану: тип + scope + measurement + AF.', 'event':'Тип події підключення.', 'event_at':'Час події підключення для відображення за Києвом.', 'event_id':'Стабільний ідентифікатор події для повторного читання й дедуплікації.',
'event_time':'Час джерельної події; у ClickHouse зберігається в UTC.', 'event_timestamp':'Unix timestamp останньої відомої події стану зонда.', 'field_code':'Внутрішній код поля.', 'field_name_uk':'Пояснювальна назва поля українською.',
'full_loss_samples':'Кількість серій із received=0.', 'high_loss_measurements':'Кількість серій із втратою понад 50%.', 'hour_start':'Початок години UTC; зберігає різні години під час переходу літнього часу.', 'id':'Технічний первинний ключ; у poll_state завжди 1, в outbox — послідовний номер.',
'incident_count':'Кількість унікальних епізодів за часом їхнього початку.', 'incident_id':'Ідентифікатор окремої події детектора.', 'incident_status':'Триває або Відновлено за відомим станом епізоду.', 'incident_type':'Тип: HIGH_RTT, PACKET_LOSS, PROBE_DOWN, ASN_OUTAGE, REGION_OUTAGE або PIPELINE_STALE.',
'ingested_at':'Час фізичного надходження до ClickHouse; версія сирого запису.', 'interval_seconds':'Номінальний інтервал RIPE-вимірювання, тут 240 с.', 'ip_version':'Підпис IPv4/IPv6; для неадресних подій у PostgreSQL — Не застосовується.', 'ipv4_provider_asn':'ASN IPv4 у читабельному довіднику.', 'ipv6_provider_asn':'ASN IPv6 у читабельному довіднику.',
'kafka_offset':'Позиція повідомлення в конкретній Kafka-партиції.', 'key':'Ключ службового маркера: last_maintenance, day:дата або вставка.', 'kind':'Внутрішній тип інциденту.', 'kpi_code':'Стабільний код KPI.', 'kpi_name':'Українська назва KPI в analytics.', 'kpi_name_uk':'Українська назва KPI в сумісному monitoring.', 'kpi_value':'Числове значення одного KPI.',
'last_error':'Збережений безпечний код останньої помилки доставки.', 'last_queued_at':'Час останньої постановки повідомлення у чергу для cooldown.', 'last_seen_at':'Час останнього підтвердження проблеми джерельними даними; не кожного запуску циклу.', 'latest_measurement_at':'Час останнього вимірювання джерела за Києвом; NULL без даних.',
'latitude':'Широта зонда.', 'local_hour':'Початок години для відображення Europe/Kyiv.', 'local_time':'Локальний час вимірювання у сумісному view.', 'longitude':'Довгота зонда.', 'loss_pct':'Втрати пакетів у конкретній сирій серії, %.','loss_samples':'Кількість серій зі втратою понад 50%.',
'max_rtt_ms':'Найбільша валідна RTT періоду, мс.', 'measured_at':'Час вимірювання у часовій зоні Europe/Kyiv.', 'measurement_count':'Кількість унікальних серій ping, а не пакетів.', 'measurement_id':'ID RIPE-вимірювання, що визначає ціль і AF.', 'measurement_success_pct':'Частка серій хоча б з однією відповіддю, %.', 'measurements_last_5h':'Кількість серій у сирій таблиці за останні 5 годин.',
'message':'Текст повідомлення або відповіді Telegram.', 'min_rtt_ms':'Найменша валідна RTT періоду, мс.', 'msm_id':'Внутрішня назва ID RIPE-вимірювання.', 'next_attempt_at':'Найраніший час наступної спроби доставки.', 'next_update_id':'Наступний getUpdates offset; захищає від повторної обробки команд.', 'no_reply_measurements':'Кількість серій без жодної відповіді.',
'normal_rtt_count':'Кількість серій із RTT>0 та втратою ≤50% для baseline.', 'normal_rtt_sum':'Сума RTT серій, придатних для baseline.', 'notification_status':'Стан сповіщення про подію; відрізняється від стану самого інциденту.', 'observed_probes':'Кількість DISTINCT зондів у сумісному агрегаті.',
'opened_at':'Час початку епізоду за доступними спостереженнями.', 'opening_id':'Подія monitoring_incidents, що відкрила епізод.', 'outbox_id':'Посилання доставки на спільне повідомлення outbox.', 'packet_loss_pct':'Зважені втрати пакетів періоду: зі співвідношення сум.', 'packets_lost':'Кількість надісланих пакетів без відповіді.', 'packets_received':'Кількість отриманих відповідей.', 'packets_sent':'Кількість надісланих пакетів.',
'partition_id':'Номер Kafka-партиції.', 'pause_until':'Глобальна пауза Telegram після 429.', 'period_end':'Права межа періоду в сумісному KPI-view.', 'period_label':'Текстовий підпис години/дня; не замінює часовий ключ.', 'period_name_uk':'Тип періоду українською.', 'period_start':'Початок періоду; analytics використовує DateTime Europe/Kyiv.',
'prb_id':'ID зонда в сирому контракті RIPE.', 'probe_id':'ID зонда у довідниках, агрегатах та звітах.', 'probes_observed':'Кількість різних зондів з вимірюваннями в цьому періоді.', 'probes_observed_last_5h':'Кількість різних зондів із результатами джерела за останні 5 годин.', 'provider_asn':'ASN відповідного протоколу в готовому звіті.', 'provider_name':'Позначення ASномер або Невідомий ASN; не комерційна назва оператора.',
'rcvd':'Кількість відповідей у сирій серії.', 'reason':'Причина відхилення запису.', 'received':'Сума отриманих відповідей у накопичувачі.', 'received_at':'Час отримання/запису діагностики, не обов’язково час початкової помилки.', 'rejected_events':'Кількість повідомлень DLQ; не кількість мережевих аварій.', 'resolved_at':'Час підтвердженого відновлення; NULL для відкритого епізоду.',
'rtt_avg':'Середня RTT однієї серії, мс.', 'rtt_count':'Кількість серій із не-NULL RTT; знаменник середнього.', 'rtt_max':'Максимум RTT.', 'rtt_min':'Мінімум RTT.', 'rtt_ms':'Середня RTT сирої серії у сумісному view.', 'rtt_sum':'Сума середніх RTT серій; чисельник середнього періоду.', 'samples':'Кількість серій ping; для службового status-рядка — 0.',
'scope':'Область інциденту: probe:ID, asn:ID, region:UA або measurement:ID.', 'sent':'Кількість пакетів у серії або сума у накопичувачі.', 'sent_at':'Час успішної доставки або завершення обробки outbox; дивіться також конкретний статус.', 'severity':'warning, critical або info.', 'source_address':'Адреса, яку RIPE повідомив як джерело вимірювання.', 'source_mode':'stream — живий потік, backfill — REST-дозавантаження.', 'src_addr':'Внутрішня назва адреси джерела.',
'stage':'Етап, на якому повідомлення відхилено: collector, websocket, RIPE або NiFi.', 'started_at':'Початок епізоду у reporting.', 'status':'Статус зонда або черги доставки залежно від таблиці.', 'status_uk':'Читабельний стан епізоду.', 'subscribed_at':'Час підписки адресата.', 'successful_measurements_pct':'Частка серій із хоча б однією відповіддю, %.',
'target':'Назва цілі у сумісному live-view.', 'target_hostname':'DNS-ім’я цілі вимірювання.', 'target_name':'Читабельна назва K-root/F-root або резервний підпис measurement.', 'telegram_message_id':'ID реально відправленого повідомлення Telegram.', 'topic':'Назва теми Kafka.', 'unit':'Одиниця KPI у analytics.', 'unit_uk':'Одиниця KPI у monitoring.', 'update_id':'ID Telegram update, який породив відповідь.', 'updated_at':'Час зміни підписки.', 'value':'Число KPI у довгому view або текст службового маркера в retention_runs.', 'version':'Версія знімка для вибору останнього запису ReplacingMergeTree.',
}

OBJECTS={
'monitoring.ping_results':'Одна сирa серія ping конкретного зонда й вимірювання. Зберігається 5 годин; записує тільки контрольований HTTP-обробник. Ключ сортування включає event_id, а ingested_at визначає версію.',
'monitoring.probe_events':'Одна подія підключення/відключення зонда. Зберігається 5 годин. Не має measurement/AF: це стан зв’язку з Atlas, а не ping до певної цілі.',
'monitoring.probe_directory':'Поточні метадані зонда. Один логічний рядок на probe_id, версії заміщуються; містить окремі ASN IPv4/IPv6 й координати. Статус оновлюється завантаженням довідника, не кожним ping.',
'monitoring.hourly_metrics':'Накопичувач: година UTC × зонд × measurement × AF × ASN. Містить достатні статистики, включно з незавершеною годиною. Зберігається 48 годин, але старий рядок не видаляється до підтвердження потрібного дня. AF=0/msm_id=0 — status-події.',
'monitoring.daily_metrics':'Довгостроковий підсумок: день Europe/Kyiv × зонд × measurement × AF × ASN. Фіналізується після 04:00; дні не видаляються. Суми, лічильники, мінімум і максимум зберігаються окремо.',
'monitoring.kpi_dictionary':'25 семантичних визначень KPI: код, назва, одиниця, пояснення. Це не часові значення показників. Читається FINAL; формульних стовпців немає.',
'monitoring.field_dictionary':'14 визначень внутрішніх назв полів. Службовий словник, а не копія вимірювань.',
'monitoring.retention_runs':'Поточні службові маркери: останнє очищення, ревізія збереженого дня, вставки. Один логічний рядок на key; це не повний журнал усіх запусків.',
'monitoring.ping_ingest_trigger':'Materialized view на INSERT у ping_results. Пише маркер ingest_request у retention_runs. Не рахує самостійно всі KPI й не запускається від годинника.',
'monitoring.status_ingest_trigger':'Materialized view на INSERT у probe_events. Пише status_ingest_request у retention_runs; повну обробку виконує Python-шлюз.',
'monitoring.raw_ping_last_5h':'Сумісний фільтр сирих ping за останні 5 годин, FINAL.',
'monitoring.raw_probe_events_last_5h':'Сумісний фільтр сирих status-подій за останні 5 годин, FINAL.',
'monitoring.live_network_measurements':'Сумісний live-view із приєднаним довідником зондів; використовує короткі внутрішні назви. Новим графікам рекомендований analytics.measurements_live.',
'monitoring.daily_probe_activity':'Поденні connects/disconnects із рядків AF=0. Рахує події, не тривалість простою.',
'analytics.measurement_directory':'Чотири визначення ціль+протокол. Один рядок на measurement_id; показує hostname, IP-версію та інтервал 240 с.',
'analytics.probe_directory':'Читабельний поточний довідник; один рядок на probe_id з окремими ASN IPv4/IPv6.',
'analytics.kpi_directory':'12 публічних числових KPI: код, назва й одиниця. Частина колонок відсутня у п’ятихвилинних views; точний склад наведено нижче.',
'analytics.measurements_live':'Одна дедуплікована серія ping за останні 5 годин; явні measurement_id, target_name, ip_version, ASN і координати.',
'analytics.data_freshness':'Один рядок на кожне з 4 налаштованих джерел, навіть без даних. Давність рахується за event_time і охоплює як stream, так і backfill; це не окремий контроль WebSocket.',
'analytics.probe_events_live':'Події Atlas за останні 5 годин у читабельних полях; AF навмисно відсутній.',
'public.monitoring_incidents':'Історія подій детектора: відкриття епізоду, ескалація та RECOVERED. Один рядок не дорівнює одному поганому ping або одній доставці. episode_id пов’язує події одного збою.',
'public.notification_cooldowns':'Один запис на ключ повідомлення епізоду з критичністю. Обмежує повторну постановку в outbox; сама активність інциденту визначається incident_episodes.',
'public.telegram_outbox':'Спільний текст одного сповіщення. Посилається на incident_id; доставки адресатам знаходяться в telegram_deliveries.',
'public.telegram_subscribers':'Один приватний Telegram-чат на chat_id. active визначає отримання майбутніх сповіщень; містить особисті операційні ідентифікатори.',
'public.telegram_poll_state':'Один singleton-рядок id=1: getUpdates offset та глобальна пауза після 429.',
'public.telegram_command_replies':'Одна відповідь на Telegram update, з незалежним станом і повторними спробами.',
'public.telegram_deliveries':'Одна доставка конкретному чату. Первинний ключ outbox_id+chat_id; стани sent/pending/failed/expired/cancelled відображають реальну спробу адресату.',
'public.incident_episodes':'Останній стан за episode_key. При новому епізоді того самого типу ключ перевикористовується; повна історія береться з monitoring_incidents, не лише з цієї таблиці.',
'public.probe_connectivity_state':'Остання відома подія стану зонда. Оновлюється лише новішим timestamp; не має 5-годинного очищення сирих status-подій.',
'public.processing_errors':'Один оброблений запис Kafka DLQ за topic+partition+offset. Зберігає причину та стадію, а не повний сирий payload. received_at — час запису діагностики, історичне перечитування може зміщувати графік.',
'public.incident_episode_metrics':'Внутрішній view останніх станів епізодів із тривалістю. Не повний архів повторних епізодів того самого ключа.',
'public.incident_history_metrics':'Внутрішній view історичних епізодів, згрупованих за episode_id, із початком, відновленням і тривалістю за спостереженнями.',
'public.processing_error_summary':'Внутрішнє погодинне групування діагностики за стадією й причиною.',
'reporting.incidents':'Один рядок на епізод: перший час початку, останній запис критичності, контекст і підтверджене відновлення. RECOVERED не рахується новою аварією.',
'reporting.incidents_hourly':'Нові епізоди за годиною початку, типом, останньою критичністю, measurement і протоколом. Не кількість активних збоїв у кожній годині.',
'reporting.incidents_daily':'Нові епізоди за київською датою початку, типом, measurement і протоколом. Тривалий збій через північ не додається щодня як новий.',
'reporting.processing_errors_hourly':'Кількість відхилених Kafka-повідомлень за часом запису діагностики, стадією та причиною.',
'reporting.telegram_deliveries_daily':'Кількість доставок за датою створення outbox і поточним статусом. Один інцидент × три адресати дає три доставки, а не три мережеві аварії.',
}

def description(name):
    if name in OBJECTS:return OBJECTS[name]
    schema,view=name.split('.')
    grain='година' if 'hourly' in view else 'день' if 'daily' in view else '5 хвилин'
    if schema=='analytics':
        level='зонд × ' if view.startswith('probes_') else 'ASN × ' if view.startswith('providers_') else ''
        long=' Один рядок на KPI; назва, одиниця та value.' if view.endswith('_kpi') else ' Один рядок із числовими колонками KPI.'
        return f'Зерно: {grain} × {level}measurement × IP-версія.{long} '+('Завершені години останніх 48 годин.' if 'hourly' in view else 'Збережені фіналізовані дні.' if 'daily' in view else 'Сирі результати останніх 5 годин; поточний 5-хвилинний інтервал може бути неповним.')
    if schema=='monitoring':
        level='ASN' if 'provider' in view else 'вся спостережувана вибірка' if 'country' in view else 'окремий зонд'
        return f'Сумісний view: {grain} × {level} × msm_id × af. '+('Довга форма: один KPI на рядок.' if 'kpi' in view else 'Середні та відсотки обчислюються зі статистик накопичувача.')+' Для нових графіків використовуйте analytics із явними назвами полів.'
    raise ValueError('Missing object description: '+name)

def files_reference():
    tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    paths=set(filter(None,tracked))|set(FILES)
    missing=paths-set(FILES)
    if missing:raise ValueError('Missing file descriptions: '+str(sorted(missing)))
    text='# Повний довідник папок і файлів\n\n[Карта документації](../README.md) · [Архітектура](PROJECT_ANALYSIS.md) · [Запуск](START_HERE.md)\n\n'
    text+='## Як читати структуру\n\nКод застосунку знаходиться в collector/app, але один образ запускається трьома різними командами: collector, analytics та alerts. Назва папки collector не означає, що всі модулі виконуються перед Kafka. SQL у init створює схему лише на порожньому томі; Python-генератори встановлюють актуальні views під час bootstrap. Міграційні SQL-файли є знімками для ручного використання, не автоматичним менеджером міграцій.\n\n'
    folders={'.github':'Автоматизація GitHub.', '.github/workflows':'Опис CI-перевірок.', 'collector':'Збірка спільного образу Python.', 'collector/app':'Код трьох сервісів і спільні модулі.', 'collector/tests':'Модульні й регресійні тести без зовнішніх сповіщень.', 'clickhouse':'Схема аналітичного сховища.', 'clickhouse/init':'Послідовна ініціалізація порожнього ClickHouse.', 'clickhouse/migrations':'SQL-знімки аналітичного шару.', 'postgres':'Операційна реляційна схема.', 'postgres/init':'Послідовна ініціалізація порожнього PostgreSQL.', 'postgres/migrations':'SQL-знімки операційних звітів.', 'nifi':'Налаштування потоку через REST API.', 'tools':'Команди запуску, перевірок і генерації документації.', 'docs':'Документація, словники та метадані схеми.'}
    text+='## Папки\n\n| Папка | Призначення |\n|---|---|\n'
    for folder,desc in folders.items():text+=f'| `{folder}/` | {desc} |\n'
    for folder in ['Корінь','.github/workflows','collector','collector/app','collector/tests','clickhouse/init','clickhouse/migrations','postgres/init','postgres/migrations','nifi','tools','docs']:
        text+='\n## '+folder+'\n\n'
        selected=[p for p in sorted(paths) if (str(Path(p).parent).replace('\\','/')==folder or folder=='Корінь' and Path(p).parent==Path('.'))]
        for path in selected:
            text+=f'### [{path}](../{path})\n\n{FILES[path]}\n\n'
            if path.endswith('.py') and (ROOT/path).exists():
                tree=ast.parse((ROOT/path).read_text(encoding='utf-8-sig'))
                names=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
                if names:text+='Основні програмні інтерфейси: '+', '.join('`'+n+'`' for n in names)+'.\n\n'
    text+='## Що створюється локально та не входить до Git\n\n| Об’єкт | Призначення |\n|---|---|\n| `.env` | Реальні локальні паролі й порти. |\n| `.secrets/telegram/config.json` | Токен бота; не передавати в репозиторій. |\n| Docker-томи | Вимірювання, агрегати, операційні дані, черги NiFi та Kafka. |\n| `collector_state/checkpoints.json` усередині тому | Завершені REST-діапазони; не SQL-таблиця. |\n| `analytics_state/pending-ingestion.json` усередині тому | Лише незавершений пакет запису; видаляється після підтвердження. |\n| Кеші Python, журнали, backups | Локальні допоміжні файли; виключені .gitignore. |\n'
    (ROOT/'docs/FILES_REFERENCE.md').write_text(text,encoding='utf-8',newline='\n')

def database_reference():
    data=json.loads((ROOT/'docs/schema_reference.json').read_text(encoding='utf-8'))
    fields={c['name'] for db in data.values() for c in db['columns']}
    if fields-set(FIELDS):raise ValueError('Missing field descriptions: '+str(sorted(fields-set(FIELDS))))
    text='# Повний довідник БД, таблиць і в’ю\n\n[Карта документації](../README.md) · [Кінцева аналітика](FINAL_ANALYTICS.md)\n\n'
    text+='## Відповідальність сховищ\n\nClickHouse: 8 фізичних таблиць, 2 materialized view та 34 звичайних view (14 сумісних у monitoring і 20 користувацьких у analytics). PostgreSQL: 10 фізичних таблиць, 3 внутрішні view у public та 5 користувацьких у reporting. Разом описано 62 об’єкти. PostgreSQL не приймає мережеві вимірювання перед ClickHouse. View — запит до існуючих даних, а не нова незалежна копія.\n\n'
    text+='## Зв’язки та ключі\n\n```mermaid\nerDiagram\n    monitoring_incidents ||--o| telegram_outbox : incident_id\n    telegram_outbox ||--o{ telegram_deliveries : outbox_id\n    telegram_subscribers ||--o{ telegram_deliveries : chat_id\n    monitoring_incidents ||--o{ incident_episodes : opening_id\n```\n\nУ ClickHouse зонд зв’язує довідник і вимірювання через probe_id/prb_id, а measurement_id/msm_id зв’язує результат із ціллю. Ключ години: hour_start+probe_id+msm_id+af+asn; ключ дня: day+ті самі виміри. ReplacingMergeTree логічно вибирає останню версію: фізичне сортування не є реляційним UNIQUE. Для коректного читання використовуються FINAL і дедуплікація шлюзу.\n\n'
    text+='## Індекс усіх об’єктів\n\n| СУБД | Об’єкт | Тип |\n|---|---|---|\n'
    for label,key,ns in [('ClickHouse','clickhouse','database'),('PostgreSQL','postgresql','schema')]:
        for obj in data[key]['objects']:
            name=obj[ns]+'.'+obj['name'];kind=obj.get('engine',obj.get('kind'))
            text+=f'| {label} | `{name}` | {kind} |\n'
    for label,key,ns in [('ClickHouse','clickhouse','database'),('PostgreSQL','postgresql','schema')]:
        text+='\n## '+label+'\n\n'
        db=data[key]
        for obj in db['objects']:
            name=obj[ns]+'.'+obj['name']
            text+='### '+name+'\n\n'+description(name)+'\n\n'
            if obj.get('sorting_key'):text+='Сортування: `'+obj['sorting_key']+'`.\n\n'
            if obj.get('partition_key'):text+='Партиціювання: `'+obj['partition_key']+'`.\n\n'
            constraints=[c for c in db.get('constraints',[]) if c['schema']==obj[ns] and c['table']==obj['name']]
            for c in constraints:text+='Обмеження: `'+c['definition']+'`.\n\n'
            text+='| Стовпець | Тип | Пояснення |\n|---|---|---|\n'
            for c in db['columns']:
                if c[ns]==obj[ns] and c['table']==obj['name']:
                    nullable='; NULL дозволений' if c.get('is_nullable')=='YES' else ''
                    text+=f"| `{c['name']}` | `{c['type']}`{nullable} | {FIELDS[c['name']]} |\n"
    text+='\n## Межі зберігання\n\n5 годин застосовуються до сирих таблиць ClickHouse; 48 годин — до накопичувачів годин із захистом незбереженого дня; daily_metrics не очищується. Ці строки не означають автоматичного очищення PostgreSQL, Kafka, довідників або резервних копій. Публікаційний код не містить політики автоматичного видалення операційної історії PostgreSQL.\n\nПовні SQL-визначення й типи зафіксовані у [schema_reference.json](schema_reference.json). Це метадані, без прикладних рядків або секретів. Для оновлення після міграції: `python tools/export_schema_reference.py`, потім `python tools/build_reference_docs.py`.\n'
    (ROOT/'docs/DATABASE_REFERENCE.md').write_text(text,encoding='utf-8',newline='\n')

if __name__=='__main__':
    files_reference();database_reference();print('Built complete file and database references')
