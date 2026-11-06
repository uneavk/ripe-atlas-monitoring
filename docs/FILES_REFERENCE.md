# Повний довідник папок і файлів

[Карта документації](../README.md) · [Архітектура](PROJECT_ANALYSIS.md) · [Запуск](START_HERE.md)

## Як читати структуру

Код застосунку знаходиться в collector/app, але один образ запускається трьома різними командами: collector, analytics та alerts. Назва папки collector не означає, що всі модулі виконуються перед Kafka. SQL у init створює схему лише на порожньому томі; Python-генератори встановлюють актуальні views під час bootstrap. Міграційні SQL-файли є знімками для ручного використання, не автоматичним менеджером міграцій.

## Папки

| Папка | Призначення |
|---|---|
| `.github/` | Автоматизація GitHub. |
| `.github/workflows/` | Опис CI-перевірок. |
| `collector/` | Збірка спільного образу Python. |
| `collector/app/` | Код трьох сервісів і спільні модулі. |
| `collector/tests/` | Модульні й регресійні тести без зовнішніх сповіщень. |
| `clickhouse/` | Схема аналітичного сховища. |
| `clickhouse/init/` | Послідовна ініціалізація порожнього ClickHouse. |
| `clickhouse/migrations/` | SQL-знімки аналітичного шару. |
| `postgres/` | Операційна реляційна схема. |
| `postgres/init/` | Послідовна ініціалізація порожнього PostgreSQL. |
| `postgres/migrations/` | SQL-знімки операційних звітів. |
| `nifi/` | Налаштування потоку через REST API. |
| `tools/` | Команди запуску, перевірок і генерації документації. |
| `docs/` | Документація, словники та метадані схеми. |

## Корінь

### [.env.example](../.env.example)

Шаблон адрес, портів і користувачів. Містить лише заглушки паролів. Bootstrap копіює його в локальний .env і генерує випадкові паролі.

### [.gitattributes](../.gitattributes)

Задає LF для текстових файлів і правила для двійкових зображень, щоб Windows та Linux однаково читали код.

### [.gitignore](../.gitignore)

Виключає .env, секрети, локальні БД, журнали, кеші та томи з публікації Git.

### [README.md](../README.md)

Головна сторінка: призначення, схема роботи, карта документації, короткий запуск і посилання на повні довідники.

### [compose.yaml](../compose.yaml)

Опис усіх Docker-сервісів, залежностей, мережі, портів, перевірок готовності та іменованих томів. Одноразовий kafka-init створює теми.


## .github/workflows

### [.github/workflows/tests.yml](../.github/workflows/tests.yml)

GitHub Actions: після push або pull request встановлює Python 3.12, залежності, перевіряє компіляцію й виконує модульні тести.


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

Основні програмні інтерфейси: `Incident`, `detect`, `format_message`.

### [collector/app/alerts.py](../collector/app/alerts.py)

Цикл детектора: читає дані та baseline з ClickHouse, веде епізоди в PostgreSQL, приймає команди Telegram і запускає доставку. Підтримує --once для одного циклу.

Основні програмні інтерфейси: `stop`, `credentials`, `ch_query`, `snapshot`, `record`, `main`.

### [collector/app/analytics_views.py](../collector/app/analytics_views.py)

Генерує 20 користувацьких в’ю analytics: довідники, live, 5 хвилин, години, дні, зрізи мережі/ASN/зонда та свіжість. Тут визначені чотири measurement ID і зрозумілі назви полів.

Основні програмні інтерфейси: `quote`, `definitions`, `main`.

### [collector/app/checkpoint.py](../collector/app/checkpoint.py)

Зберігає позиції завершеного backfill за measurement ID у JSON-файлі Docker-тому. Оновлює файл атомарною заміною; PostgreSQL не використовує.

Основні програмні інтерфейси: `CheckpointStore`.

### [collector/app/config.py](../collector/app/config.py)

Зчитує параметри середовища: країну, вимірювання, backfill, Kafka, checkpoint і рівень журналювання. Містить адреси RIPE API та межі reconnect.

Основні програмні інтерфейси: `_csv_ints`, `Settings`.

### [collector/app/incident_state.py](../collector/app/incident_state.py)

Операційна схема, ключ епізоду та правила відновлення. Відсутність даних не вважається відновленням. Зберігає актуальний стан окремо від історії подій.

Основні програмні інтерфейси: `key`, `recovered`, `recovery_events`.

### [collector/app/install_kpi.py](../collector/app/install_kpi.py)

Створює або оновлює словники ClickHouse та чотири сумісні довгі KPI-в’ю monitoring. Прибирає колонки formula_uk та aggregation із таблиці словника.

Основні програмні інтерфейси: `main`.

### [collector/app/kafka_io.py](../collector/app/kafka_io.py)

Синхронний Kafka producer: acks=all, gzip, повтори та очікування підтвердження. Ключ повідомлення — probe ID або event ID.

Основні програмні інтерфейси: `ReliableProducer`.

### [collector/app/kpi_catalog.py](../collector/app/kpi_catalog.py)

Семантичний каталог 25 кодів KPI та 14 полів: назви, одиниці, пояснення й правила розрахунку. Формули в коді/документації не є стовпцями готових в’ю.

### [collector/app/logging_config.py](../collector/app/logging_config.py)

Налаштовує структуровані JSON-журнали: час, рівень, компонент, тип події та контекст обробки.

Основні програмні інтерфейси: `JsonFormatter`, `configure_logging`.

### [collector/app/main.py](../collector/app/main.py)

Точка входу збирача. Завантажує довідник, перевіряє джерела, виконує REST-backfill, слухає WebSocket, фільтрує UA, публікує Kafka-повідомлення та відхилення. Checkpoint змінюється після завершеного REST-діапазону.

Основні програмні інтерфейси: `stop`, `main`.

### [collector/app/models.py](../collector/app/models.py)

Нормалізація ping і статусів, розрахунок loss, стабільні SHA-256 event_id, перевірка ідентифікаторів, AF, пакетів і RTT. При rcvd=0 очищує RTT до NULL.

Основні програмні інтерфейси: `make_event_id`, `normalize_ping`, `normalize_probe_status`, `validate_minimum`.

### [collector/app/operational_views.py](../collector/app/operational_views.py)

Створює 5 в’ю reporting у PostgreSQL. Формує один рядок на епізод, підсумки інцидентів, помилок та доставки.

Основні програмні інтерфейси: `main`.

### [collector/app/pipeline_errors.py](../collector/app/pipeline_errors.py)

Окремий Kafka consumer ripe.dead_letter. Після запису діагностики в PostgreSQL підтверджує offset; унікальний ключ topic/partition/offset захищає від повторів.

Основні програмні інтерфейси: `ErrorReader`.

### [collector/app/retention.py](../collector/app/retention.py)

Сумісна точка входу, що перенаправляє до retention_clickhouse. Це не другий обробник і не PostgreSQL-агрегація.

### [collector/app/retention_clickhouse.py](../collector/app/retention_clickhouse.py)

HTTP-шлюз запису в ClickHouse. Валідує та дедуплікує записи, об’єднує HTTP-запити в пакети, веде короткий журнал незавершеної операції, оновлює години, фіналізує дні й очищує старі дані.

Основні програмні інтерфейси: `encode`, `ch`, `quote`, `instant`, `finalized_day`, `seconds_to_next_run`, `values`, `hour_key`, `combine`, `Store`, `ingestion_worker`, `Handler`, `worker`, `main`.

### [collector/app/ripe_client.py](../collector/app/ripe_client.py)

Клієнт RIPE: пагінація зондів, перевірка measurement, REST-запити 5-хвилинними частинами та підписки WebSocket. Некоректні JSON/envelope передає обробнику помилок.

Основні програмні інтерфейси: `RipeAtlasClient`.

### [collector/app/telegram_sender.py](../collector/app/telegram_sender.py)

HTTP-транспорт Telegram: виклики Bot API, HTML-повідомлення, повернення message_id, розбір помилок і retry_after. При помилці не виводить URL із токеном.

Основні програмні інтерфейси: `DeliveryError`, `call`, `send`.

### [collector/app/telegram_subscriptions.py](../collector/app/telegram_subscriptions.py)

Обробляє /start, /stop, /status, /help у приватних чатах. Веде offsets команд, черги відповідей і доставки кожному підписнику; обробляє блокування, 429 та закінчення строку повідомлень.

Основні програмні інтерфейси: `command`, `apply_updates`, `poll`, `retry`, `dispatch`.


## collector/tests

### [collector/tests/test_alerts.py](../collector/tests/test_alerts.py)

Перевіряє пороги й підтвердження аномалій, групування за ASN/AF, знаменники вибірки та транспорт Telegram на підставних відповідях.

Основні програмні інтерфейси: `ping`, `RulesTests`, `TelegramTests`.

### [collector/tests/test_audit_fixes.py](../collector/tests/test_audit_fixes.py)

Регресійні сценарії: повна втрата без RTT, тривалий disconnect, відновлення лише за новими даними, свіжість та відокремлення епізодів.

Основні програмні інтерфейси: `ping`, `AuditFixes`.

### [collector/tests/test_clickhouse_daily.py](../collector/tests/test_clickhouse_daily.py)

Підставне сховище перевіряє добове згортання, порядок збереження й очищення та повтор після помилки запису дня.

Основні програмні інтерфейси: `DailyBackend`, `DailyTests`.

### [collector/tests/test_clickhouse_store.py](../collector/tests/test_clickhouse_store.py)

Підставне сховище перевіряє повтор після часткового запису, відсутність подвійного підрахунку, накопичення статистик і відхилення старих даних.

Основні програмні інтерфейси: `FakeClickHouse`, `ClickHouseOnlyTests`.

### [collector/tests/test_models.py](../collector/tests/test_models.py)

Перевіряє нормалізацію, відсоток втрат, стабільність event ID і події статусів.

Основні програмні інтерфейси: `ModelTests`.

### [collector/tests/test_retention.py](../collector/tests/test_retention.py)

Перевіряє межу 04:00 Europe/Kyiv, перехід літнього часу, часові ключі, NULL RTT і валідність пакетів.

Основні програмні інтерфейси: `RetentionTests`.

### [collector/tests/test_subscriptions.py](../collector/tests/test_subscriptions.py)

Перевіряє дозволені Telegram-команди та приватний характер підписки без реальних повідомлень.

Основні програмні інтерфейси: `CommandsTests`.


## clickhouse/init

### [clickhouse/init/001_schema.sql](../clickhouse/init/001_schema.sql)

Первинні сирі таблиці ping_results і probe_events, їхні типи, сортування й версії.

### [clickhouse/init/002_analytics.sql](../clickhouse/init/002_analytics.sql)

Погодинні/поденні накопичувачі та початкові сумісні views. Автоматичний TTL не застосовується: порядок очищення контролює обробник.

### [clickhouse/init/003_reporting.sql](../clickhouse/init/003_reporting.sql)

Довідник зондів і сумісні live, country та activity views у monitoring.

### [clickhouse/init/004_clickhouse_only.sql](../clickhouse/init/004_clickhouse_only.sql)

Таблиця службових маркерів retention_runs і два materialized view, що фіксують факт вставки.


## clickhouse/migrations

### [clickhouse/migrations/006_analytics_views.sql](../clickhouse/migrations/006_analytics_views.sql)

SQL-знімок визначень analytics для ручного перегляду/міграції. Чинний генератор — app.analytics_views; bootstrap використовує саме його.


## postgres/init

### [postgres/init/001_schema.sql](../postgres/init/001_schema.sql)

Навмисно мінімальний файл: фіксує, що вимірювання й довідник більше не створюються в PostgreSQL.

### [postgres/init/002_alerts.sql](../postgres/init/002_alerts.sql)

Базові інциденти, cooldown та outbox Telegram зі зв’язками й індексами.

### [postgres/init/003_telegram_subscriptions.sql](../postgres/init/003_telegram_subscriptions.sql)

Підписники, позиція getUpdates, відповіді на команди та доставки кожному адресату.

### [postgres/init/004_incident_state.sql](../postgres/init/004_incident_state.sql)

Стан епізодів і підключення, зв’язок подій з епізодом, діагностика обробки та внутрішні операційні views.


## postgres/migrations

### [postgres/migrations/008_reporting_views.sql](../postgres/migrations/008_reporting_views.sql)

SQL-знімок п’яти reporting-в’ю. Чинний генератор — app.operational_views.


## nifi

### [nifi/api_client.py](../nifi/api_client.py)

Локальний REST-клієнт NiFi. Знаходить контейнер і опублікований порт через Compose, читає налаштовані облікові дані з Docker, чекає готовності й отримує тимчасовий JWT без друку секретів.

Основні програмні інтерфейси: `api`.

### [nifi/build_pipeline.py](../nifi/build_pipeline.py)

Відтворює 11 процесорів і зв’язки. Налаштовує Kafka, Groovy-перевірки, HTTP sinks та відхилення; при повторі тимчасово зупиняє власні процесори й відновлює роботу.

Основні програмні інтерфейси: `restore_running`, `processor`, `connect`.


## tools

### [tools/bootstrap.py](../tools/bootstrap.py)

Основна команда першого запуску. Створює локальні паролі, перевіряє Compose, збирає один спільний образ, запускає стек, налаштовує NiFi та обидва шари в’ю.

Основні програмні інтерфейси: `run`, `environment`, `main`.

### [tools/build_reference_docs.py](../tools/build_reference_docs.py)

Будує цей пофайловий довідник і докладний каталог БД із версійованого JSON метаданих. Перевіряє, щоб кожен файл та кожна назва поля мали пояснення.

Основні програмні інтерфейси: `description`, `files_reference`, `database_reference`.

### [tools/check_publication.py](../tools/check_publication.py)

Перевіряє тільки файли, які відстежує Git: шукає типові токени, приватні ключі, локальні шляхи та файли стану. Не є заміною повного аудиту секретів.

Основні програмні інтерфейси: `main`.

### [tools/configure_telegram.py](../tools/configure_telegram.py)

Приховано запитує токен і записує його тільки в .secrets/telegram/config.json. Сам не надсилає повідомлень і не перевіряє токен через мережу.

Основні програмні інтерфейси: `main`.

### [tools/export_kpi_dictionary.py](../tools/export_kpi_dictionary.py)

Оновлює Markdown та CSV-словник із app.kpi_catalog. CSV містить назви й пояснення; докладні формули залишаються в Markdown.

### [tools/export_schema_reference.py](../tools/export_schema_reference.py)

Зчитує лише метадані таблиць, в’ю, стовпців і обмежень із запущених БД та зберігає docs/schema_reference.json; рядки прикладних даних не експортує.

Основні програмні інтерфейси: `run`, `main`.

### [tools/verify_analytics_views.py](../tools/verify_analytics_views.py)

Виконує SELECT до 20 analytics-в’ю, перевіряє відсутність формульних колонок і звіряє поденні суми, DISTINCT та зважені середні зі сховищем. На хості делегує перевірку Docker.


## docs

### [docs/ANALYTICS_GUIDE.md](../docs/ANALYTICS_GUIDE.md)

Коротка практична карта в’ю та відповідність полів осям графіків.

### [docs/CONNECTIONS.md](../docs/CONNECTIONS.md)

Параметри DBeaver, JDBC, Docker DNS, доступ з іншого ПК, томи та типові проблеми підключення.

### [docs/DATABASE_REFERENCE.md](../docs/DATABASE_REFERENCE.md)

Повний каталог усіх таблиць, зв’язків і views обох СУБД, із типами та поясненнями кожного стовпця.

### [docs/FILES_REFERENCE.md](../docs/FILES_REFERENCE.md)

Повний перелік папок і файлів із призначенням та інтерфейсами Python-модулів.

### [docs/FINAL_ANALYTICS.md](../docs/FINAL_ANALYTICS.md)

Повне пояснення кінцевої аналітики: зерно рядка, KPI, приклади розрахунків, готові графіки й обмеження висновків.

### [docs/KPI_DICTIONARY.csv](../docs/KPI_DICTIONARY.csv)

Машиночитаний словник: код, українська назва, одиниця та пояснення; без колонки формул.

### [docs/KPI_DICTIONARY.md](../docs/KPI_DICTIONARY.md)

Каталог усіх 25 внутрішніх/публічних KPI з одиницями, формулами та правилами агрегації.

### [docs/PROJECT_ANALYSIS.md](../docs/PROJECT_ANALYSIS.md)

Повний аналіз архітектури, потоків, контрактів, відновлення, відповідальності компонентів, реалізованих можливостей і обмежень.

### [docs/START_HERE.md](../docs/START_HERE.md)

Послідовний запуск із нуля: підготовка, клонування, bootstrap, контрольні запити, DBeaver, Telegram, щоденна робота та діагностика.

### [docs/VALIDATION.md](../docs/VALIDATION.md)

Зафіксований результат перевірки публікаційного пакета: порожні томи, bootstrap, views і тести. Не є поточним live-статусом сервера.

### [docs/schema_reference.json](../docs/schema_reference.json)

Версійований знімок структури: 44 об’єкти ClickHouse та 18 PostgreSQL, стовпці, SQL визначень і обмеження. Не містить вимірювань або даних підписників.

## Що створюється локально та не входить до Git

| Об’єкт | Призначення |
|---|---|
| `.env` | Реальні локальні паролі й порти. |
| `.secrets/telegram/config.json` | Токен бота; не передавати в репозиторій. |
| Docker-томи | Вимірювання, агрегати, операційні дані, черги NiFi та Kafka. |
| `collector_state/checkpoints.json` усередині тому | Завершені REST-діапазони; не SQL-таблиця. |
| `analytics_state/pending-ingestion.json` усередині тому | Лише незавершений пакет запису; видаляється після підтвердження. |
| Кеші Python, журнали, backups | Локальні допоміжні файли; виключені .gitignore. |
