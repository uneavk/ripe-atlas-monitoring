# Файли та структура проєкту

[Головна](../README.md) · [Архітектура](ARCHITECTURE.md) · [Запуск](SETUP.md)

Описано всі 87 файлів і 15 папок, які відстежує Git.

Один Python-образ запускає три різні сервіси: collector, analytics та alerts. Початкові схеми містяться у clickhouse/init.sql та postgres/init.sql. Аналітичні в’ю створюють Python-модулі під час bootstrap. Специфікація Metabase має власний JSON-експорт.

## Папки

| Папка | Призначення |
|---|---|
| `.github/` | Автоматизація GitHub. |
| `.github/workflows/` | CI та ручний download приватної конфігурації. |
| `artifacts/` | Історичні докази роботи. |
| `artifacts/handin/` | Готові матеріали для захисту, сценарій, демонстраційні SQL та контрольний зріз. |
| `artifacts/handin/screenshots/` | 16 оригіналів реальних екранів Docker, GitHub, Kafka, NiFi, DBeaver та Metabase від 16.11.2026. |
| `artifacts/screenshots/` | Збережені екрани Metabase. |
| `bi/` | Специфікація, експорт і тести дашбордів. |
| `clickhouse/` | Єдина початкова аналітична схема. |
| `collector/` | Спільний Python-образ. |
| `collector/app/` | Прикладні модулі трьох сервісів. |
| `collector/tests/` | Модульні та регресійні тести. |
| `docs/` | Шість інструкцій, CSV KPI й метадані схеми. |
| `nifi/` | API та конфігуратор потоку. |
| `postgres/` | Єдина початкова операційна схема. |
| `tools/` | Запуск, документація та перевірки. |

## Корінь

### [.env.example](../.env.example)

Шаблон адрес, портів і користувачів. Містить лише заглушки паролів. Bootstrap копіює його в локальний .env і генерує випадкові паролі.

### [.gitattributes](../.gitattributes)

Задає LF для текстових файлів і правила для двійкових зображень, щоб Windows та Linux однаково читали код.

### [.gitignore](../.gitignore)

Виключає .env, секрети, локальні БД, журнали, кеші та томи з публікації Git.

### [README.md](../README.md)

Короткий огляд, швидкий запуск, структура та посилання на шість повних інструкцій.

### [compose.bi.yaml](../compose.bi.yaml)

Необов’язкове підключення Metabase до мережі старого Docker-стека. Для нового встановлення достатньо основного compose.yaml.

### [compose.yaml](../compose.yaml)

Повний Docker-стек. На порожніх томах монтує два init.sql, запускає спільний Python-образ і Metabase.


## .github/workflows

### [.github/workflows/download-configuration.yml](../.github/workflows/download-configuration.yml)

Ручний workflow приватного репозиторію: готує download налаштованої GitHub Secrets копії чотирьох конфігураційних файлів. Перевіряє склад і контрольні суми, не показує паролі й не запускає бот.

### [.github/workflows/tests.yml](../.github/workflows/tests.yml)

GitHub Actions: модульні тести, повнота документації, файли коміту й відтворюваність згенерованих артефактів.


## artifacts

### [artifacts/evidence_snapshot.json](../artifacts/evidence_snapshot.json)

Історичний знеособлений контрольний зріз від 09.11.2026, а не поточні дані нової інсталяції.


## artifacts/handin

### [artifacts/handin/README.md](../artifacts/handin/README.md)

Сценарій командного захисту, схеми, запуск, пояснення матеріалів і 16 реальних скріншотів.

### [artifacts/handin/RIPE_Atlas_Defense.pptx](../artifacts/handin/RIPE_Atlas_Defense.pptx)

Редагована презентація з 15 слайдів і нотатками для рівного виступу трьох учасниць. Датовані докази, 16.11.2026.

### [artifacts/handin/RIPE_Atlas_Report.pdf](../artifacts/handin/RIPE_Atlas_Report.pdf)

Звіт на 18 сторінках: зв’язний опис системи, 2 схеми, 16 реальних скріншотів, KPI, помилки, аналітика та джерела.

### [artifacts/handin/architecture.svg](../artifacts/handin/architecture.svg)

Векторна схема архітектури за README: RIPE → collector → Kafka → NiFi → ClickHouse, операційний стан, BI та Telegram.

### [artifacts/handin/demo_clickhouse.sql](../artifacts/handin/demo_clickhouse.sql)

13 запитів лише на читання для DBeaver: структура, протоколи, години/дні, KPI, маркери INSERT і штучні приклади в SELECT без запису даних.

### [artifacts/handin/demo_postgres.sql](../artifacts/handin/demo_postgres.sql)

5 запитів лише на читання: епізоди, підсумки інцидентів, діагностика та стани доставки без адресатів Telegram.

### [artifacts/handin/nifi-flow.svg](../artifacts/handin/nifi-flow.svg)

Векторна схема трьох основних гілок NiFi та спільного маршруту діагностики відхилених подій.

### [artifacts/handin/verification.json](../artifacts/handin/verification.json)

Знеособлений контрольний зріз від 16.11.2026: БД, 18 перевірених запитів, Docker і фактичні процесори/зв’язки NiFi. Не містить секретів чи сирих подій.


## artifacts/handin/screenshots

### [artifacts/handin/screenshots/01-docker-live.jpg](../artifacts/handin/screenshots/01-docker-live.jpg)

Реальний оригінал скріншота від 16.11.2026. Docker Desktop: служби проєкту та журнал успішних публікацій collector у ripe.raw. Поточний запуск, 16.11.2026.

### [artifacts/handin/screenshots/02-github-structure.jpg](../artifacts/handin/screenshots/02-github-structure.jpg)

Реальний оригінал скріншота від 16.11.2026. README репозиторію: основні папки та команди перевірки.

### [artifacts/handin/screenshots/03-kafka-topics.jpg](../artifacts/handin/screenshots/03-kafka-topics.jpg)

Реальний оригінал скріншота від 16.11.2026. Теми Kafka UI. Порожня ripe.validated - успадкована тема, поточний потік її не використовує. Фрагмент екрана.

### [artifacts/handin/screenshots/04-kafka-consumers.jpg](../artifacts/handin/screenshots/04-kafka-consumers.jpg)

Реальний оригінал скріншота від 16.11.2026. Окремі consumer groups NiFi та діагностики. STABLE означає стабільне членство в групі. N/A у lag не означає нуль відставання. Фрагмент екрана.

### [artifacts/handin/screenshots/05-dbeaver-clickhouse-views.jpg](../artifacts/handin/screenshots/05-dbeaver-clickhouse-views.jpg)

Реальний оригінал скріншота від 16.11.2026. DBeaver: 8 фізичних таблиць monitoring і результат запиту до каталогу 44 об’єктів ClickHouse.

### [artifacts/handin/screenshots/06-dbeaver-ip-versions.jpg](../artifacts/handin/screenshots/06-dbeaver-ip-versions.jpg)

Реальний оригінал скріншота від 16.11.2026. data_freshness у DBeaver: чотири джерела, IP-версія, давність даних і фактично спостережувані зонди.

### [artifacts/handin/screenshots/07-dbeaver-retention.jpg](../artifacts/handin/screenshots/07-dbeaver-retention.jpg)

Реальний оригінал скріншота від 16.11.2026. Маркери вставок, last_maintenance і перевірка raw_rows_older_than_5h=0. Час маркерів зберігається в UTC.

### [artifacts/handin/screenshots/08-dbeaver-kpi.jpg](../artifacts/handin/screenshots/08-dbeaver-kpi.jpg)

Реальний оригінал скріншота від 16.11.2026. network_hourly_kpi: назва, одиниця та значення KPI останньої завершеної години для K-root IPv4.

### [artifacts/handin/screenshots/09-metabase-rtt.jpg](../artifacts/handin/screenshots/09-metabase-rtt.jpg)

Реальний оригінал скріншота від 16.11.2026. Дашборд поточного стану, картка RTT: окрема лінія для кожної цілі й IP-версії. Дані згруповані по 5 хвилин.

### [artifacts/handin/screenshots/10-metabase-daily.jpg](../artifacts/handin/screenshots/10-metabase-daily.jpg)

Реальний оригінал скріншота від 16.11.2026. Поденні середні: історія зберігає також давніші вересневі дані.

### [artifacts/handin/screenshots/11-metabase-ipv6-map.jpg](../artifacts/handin/screenshots/11-metabase-ipv6-map.jpg)

Реальний оригінал скріншота від 16.11.2026. Карта K-root IPv6, measurement=2001, 47 рядків на момент знімка. Підкладка © OpenStreetMap contributors, Leaflet.

### [artifacts/handin/screenshots/12-metabase-hourly.jpg](../artifacts/handin/screenshots/12-metabase-hourly.jpg)

Реальний оригінал скріншота від 16.11.2026. Завершені години: видимі розриви даних.

### [artifacts/handin/screenshots/13-metabase-incidents.jpg](../artifacts/handin/screenshots/13-metabase-incidents.jpg)

Реальний оригінал скріншота від 16.11.2026. Журнал Metabase розрізняє відкриті та відновлені епізоди. Знімок показує реальні спостереження, 16.11.2026.

### [artifacts/handin/screenshots/14-dbeaver-postgresql.jpg](../artifacts/handin/screenshots/14-dbeaver-postgresql.jpg)

Реальний оригінал скріншота від 16.11.2026. DBeaver/PostgreSQL: реальні епізоди з протоколом, часом Києва, станом і статусом сповіщення.

### [artifacts/handin/screenshots/15-nifi-summary.jpg](../artifacts/handin/screenshots/15-nifi-summary.jpg)

Реальний оригінал скріншота від 16.11.2026. NiFi Summary, 16.11.2026: усі 11 процесорів Running. Лічильники In/Out та Read/Write показують роботу за останні 5 хвилин.

### [artifacts/handin/screenshots/16-nifi-canvas.jpg](../artifacts/handin/screenshots/16-nifi-canvas.jpg)

Реальний оригінал скріншота від 16.11.2026. Повне полотно NiFi: три основні рядки та нижня гілка Describe rejected events → RIPE invalid events. Це реальний екран; читабельні назви наведено на схемі попередньої сторінки.


## artifacts/screenshots

### [artifacts/screenshots/live-rtt.jpg](../artifacts/screenshots/live-rtt.jpg)

Реальний скріншот RTT у Metabase від 09.11.2026 без облікових даних.

### [artifacts/screenshots/map-ipv6.jpg](../artifacts/screenshots/map-ipv6.jpg)

Реальна карта останніх результатів K-root IPv6 від 09.11.2026. Містить підпис OpenStreetMap.


## bi

### [bi/dashboard_spec.json](../bi/dashboard_spec.json)

Публічний переносимий експорт специфікації дашбордів без локальних ID, адресатів і credentials. Не є vendor-export Metabase.

### [bi/dashboards.py](../bi/dashboards.py)

Джерело 3 дашбордів і 26 SQL-карток: показники, підписи, фільтри та налаштування візуалізацій без паролів.

Основні інтерфейси: `card`, `trend`, `build`.

### [bi/test_dashboards.py](../bi/test_dashboards.py)

4 тести SQL-контрактів, пропусків даних, фільтра, геометрії й відсутності доступу до підписників.

Основні інтерфейси: `DashboardContracts`.

### [bi/validation.json](../bi/validation.json)

Збережені результати виконання 26 карток, додаткового IPv6-фільтра та перевірки геометрії. Не поточний live-статус.


## clickhouse

### [clickhouse/init.sql](../clickhouse/init.sql)

Єдина початкова схема ClickHouse. Послідовно створює сирі таблиці, накопичувачі, довідник, сумісні в’ю й маркери вставок.


## collector

### [collector/.dockerignore](../collector/.dockerignore)

Виключає кеші, локальний стан і секрети з контексту збірки образу Python.

### [collector/Dockerfile](../collector/Dockerfile)

Будує спільний Python-образ для collector, analytics та alerts. Копіює код і тести, встановлює залежності, запускає процеси від користувача collector.

### [collector/requirements.txt](../collector/requirements.txt)

Фіксує прямі залежності: kafka-python для Kafka, psycopg для PostgreSQL, requests для REST/HTTP і websocket-client для потоку RIPE.


## collector/app

### [collector/app/__init__.py](../collector/app/__init__.py)

Позначає каталог app як Python-пакет; самостійного сервісу не запускає.

### [collector/app/alert_rules.py](../collector/app/alert_rules.py)

Чисті правила детекції та форматування повідомлень. Не записує БД і не звертається до Telegram. Отримує готовий зріз і повертає Incident.

Основні інтерфейси: `Incident`, `detect`, `format_message`.

### [collector/app/alerts.py](../collector/app/alerts.py)

Цикл детектора: читає дані та baseline з ClickHouse, веде епізоди в PostgreSQL, приймає команди Telegram і запускає доставку. Підтримує --once для одного циклу.

Основні інтерфейси: `stop`, `credentials`, `ch_query`, `snapshot`, `record`, `main`.

### [collector/app/analytics_views.py](../collector/app/analytics_views.py)

Генерує 20 користувацьких в’ю analytics: довідники, live, 5 хвилин, години, дні, зрізи мережі/ASN/зонда та свіжість. Тут визначені чотири measurement ID і зрозумілі назви полів.

Основні інтерфейси: `quote`, `definitions`, `main`.

### [collector/app/checkpoint.py](../collector/app/checkpoint.py)

Зберігає позиції завершеного backfill за measurement ID у JSON-файлі Docker-тому. Оновлює файл атомарною заміною; PostgreSQL не використовує.

Основні інтерфейси: `CheckpointStore`.

### [collector/app/config.py](../collector/app/config.py)

Зчитує параметри середовища: країну, вимірювання, backfill, Kafka, checkpoint і рівень журналювання. Містить адреси RIPE API та межі reconnect.

Основні інтерфейси: `_csv_ints`, `Settings`.

### [collector/app/incident_state.py](../collector/app/incident_state.py)

Операційна схема, ключ епізоду та правила відновлення. Відсутність даних не вважається відновленням. Зберігає актуальний стан окремо від історії подій.

Основні інтерфейси: `key`, `recovered`, `recovery_events`.

### [collector/app/install_kpi.py](../collector/app/install_kpi.py)

Створює або оновлює словники ClickHouse та чотири сумісні довгі KPI-в’ю monitoring. Прибирає колонки formula_uk та aggregation із таблиці словника.

Основні інтерфейси: `main`.

### [collector/app/kafka_io.py](../collector/app/kafka_io.py)

Синхронний Kafka producer: acks=all, gzip, повтори та очікування підтвердження. Ключ повідомлення — probe ID або event ID.

Основні інтерфейси: `ReliableProducer`.

### [collector/app/kpi_catalog.py](../collector/app/kpi_catalog.py)

Семантичний каталог 25 кодів KPI та 14 полів: назви, одиниці, пояснення й правила розрахунку. Формули в коді/документації не є стовпцями готових в’ю.

### [collector/app/logging_config.py](../collector/app/logging_config.py)

Налаштовує структуровані JSON-журнали: час, рівень, компонент, тип події та контекст обробки.

Основні інтерфейси: `JsonFormatter`, `configure_logging`.

### [collector/app/main.py](../collector/app/main.py)

Точка входу збирача. Завантажує довідник, перевіряє джерела, виконує REST-backfill, слухає WebSocket, фільтрує UA, публікує Kafka-повідомлення та відхилення. Checkpoint змінюється після завершеного REST-діапазону.

Основні інтерфейси: `stop`, `main`.

### [collector/app/models.py](../collector/app/models.py)

Нормалізація ping і статусів, розрахунок loss, стабільні SHA-256 event_id, перевірка ідентифікаторів, AF, пакетів і RTT. При rcvd=0 очищує RTT до NULL.

Основні інтерфейси: `make_event_id`, `normalize_ping`, `normalize_probe_status`, `validate_minimum`.

### [collector/app/operational_views.py](../collector/app/operational_views.py)

Створює 5 в’ю reporting у PostgreSQL. Формує один рядок на епізод, підсумки інцидентів, помилок та доставки.

Основні інтерфейси: `main`.

### [collector/app/pipeline_errors.py](../collector/app/pipeline_errors.py)

Окремий Kafka consumer ripe.dead_letter. Після запису діагностики в PostgreSQL підтверджує offset; унікальний ключ topic/partition/offset захищає від повторів.

Основні інтерфейси: `ErrorReader`.

### [collector/app/retention_clickhouse.py](../collector/app/retention_clickhouse.py)

HTTP-шлюз запису в ClickHouse. Валідує та дедуплікує записи, об’єднує HTTP-запити в пакети, веде короткий журнал незавершеної операції, оновлює години, фіналізує дні й очищує старі дані.

Основні інтерфейси: `encode`, `ch`, `quote`, `instant`, `finalized_day`, `seconds_to_next_run`, `values`, `hour_key`, `combine`, `Store`, `ingestion_worker`, `Handler`, `worker`, `main`.

### [collector/app/ripe_client.py](../collector/app/ripe_client.py)

Клієнт RIPE: пагінація зондів, перевірка measurement, REST-запити 5-хвилинними частинами та підписки WebSocket. Некоректні JSON/envelope передає обробнику помилок.

Основні інтерфейси: `RipeAtlasClient`.

### [collector/app/telegram_sender.py](../collector/app/telegram_sender.py)

HTTP-транспорт Telegram: виклики Bot API, HTML-повідомлення, повернення message_id, розбір помилок і retry_after. При помилці не виводить URL із токеном.

Основні інтерфейси: `DeliveryError`, `call`, `send`.

### [collector/app/telegram_subscriptions.py](../collector/app/telegram_subscriptions.py)

Обробляє /start, /stop, /status, /help у приватних чатах. Веде offsets команд, черги відповідей і доставки кожному підписнику; обробляє блокування, 429 та закінчення строку повідомлень.

Основні інтерфейси: `command`, `apply_updates`, `poll`, `retry`, `dispatch`.


## collector/tests

### [collector/tests/test_alerts.py](../collector/tests/test_alerts.py)

Перевіряє пороги й підтвердження аномалій, групування за ASN/AF, знаменники вибірки та транспорт Telegram на підставних відповідях.

Основні інтерфейси: `ping`, `RulesTests`, `TelegramTests`.

### [collector/tests/test_audit_fixes.py](../collector/tests/test_audit_fixes.py)

Регресійні сценарії: повна втрата без RTT, тривалий disconnect, відновлення лише за новими даними, свіжість та відокремлення епізодів.

Основні інтерфейси: `ping`, `AuditFixes`.

### [collector/tests/test_clickhouse_daily.py](../collector/tests/test_clickhouse_daily.py)

Підставне сховище перевіряє добове згортання, порядок збереження й очищення та повтор після помилки запису дня.

Основні інтерфейси: `DailyBackend`, `DailyTests`.

### [collector/tests/test_clickhouse_store.py](../collector/tests/test_clickhouse_store.py)

Підставне сховище перевіряє повтор після часткового запису, відсутність подвійного підрахунку, накопичення статистик і відхилення старих даних.

Основні інтерфейси: `FakeClickHouse`, `ClickHouseOnlyTests`.

### [collector/tests/test_models.py](../collector/tests/test_models.py)

Перевіряє нормалізацію, відсоток втрат, стабільність event ID і події статусів.

Основні інтерфейси: `ModelTests`.

### [collector/tests/test_retention.py](../collector/tests/test_retention.py)

Перевіряє безпосередньо ClickHouse-обробник: межу 04:00, DST, часові ключі, NULL RTT і пакети.

Основні інтерфейси: `RetentionTests`.

### [collector/tests/test_subscriptions.py](../collector/tests/test_subscriptions.py)

Перевіряє дозволені Telegram-команди та приватний характер підписки без реальних повідомлень.

Основні інтерфейси: `CommandsTests`.


## docs

### [docs/ANALYTICS.md](../docs/ANALYTICS.md)

Правила KPI й агрегації, приклади SQL, повний словник і пояснення кожної з 26 карток Metabase.

### [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)

Повний аналіз джерел, компонентів, контрактів, відновлення, retention, інцидентів і меж системи.

### [docs/CHECKS.md](../docs/CHECKS.md)

Протоколи перевірок із датами, результатами й межами підтверджених висновків.

### [docs/DATABASE.md](../docs/DATABASE.md)

Згенеровані пояснення всіх 62 прикладних об’єктів БД та 599 стовпців із типами, ключами і зв’язками.

### [docs/FILES.md](../docs/FILES.md)

Згенерований опис кожної відстежуваної папки й файла, основних функцій і локального робочого стану.

### [docs/KPI_DICTIONARY.csv](../docs/KPI_DICTIONARY.csv)

Машиночитаний словник: код, українська назва, одиниця та пояснення; без колонки формул.

### [docs/SETUP.md](../docs/SETUP.md)

Єдина інструкція встановлення, параметрів, DBeaver, Metabase, Telegram, онлайн-копії налаштувань і супроводу.

### [docs/schema_reference.json](../docs/schema_reference.json)

Версійований знімок структури: 44 об’єкти ClickHouse та 18 PostgreSQL, стовпці, SQL визначень і обмеження. Не містить вимірювань або даних підписників.


## nifi

### [nifi/api_client.py](../nifi/api_client.py)

Локальний REST-клієнт NiFi. Знаходить контейнер і опублікований порт через Compose, читає налаштовані облікові дані з Docker, чекає готовності й отримує тимчасовий JWT без друку секретів.

Основні інтерфейси: `api`.

### [nifi/build_pipeline.py](../nifi/build_pipeline.py)

Відтворює 11 процесорів і зв’язки. Налаштовує Kafka, Groovy-перевірки, HTTP sinks та відхилення; при повторі тимчасово зупиняє власні процесори й відновлює роботу.

Основні інтерфейси: `restore_running`, `processor`, `connect`.


## postgres

### [postgres/init.sql](../postgres/init.sql)

Єдина початкова схема PostgreSQL: інциденти, cooldown, outbox, підписки, доставки, епізоди й діагностика.


## tools

### [tools/bootstrap.py](../tools/bootstrap.py)

Основна команда першого запуску. Створює локальні паролі, перевіряє Compose, збирає один спільний образ, запускає стек, налаштовує NiFi та обидва шари в’ю.

Основні інтерфейси: `run`, `environment`, `main`.

### [tools/checks.py](../tools/checks.py)

Одна команда для 41 модульного тесту, аудиту документації та перевірки файлів Git. Підтримує --unit, --docs і --publication.

Основні інтерфейси: `inspect_file`, `publication`, `audit`, `unit`, `main`.

### [tools/configure_telegram.py](../tools/configure_telegram.py)

Приховано запитує токен і записує його тільки в .secrets/telegram/config.json. Сам не надсилає повідомлень і не перевіряє токен через мережу.

Основні інтерфейси: `main`.

### [tools/docs.py](../tools/docs.py)

Одна команда для генерації довідників, словника KPI й експорту Metabase. --schema попередньо оновлює метадані працюючих БД.

Основні інтерфейси: `description`, `database_reference`, `run`, `export_schema`, `files_reference`, `export_assets`, `kpi_section`, `dashboard_section`, `analytics_reference`, `main`.

### [tools/setup_metabase.py](../tools/setup_metabase.py)

Ідемпотентно налаштовує Metabase через API, створює BI-reader та власні картки. Паролі й локальні ID записує лише у .secrets.

Основні інтерфейси: `API`, `inspect`, `container_python`, `configure_readers`, `items`, `layout`, `main`.

### [tools/verify_analytics_views.py](../tools/verify_analytics_views.py)

Виконує SELECT до 20 analytics-в’ю, перевіряє відсутність формульних колонок і звіряє поденні суми, DISTINCT та зважені середні зі сховищем. На хості делегує перевірку Docker.

### [tools/verify_metabase.py](../tools/verify_metabase.py)

Виконує запити всіх BI-карток, IPv6-фільтр та перевірку відсутності перекриття. Звіт містить статуси й кількість рядків без даних адресатів.

Основні інтерфейси: `main`.

## Робочі файли поза комітами

| Об’єкт | Призначення |
|---|---|
| `.env` | Паролі й порти поточної копії; погоджений знімок є в GitHub Secrets. |
| `.secrets/metabase/admin.json` | Вхід адміністратора Metabase та пароль BI-reader. |
| `.secrets/metabase/manifest.json` | ID та URL локальних дашбордів. |
| `.secrets/metabase/deployment.env` | Окреме підключення BI до старого стека. |
| `.secrets/configuration-backup-receipt.json` | Протокол звіряння онлайн-копії без значень паролів. |
| `.secrets/telegram/config.json` | Токен власного бота, не включений до погодженого онлайн-знімка. |
| `Docker-томи` | Бази, черги, checkpoints і журнал незавершеного запису. |
| `Кеші, журнали, backups` | Робочий стан та діагностика, виключені .gitignore. |
