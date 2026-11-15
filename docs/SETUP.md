# Встановлення, підключення та супровід

[Головна](../README.md) · [Архітектура](ARCHITECTURE.md) · [Аналітика](ANALYTICS.md)

- [Покрокове встановлення](#installation)
- [Параметри, порти та DBeaver](#connections)
- [Перегляд і відтворення Metabase](#metabase)
- [Онлайн-копія налаштувань із паролями](#online-configuration)
- [Супровід, перевірки та очищення](#maintenance)

<a id="installation"></a>

## Покрокове встановлення

### Крок 1. Підготувати комп’ютер

Потрібні Git, Python 3.10+ та Docker Desktop/Engine з Compose v2. На Windows використовуйте Linux containers. Рекомендовано виділити Docker щонайменше 8 ГБ RAM. Інтернет потрібний для образів, залежностей та RIPE. Запустіть Docker Desktop, дочекайтеся готовності engine, відкрийте PowerShell або термінал:

```bash
git --version
python --version
docker version
docker compose version
```

У docker version має відповідати Client і Server. Якщо python у Windows не знайдений, використайте `py -3 --version` і замінюйте далі python на py -3.

### Крок 2. Клонувати проєкт

```bash
git clone https://github.com/uneavk/ripe-atlas-monitoring.git
cd ripe-atlas-monitoring
```

Репозиторій приватний. GitHub запропонує увійти в дозволений акаунт через браузер або збережений Git Credential Manager. Для чужого акаунта без доступу посилання може показувати 404. Запрошення надаються власником окремо.

У папці мають бути README.md, compose.yaml та каталоги collector, clickhouse, postgres, nifi, bi, tools, docs, artifacts. Усі подальші команди виконуються з кореня репозиторію.

### Крок 3. Обрати конфігурацію

Для стандартного першого запуску .env вручну не створюйте: bootstrap сам збереже випадкові паролі.

Для відновлення саме наявної конфігурації спочатку отримайте [онлайн-копію через GitHub Actions](#online-configuration). Це окремий шлях: новому незалежному встановленню можна створити власні паролі. Не перезаписуйте .env діючого стека шаблоном.

Для інших портів спочатку скопіюйте шаблон. PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Відкрийте .env у редакторі. Замініть усі чотири replace_with_... на різні випадкові паролі. Для POSTGRES_PASSWORD використовуйте випадкові латинські літери/цифри без URI-спецсимволів; пароль NiFi має бути не коротший за 12 символів. Bootstrap не запуститься із заглушками.

Для другої незалежної копії на тому самому ПК змініть COMPOSE_PROJECT_NAME та зайняті зовнішні порти. Внутрішні назви postgres, clickhouse, kafka у коді змінювати не потрібно. Після створення .env можна перевірити:

```bash
docker compose config --quiet
```

Файл .env приватний; не додавайте його в Git або повідомлення іншим людям.

### Крок 4. Запустити автоматичне налаштування

```bash
python tools/bootstrap.py
```

Скрипт створює .env і локальний каталог Telegram, перевіряє Compose, один раз збирає спільний образ collector/analytics/alerts, запускає стек, створює теми Kafka, очікує NiFi, налаштовує 11 процесорів, а потім створює словники, 20 в’ю ClickHouse та 5 reporting-в’ю PostgreSQL. Далі очікує Metabase, створює read-only підключення, колекцію, 3 дашборди та 26 SQL-карток. Наприкінці друкує стан контейнерів і Ready.

Перший запуск може тривати кілька хвилин. Waiting for NiFi initialization — очікуване повідомлення запуску JVM. Traceback або завершення з помилкою означає, що налаштування ще не завершене; перейдіть до діагностики нижче.

### Крок 5. Перевірити контейнери

```bash
docker compose ps -a
docker compose logs --tail 30 collector
docker compose logs --tail 30 analytics
docker compose logs --tail 30 alerts
```

Kafka, PostgreSQL, ClickHouse та analytics повинні бути healthy; постійні сервіси — запущені. kafka-init має завершитися Exited (0). У collector очікуються backfill_started, backfill_completed, websocket_connected та Kafka-публікації. Без токена telegram_configured=False є нормальним.

Перше REST-дозавантаження послідовне за чотирма джерелами; черги NiFi можуть тимчасово зростати. Порожній IPv6 у перші секунди не є доказом аварії IPv6.

### Крок 6. Відкрити службові інтерфейси

| Інтерфейс | Стандартна адреса | Вхід |
|---|---|---|
| Metabase | http://localhost:3000 | admin@ripe.local; пароль у .secrets/metabase/admin.json |
| NiFi | https://localhost:8443/nifi | NIFI_USERNAME / NIFI_PASSWORD із .env |
| Kafka UI | http://localhost:8080 | Теми та consumer groups |
| Adminer | http://localhost:8081 | PostgreSQL, сервер postgres, облікові дані з .env |

NiFi використовує локальний сертифікат; браузер може показати попередження. Перевірте адресу власного локального сервера перед продовженням. У канві мають бути три гілки Read → Validate and transform → Store та маршрут відхилень. Порожня канва після Ready не є очікуваним результатом.

### Крок 7. Підключити ClickHouse у DBeaver

1. Database → New Database Connection → ClickHouse.
2. Host localhost, Port 8123 або CLICKHOUSE_HTTP_PORT.
3. Database analytics.
4. User CLICKHOUSE_USER, Password CLICKHOUSE_PASSWORD із .env.
5. Test Connection → Finish; за потреби завантажте запропонований JDBC-драйвер.
6. Refresh → analytics → Views → SQL Editor.

```sql
SELECT * FROM analytics.measurement_directory ORDER BY measurement_id;
SELECT * FROM analytics.data_freshness ORDER BY measurement_id;
```

Перший запит завжди показує чотири визначення. Другий — реальний стан надходження. Після обробки backfill очікуються дані IPv4 та IPv6, кількості зондів можуть різнитися.

```sql
SELECT measured_at, probe_id, target_name, ip_version, avg_rtt_ms, packet_loss_pct
FROM analytics.measurements_live
ORDER BY measured_at DESC
LIMIT 100;
```

### Крок 8. Відкрити готові дашборди Metabase

Bootstrap уже створює Metabase, підключення для читання та три дашборди. Відкрийте http://localhost:3000 (або METABASE_PORT з .env), увійдіть як admin@ripe.local. Пароль - поле password у локальному .secrets/metabase/admin.json. Відкрийте колекцію RIPE Atlas · Лабораторна СТП. Посилання саме вашої інсталяції зберігаються у .secrets/metabase/manifest.json.

Почніть зі свіжості, потім подивіться RTT, втрати та карту. Фільтр measurement=2001 показує K-root IPv6. Історія й журнал інцидентів знаходяться у двох інших дашбордах. [Повна інструкція Metabase](#metabase).

Нижче наведений необов’язковий приклад власного графіка:

```sql
SELECT period_start, target_name, ip_version, avg_rtt_ms, packet_loss_pct
FROM analytics.network_5minutes
ORDER BY period_start, target_name, ip_version;
```

У DBeaver/BI: X — period_start, Y — avg_rtt_ms або packet_loss_pct, серії — target_name та ip_version. Для завершених годин використовуйте network_hourly, для довгої історії — network_daily. Нова година має спочатку завершитися; перший день з’явиться після фіналізації о 04:00 за Києвом. Порожній період не заповнюйте нульовими втратами. Пояснення всіх графіків і формул: [ANALYTICS.md](ANALYTICS.md).

### Крок 9. Підключити PostgreSQL у DBeaver

1. New Database Connection → PostgreSQL.
2. Host localhost, Port 5432 або POSTGRES_PORT.
3. Database POSTGRES_DB; User POSTGRES_USER; Password POSTGRES_PASSWORD.
4. Test Connection → Finish → Schemas → reporting → Views.

```sql
SELECT * FROM reporting.incidents ORDER BY started_at DESC;
SELECT * FROM reporting.incidents_daily ORDER BY day;
SELECT * FROM reporting.processing_errors_hourly ORDER BY period_start DESC;
```

Без реальних інцидентів порожній результат допустимий. Не створюйте вигадані аварії для наповнення графіка. PostgreSQL містить операційні дані; ping-вимірювання знаходяться в ClickHouse.

### Крок 10. Налаштувати власного Telegram-бота

Отримайте токен власного бота через BotFather. Не публікуйте його.

```bash
python tools/configure_telegram.py
docker compose restart alerts
```

Введіть токен у прихованому запиті. Потім у Telegram надішліть цьому боту /start та дочекайтеся підтвердження. Кожен учасник підписується у своєму приватному чаті. /status перевіряє підписку, /stop вимикає її. Токен зберігається тільки в .secrets/telegram/config.json.

Конфігуратор сам не викликає getMe та не надсилає штучний інцидент. Відповідь /start перевіряє прийом команд і транспорт, а не весь шлях реальної аномалії. Не запускайте два alerts із тим самим токеном — вони конкуруватимуть за getUpdates.

### Крок 11. Запустити перевірки

```bash
docker compose run --rm --no-deps analytics python -m unittest discover -s tests -p "test_*.py"
python tools/verify_analytics_views.py
```

Тести мають завершитися OK. Перевірка в’ю виконує SELECT і звіряє наявні денні статистики. 0 поденних груп на нових томах є очікуваним і не означає перевірки історії, якої ще немає.

Для оновлення довідника після зміни схеми:

```bash
python tools/docs.py --schema
python tools/docs.py
```

Експортуються метадані, не рядки вимірювань чи дані підписників.

### Крок 12. Щоденна робота й оновлення

```bash
docker compose stop
docker compose up -d
```

Ці команди зберігають дані в Docker-томах. down без -v також зберігає томи, а down -v їх видаляє і не потрібний для звичайного запуску.

Перед оновленням збережіть важливі БД і експорт вручну зміненого NiFi:

```bash
git pull --ff-only
python tools/bootstrap.py
```

Повторний bootstrap використовує існуючі .env і томи та переналаштовує керовані процесори. Init SQL автоматично виконується тільки на порожніх томах. Структурні міграції вже створених БД застосовуються відповідно до конкретного оновлення: bootstrap не є універсальним менеджером усіх міграцій.

### Крок 13. Підключити інший ПК

У тій самій мережі потрібні доступний IP Docker-хоста, опублікований порт та дозволений мережевий доступ. Налаштуйте BIND_ADDRESS, застосуйте Compose, у DBeaver іншого ПК вкажіть IP хоста замість localhost. Для зовнішнього доступу до NiFi задається також NIFI_PROXY_HOST; локальний localhost залишається дозволеним для конфігуратора.

Для іншої локальної мережі потрібний окремий мережевий маршрут. GitHub відкриває код, не базу. Інша людина може клонувати репозиторій і запустити власну незалежну копію; її історія буде окремою. Повні адреси й обмеження: [SETUP.md](#connections).

### Діагностика

| Симптом | Перевірка | Дія / пояснення |
|---|---|---|
| Немає Docker Server | docker version | Запустити Docker Desktop/Linux engine. |
| Порт зайнятий | .env, docker compose ps | Змінити зовнішній порт; для другої копії — project name. |
| kafka-init не завершився з 0 | docker compose logs kafka-init | Collector/alerts очікують створення тем. |
| Waiting for NiFi | docker compose logs --tail 80 nifi | JVM потребує часу; перевірити пароль і порт. |
| Invalid host header | NIFI_PORT / NIFI_PROXY_HOST | Адреса має бути серед дозволених host headers. |
| Зростають черги | NiFi Store і analytics logs | Дозавантаження, повільна БД або повтори; не видаляти чергу. |
| IPv6 поки порожній | data_freshness, collector logs | Послідовний backfill і менша вибірка. |
| Hourly/daily порожні | Час запуску | Використати network_5minutes до завершення періоду. |
| Новий пароль .env не працює | Наявний том | .env не змінює пароль існуючого користувача БД. |
| Telegram мовчить | alerts logs, /start, config | Токен, блокування, друга копія або API-помилка. |

Зберігайте повідомлення про помилки без секретів. Factory reset Docker, видалення томів і очищення черг не є штатним способом налагодження проєкту.

<a id="connections"></a>

## Параметри, порти та DBeaver

Для послідовного першого встановлення використовуйте [SETUP.md](#installation). Нижче — довідник параметрів.

### Усі параметри локального середовища

| Змінна | Типове значення | Призначення |
|---|---|---|
| COMPOSE_PROJECT_NAME | ripe-monitoring | Префікс контейнерів, мережі й томів. Змініть для незалежної другої копії. |
| APP_IMAGE | ripe-monitoring-app:local | Тег спільного образу collector, analytics та alerts. |
| BIND_ADDRESS | 127.0.0.1 | Інтерфейс хоста для зовнішніх портів. За замовчуванням тільки локальний ПК. |
| POSTGRES_DB | ripe_monitoring | Назва операційної БД. |
| POSTGRES_USER | ripe | Початковий користувач PostgreSQL. |
| POSTGRES_PASSWORD | Генерується bootstrap | Початковий пароль; латинські літери/цифри спрощують URI. |
| POSTGRES_PORT | 5432 | Опублікований порт PostgreSQL на хості. |
| CLICKHOUSE_USER | ripe | Початковий користувач ClickHouse. |
| CLICKHOUSE_PASSWORD | Генерується bootstrap | Початковий пароль ClickHouse. |
| CLICKHOUSE_HTTP_PORT | 8123 | HTTP/JDBC-порт для DBeaver. |
| CLICKHOUSE_NATIVE_PORT | 9000 | Native-порт ClickHouse; не потрібний для HTTP/JDBC прикладів. |
| NIFI_USERNAME | admin | Користувач локального NiFi. |
| NIFI_PASSWORD | Генерується bootstrap | Пароль NiFi, щонайменше 12 символів. |
| NIFI_PORT | 8443 | HTTPS-порт NiFi на хості. |
| NIFI_PROXY_HOST | localhost, якщо не задано | Додаткова дозволена host-назва NiFi; опційно додається до .env для зовнішнього UI. |
| KAFKA_PORT | 29092 | Зовнішній Kafka listener; усередині Docker використовується kafka:9092. |
| KAFKA_ADVERTISED_HOST | localhost | Ім’я/IP, яке Kafka повертає зовнішнім клієнтам. |
| KAFKA_UI_PORT | 8080 | Локальна сторінка Kafka UI. |
| ADMINER_PORT | 8081 | Локальна сторінка Adminer. |
| BACKFILL_MINUTES | 60 | Максимальний горизонт REST-дозавантаження, не строк зберігання БД. |
| METABASE_DB_PASSWORD | Генерується bootstrap | Пароль службової PostgreSQL-БД Metabase, не пароль входу у вебінтерфейс. |
| METABASE_PORT | 3000 | HTTP-порт Metabase на комп’ютері запуску. |

Країна UA і чотири measurement ID явно задані у compose.yaml. Для підтриманого розширення джерел недостатньо змінити лише одну змінну: узгодьте collector, analytics_views.MEASUREMENTS, контроль свіжості та підписи. Настроювання довільних measurement через UI не реалізоване.

Зміна порту в .env не змінює внутрішній порт контейнера. Зміна початкового пароля в .env не мігрує облікові дані вже ініціалізованого тому.

### Перший запуск

1. Запустіть Docker Desktop у режимі Linux containers.
2. Відкрийте папку скопійованого репозиторію.
3. Виконайте `python tools/bootstrap.py` (Windows: також можна `py -3 tools/bootstrap.py`).
4. Зачекайте завершення налаштування NiFi, Metabase та повідомлення Ready.
5. Відкрийте локальний `.env`: там адреси портів, користувачі й випадково створені паролі.

Усі команди `docker compose` запускаються з кореня репозиторію. Якщо вже працює інша копія цього проєкту на тому самому комп’ютері, до запуску створіть `.env` за шаблоном, змініть `COMPOSE_PROJECT_NAME` і зайняті порти. Паролі замініть на різні випадкові значення. Для POSTGRES_PASSWORD використовуйте випадкові латинські літери й цифри: значення включається в URI підключення.

### ClickHouse у DBeaver

1. Database → New Database Connection → ClickHouse.
2. Host: `localhost`.
3. Port: `8123` (значення CLICKHOUSE_HTTP_PORT, якщо змінювали).
4. Database: `analytics` для готових в’ю або `monitoring` для таблиць зберігання.
5. Username: CLICKHOUSE_USER із `.env`.
6. Password: CLICKHOUSE_PASSWORD із `.env`.
7. Test Connection → Finish. Якщо DBeaver пропонує завантажити JDBC-драйвер, погодьтеся на його встановлення.
8. Оновіть підключення (Refresh) та відкрийте `analytics → Views`.

JDBC URL: `jdbc:clickhouse:http://localhost:8123/analytics`.

Перший запит:

```sql
SELECT * FROM analytics.data_freshness ORDER BY measurement_id;
```

Перегляд тільки IPv6:

```sql
SELECT measured_at, probe_id, target_name, ip_version, avg_rtt_ms, packet_loss_pct
FROM analytics.measurements_live
WHERE ip_version = 'IPv6'
ORDER BY measured_at DESC
LIMIT 100;
```

Графік затримки:

```sql
SELECT period_start, target_name, ip_version, avg_rtt_ms
FROM analytics.network_hourly
ORDER BY period_start, target_name, ip_version;
```

### PostgreSQL у DBeaver

1. Database → New Database Connection → PostgreSQL.
2. Host: `localhost`, Port: `5432` (або POSTGRES_PORT).
3. Database: POSTGRES_DB із `.env`, за замовчуванням `ripe_monitoring`.
4. Username / Password: POSTGRES_USER / POSTGRES_PASSWORD із `.env`.
5. Test Connection → Finish.
6. Schemas → `reporting` → Views — готові операційні звіти; `public` — таблиці інцидентів, підписок і доставки.

JDBC URL: `jdbc:postgresql://localhost:5432/ripe_monitoring`.

```sql
SELECT * FROM reporting.incidents ORDER BY started_at DESC;
SELECT * FROM reporting.incidents_daily ORDER BY day;
SELECT * FROM reporting.processing_errors_hourly ORDER BY period_start DESC;
```

PostgreSQL не містить копій сирих мережевих вимірювань. Вони та їхні погодинні/поденні агрегати знаходяться в ClickHouse.

### Адреси всередині Docker

| Клієнт | Адреса |
|---|---|
| Python / NiFi → Kafka | kafka:9092 |
| NiFi → HTTP-обробник | http://analytics:8082/ingest/ping_results |
| NiFi → довідник | http://analytics:8082/ingest/probe_directory |
| NiFi → статуси | http://analytics:8082/ingest/probe_events |
| Застосунок → ClickHouse | http://clickhouse:8123/ |
| Детектор → PostgreSQL | postgres:5432 |

`localhost` усередині контейнера означає саме цей контейнер, тому для зв’язку між сервісами використовуються їхні Docker-імена. Порт 8082 назовні не публікується.

### Інший комп’ютер у тій самій мережі

За замовчуванням порти доступні тільки на комп’ютері запуску. Щоб дозволити підключення з локальної мережі, змініть `BIND_ADDRESS` у `.env` на локальну адресу хоста або `0.0.0.0`, застосуйте `docker compose up -d` і налаштуйте дозволений доступ у брандмауері Windows. З іншого ПК у DBeaver вкажіть LAN-IP комп’ютера з Docker замість localhost та відповідний опублікований порт. Користувачі й паролі залишаються з `.env`.

Kafka додатково потребує `KAFKA_ADVERTISED_HOST`, що доступний зовнішньому клієнту, наприклад LAN-IP хоста. Для DBeaver доступ до Kafka не потрібний.

### Інша локальна мережа / Інтернет

Публічний GitHub містить код, а не запущені бази. `localhost` і Docker-імена недоступні з іншої мережі. Для доступу до єдиної запущеної БД потрібний окремо налаштований мережевий шлях до комп’ютера-хоста. Сам Docker такого зовнішнього маршруту не створює. Цей репозиторій не налаштовує роутер або зовнішній сервер. Інша людина може також клонувати репозиторій і запустити незалежну копію з власними даними.

### Зберігання та резервування

Дані знаходяться в іменованих Docker-томах: postgres_data, clickhouse_data, kafka_data, collector_state, analytics_state та томах NiFi. Реальні назви мають префікс COMPOSE_PROJECT_NAME. Ручний перенос папки репозиторію не переносить ці томи. Для перенесення накопиченої історії потрібні окремі резервні копії PostgreSQL і ClickHouse; вихідний репозиторій містить лише схеми.

Не додавайте `.env`, `.secrets`, дампи чи журнали з ідентифікаторами Telegram у Git. Каталоги резервних копій і стану вже виключені у `.gitignore`.

### Якщо щось не працює

- Docker API недоступний: перевірте, чи запущений Docker Desktop і Linux engine.
- Порт зайнятий: змініть його в `.env`, потім виконайте `docker compose up -d`.
- NiFi ще запускається: перегляньте `docker compose logs --tail 80 nifi`; скрипт початкового налаштування очікує його готовності.
- Немає даних: перевірте `analytics.data_freshness`, журнали collector та черги NiFi. Перший REST-backfill може заповнювати джерела послідовно.
- Погодинний графік порожній у новій системі: готові години публікуються після завершення години; для поточного стану використайте network_5minutes.
- Поденного рядка ще немає: попередня доба фіналізується після 04:00 за Києвом.
- Пароль змінили у `.env`, але БД відмовляє: змінні початкового користувача застосовуються при першій ініціалізації тому. Зміна `.env` сама по собі не змінює пароль у вже створеній БД.
- Telegram не відповідає: перевірте локальну конфігурацію, `/start`, журнали alerts та відсутність другої копії бота з тим самим токеном.

### Metabase

Типовий порт METABASE_PORT=3000, адреса http://localhost:3000. Адміністратор admin@ripe.local, пароль у локальному .secrets/metabase/admin.json. METABASE_DB_PASSWORD у .env є паролем службової PostgreSQL-БД, а не паролем входу в інтерфейс. Власний том metabase_data зберігає налаштування BI. Докладно: [SETUP.md](#metabase).

<a id="metabase"></a>

## Перегляд і відтворення Metabase

### Вхід і перегляд

Після `python tools/bootstrap.py` відкрийте http://localhost:3000. Якщо `METABASE_PORT` змінено, використайте свій порт. Логін `admin@ripe.local`, пароль - локальне поле `password` у `.secrets/metabase/admin.json`. Файл не входить до Git.

[Довідник кожної картки, її джерел, типу й фільтра](ANALYTICS.md#dashboard-cards).

У колекції **RIPE Atlas · Лабораторна СТП** є 3 дашборди та 26 карток:

| Дашборд | Карток | Що читати |
|---|---|---|
| 01 · Поточний стан мережі | 10 | Давність джерел, кількість зондів IPv4/IPv6, RTT, втрати, серії з відповіддю, карта |
| 02 · Історія та провайдери | 8 | Завершені години, дні, покриття, ASN та відхилення зондів |
| 03 · Інциденти та якість потоку | 8 | Відкриті епізоди, нові епізоди за датами, тривалість, DLQ та доставки |

ID не фіксовані. Локальний `.secrets/metabase/manifest.json` містить URL саме вашої інсталяції. Автооновлення вмикається у дашборді або фрагментом URL `#refresh=60`.

Фільтр measurement: 1001 K-root IPv4, 2001 K-root IPv6, 1004 F-root IPv4, 2004 F-root IPv6. Він застосовується до карток з явно налаштованим параметром. Графіки з усіма чотирма серіями залишаються порівняльними.

### Як читати результати

Починайте зі свіжості. Відсутні дані не є нульовими втратами. Поточний п’ятихвилинний інтервал може бути неповним. У погодинному зрізі показуються завершені години. Дні з’являються після фіналізації о 04:00 Europe/Kyiv. Поденні графіки обмежені останнім роком для помірного обсягу запиту; давніші підсумки залишаються у БД безстроково.

Карта показує останній результат на зонд обраного measurement і лише зонди з координатами. Це не покриття всіх адрес України. ASN-рейтинг використовує щонайменше чотири спостережувані зонди за останню завершену годину. Відхилення RTT від середнього вибірки не є правилом HIGH_RTT, яке використовує власний baseline.

Нові епізоди рахуються за початком епізоду, а не за кожною повторною подією. Тривалість завершених епізодів не є доведеним downtime усієї мережі. Діагностика DLQ групується за часом запису помилки, доставка - за датою створення outbox і поточним статусом.

### Відтворення налаштувань

Джерело конфігурації - `bi/dashboards.py`. `bi/dashboard_spec.json` є читабельним експортом SQL, типів графіків і налаштувань без прив’язки до локальних ID та без облікових даних. Це власний формат проєкту, а не ліцензійний export/import Metabase.

```bash
python tools/setup_metabase.py
python tools/verify_metabase.py
```

Setup читає назву проєкту з `.env`, підключається до Metabase, створює або оновлює власну колекцію й картки, а також окремих `bi_reader`. ClickHouse читається через SELECT до analytics/monitoring, PostgreSQL - через reporting та потрібне внутрішнє в’ю. Таблиці Telegram-підписників не надаються BI-користувачу.

Setup є ідемпотентним щодо власних назв. Ручні зміни власних карток можуть бути перезаписані, тому переносьте узгоджені зміни у специфікацію. Чужі дашборди скрипт не видаляє. Якщо локально вручну змінено адміністративний пароль, актуалізуйте приватний admin.json перед повторним setup.

Для наявного старого стека, який не містить Metabase, залишено **додатковий** `compose.bi.yaml`. Він приєднується до вже створеної мережі Docker. Це не другий обов’язковий запуск нового проєкту:

```bash
docker compose --env-file .secrets/metabase/deployment.env -f compose.bi.yaml up -d
python tools/setup_metabase.py --project ripe-monitoring
```

Локальний deployment.env повинен містити COMPOSE_PROJECT_NAME, BI_DOCKER_NETWORK, METABASE_DB_PASSWORD, METABASE_PORT та BIND_ADDRESS. Його пароль генерується окремо й не завантажується до Git. Для нової інсталяції використовуйте основний compose.yaml і bootstrap, а не обидва способи одночасно.

### Зберігання й діагностика

Власна БД Metabase зберігає картки, колекції та користувачів у томі `metabase_data`. Це службові таблиці постачальника, вони не додаються до каталогу 62 прикладних об’єктів. Втрата admin.json не видаляє користувача в цій БД і не скидає його пароль. Зберігайте локальну копію файлів доступу та резервні копії томів поза публічним Git.

- Сторінка недоступна: перевірте Docker Desktop, `docker compose ps` і налаштований порт.
- Сервіс ще запускається: `docker compose logs --tail 50 metabase metabase-db`.
- Графік порожній: перевірте свіжість, джерело, фільтр та наявність потрібного часового рівня.
- Помилка запиту: `python tools/verify_metabase.py` збереже подробиці тільки в `.secrets/metabase/`.
- Зміна .env не змінює пароль уже існуючої БД. Не видаляйте томи для виправлення входу.

`bi/validation.json` та скріншоти є збереженими доказами попередньої перевірки, а не онлайн-моніторингом. Повторна перевірка перезаписує звіт із датою виконання. Скріншоти від 09.11.2026 зібрані у `artifacts/screenshots/`.

<a id="online-configuration"></a>

## Онлайн-копія налаштувань із паролями

Репозиторій приватний. Для відкриття потрібний дозволений GitHub-акаунт, самого посилання недостатньо. Запрошення автоматично не надсилаються.

Код і специфікації аналітики зберігаються як звичайні файли Git. Копію налаштувань із робочими паролями можна окремо зберегти в зашифрованому repository secret **RIPE_CONFIGURATION_BACKUP**. Секрет має бути налаштований перед використанням кнопки завантаження. Якщо його немає, workflow завершиться зрозумілою помилкою й не створить архів.

### Що містить копія

| Файл | Зміст |
|---|---|
| `.env` | Налаштування саме цієї локальної копії, порти, імена та паролі БД/NiFi |
| `.secrets/metabase/admin.json` | Пароль входу в Metabase та пароль облікових записів BI-reader |
| `.secrets/metabase/manifest.json` | Локальні ID та посилання дашбордів |
| `.secrets/metabase/deployment.env` | Параметри окремого підключення Metabase до наявного стека |

`configuration-info.json` містить час знімка, назву репозиторію та контрольні суми файлів. Це точний знімок конфігурації, не дамп БД. Telegram-токен, вимірювання, підписники, журнали й Docker-томи до цієї копії не включаються.

GitHub Secrets не показує збережене значення назад у налаштуваннях. Для отримання файлів створено окремий ручний workflow. Він працює лише у приватному репозиторії, не запускає сервіси й не надсилає повідомлень.

### Як завантажити налаштування

1. Увійдіть у дозволений акаунт GitHub і відкрийте репозиторій.
2. Перейдіть до **Actions → Download saved configuration**.
3. Натисніть **Run workflow**, оберіть основну гілку та запустіть.
4. Дочекайтеся успішного завершення й відкрийте цей запуск.
5. У **Artifacts** завантажте **ripe-configuration-backup**.
6. Розпакуйте завантаження. Усередині буде `configuration-backup.zip` із чотирма файлами та інформацією про знімок.

Завантаження доступне один день. Зашифрований secret зберігається, тому пізніше можна створити новий download запуском workflow. Облікові записи, які мають доступ до приватного репозиторію й артефактів, можуть завантажити цей файл з робочими паролями. Вміст архіву не виводиться в журнали Actions.

### Використання після завантаження

Локальні конфігураційні файли потрібні сервісам під час запуску. Онлайн-копія забезпечує можливість їх відновити, а не замінює локальне читання .env та admin.json.

На новому комп’ютері спочатку клонуйте приватний репозиторій з авторизацією, потім розмістіть файли за їхніми відносними шляхами. Не перезаписуйте конфігурацію іншого вже запущеного стека без звіряння імен, портів і томів. Локальна .env у знімку може описувати тестовий стек з іншими портами, а deployment.env - окремий робочий Metabase.

Для нового порожнього розгортання використовуйте основний bootstrap. Він застосує налаштування Metabase й оновить manifest для нових локальних ID. Для наявної БД зміна значення у .env сама собою не змінює пароль у томі. Цей архів не відновлює вимірювання або історію інцидентів.

Копія є знімком. Подальші зміни паролів не оновлюють GitHub Secret автоматично. Читабельні робочі паролі не додаються до історії комітів.

<a id="maintenance"></a>

## Супровід, перевірки та очищення

Основний каталог репозиторію містить вихідний код і конфігурації. Docker-томи містять БД і черги. Папка з кодом не є резервною копією всіх даних.

### Що входить до Git

Код Python, тести, Docker Compose, requirements, початкові SQL-схеми й генератори в’ю, конфігуратор NiFi, специфікація Metabase, словники, документація та історичні скріншоти.

`nifi/build_pipeline.py` відтворює потік через API. `bi/dashboard_spec.json` зберігає конфігурацію графіків без ID та паролів. Секретні connection details не потрібні для публікації: при запуску створюються локальні облікові записи.

### Що залишається локально

| Файл / об’єкт | Навіщо |
|---|---|
| `.env` | Паролі БД/NiFi, імена та порти |
| `.secrets/metabase/admin.json` | Вхід адміністратора Metabase і пароль BI-reader |
| `.secrets/metabase/manifest.json` | ID та посилання поточної інсталяції |
| `.secrets/metabase/deployment.env` | Локальне підключення BI до старого стека, якщо використовується |
| `.secrets/telegram/config.json` | Токен власного бота |
| Docker-томи | БД, агрегати, черги, checkpoints та службовий стан |

Файли з реальними паролями й токенами не додаються до комітів. Онлайн-копія чотирьох погоджених файлів збережена окремо в GitHub Secrets; [відновлення](#online-configuration). `.env.example` є достатнім шаблоном, bootstrap генерує випадкові значення. Паролі діючих томів не можна обертати простим редагуванням .env: потрібна окрема зміна в самій БД.

### Що можна очищувати

Python-кеші `__pycache__`, `.pytest_cache` та тимчасові локальні звіти не потрібні для розгортання. Вони ігноруються Git. Початкові схеми об’єднані у два init.sql. Аналітичні в’ю встановлюються Python-модулями під час bootstrap; окремих дублюючих SQL-знімків немає.

Не видаляйте Docker-томи, .env, .secrets, checkpoints, журнал незавершеного запису або каталоги, які змонтовані у чинні контейнери. Старий live-каталог може використовуватися працюючими контейнерами; перед його видаленням потрібна окрема перевірена міграція запуску.

### Зміна й публікація

Новий файл опишіть у FILES, нову папку - у FOLDERS в tools/docs.py. Графіки змінюйте у bi/dashboards.py. Потім виконайте:

```bash
git add .
python tools/docs.py
git add README.md docs bi/dashboard_spec.json
python tools/checks.py
git diff --cached --check
git diff --cached --stat
git commit -m "Update project implementation and documentation"
git push
```

Генератор читає список Git, тому нові файли додаються до staging перед генерацією. Після генерації оновлені довідники теж додаються до staging. tools/docs.py зберігає ручні розділи ANALYTICS.md та оновлює тільки позначені секції словника й карток.

Для локальних модульних тестів встановіть залежності: python -m pip install -r collector/requirements.txt. Команда python tools/checks.py виконує всі офлайн-перевірки. Окремо можна обрати --unit, --docs або --publication. Для актуалізації структури працюючих БД виконайте python tools/docs.py --schema.

За наявності запущеного стека додатково виконайте python tools/verify_analytics_views.py та python tools/verify_metabase.py. Вони читають дані й не надсилають Telegram-повідомлень. Модульні тести використовують підставні відповіді.
