# Покрокова інструкція запуску

[Карта документації](../README.md) · [Параметри підключення](CONNECTIONS.md) · [Пояснення файлів](FILES_REFERENCE.md)

## Крок 1. Підготувати комп’ютер

Потрібні Git, Python 3.10+ та Docker Desktop/Engine з Compose v2. На Windows використовуйте Linux containers. Рекомендовано виділити Docker щонайменше 8 ГБ RAM. Інтернет потрібний для образів, залежностей та RIPE. Запустіть Docker Desktop, дочекайтеся готовності engine, відкрийте PowerShell або термінал:

```bash
git --version
python --version
docker version
docker compose version
```

У docker version має відповідати Client і Server. Якщо python у Windows не знайдений, використайте `py -3 --version` і замінюйте далі python на py -3.

## Крок 2. Клонувати проєкт

```bash
git clone https://github.com/uneavk/ripe-atlas-monitoring.git
cd ripe-atlas-monitoring
```

У папці мають бути README.md, compose.yaml та каталоги collector, clickhouse, postgres, nifi, tools, docs. Усі подальші команди виконуються з кореня репозиторію.

## Крок 3. Обрати конфігурацію

Для стандартного першого запуску .env вручну не створюйте: bootstrap сам збереже випадкові паролі.

Для інших портів спочатку скопіюйте шаблон. PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Відкрийте .env у редакторі. Замініть усі три replace_with_... на різні випадкові паролі. Для POSTGRES_PASSWORD використовуйте випадкові латинські літери/цифри без URI-спецсимволів; пароль NiFi має бути не коротший за 12 символів. Bootstrap не запуститься із заглушками.

Для другої незалежної копії на тому самому ПК змініть COMPOSE_PROJECT_NAME та зайняті зовнішні порти. Внутрішні назви postgres, clickhouse, kafka у коді змінювати не потрібно. Після створення .env можна перевірити:

```bash
docker compose config --quiet
```

Файл .env приватний; не додавайте його в Git або повідомлення іншим людям.

## Крок 4. Запустити автоматичне налаштування

```bash
python tools/bootstrap.py
```

Скрипт створює .env і локальний каталог Telegram, перевіряє Compose, один раз збирає спільний образ collector/analytics/alerts, запускає стек, створює теми Kafka, очікує NiFi, налаштовує 11 процесорів, а потім створює словники, 20 в’ю ClickHouse та 5 reporting-в’ю PostgreSQL. Наприкінці друкує стан контейнерів і Ready.

Перший запуск може тривати кілька хвилин. Waiting for NiFi initialization — очікуване повідомлення запуску JVM. Traceback або завершення з помилкою означає, що налаштування ще не завершене; перейдіть до діагностики нижче.

## Крок 5. Перевірити контейнери

```bash
docker compose ps -a
docker compose logs --tail 30 collector
docker compose logs --tail 30 analytics
docker compose logs --tail 30 alerts
```

Kafka, PostgreSQL, ClickHouse та analytics повинні бути healthy; постійні сервіси — запущені. kafka-init має завершитися Exited (0). У collector очікуються backfill_started, backfill_completed, websocket_connected та Kafka-публікації. Без токена telegram_configured=False є нормальним.

Перше REST-дозавантаження послідовне за чотирма джерелами; черги NiFi можуть тимчасово зростати. Порожній IPv6 у перші секунди не є доказом аварії IPv6.

## Крок 6. Відкрити службові інтерфейси

| Інтерфейс | Стандартна адреса | Вхід |
|---|---|---|
| NiFi | https://localhost:8443/nifi | NIFI_USERNAME / NIFI_PASSWORD із .env |
| Kafka UI | http://localhost:8080 | Теми та consumer groups |
| Adminer | http://localhost:8081 | PostgreSQL, сервер postgres, облікові дані з .env |

NiFi використовує локальний сертифікат; браузер може показати попередження. Перевірте адресу власного локального сервера перед продовженням. У канві мають бути три гілки Read → Validate and transform → Store та маршрут відхилень. Порожня канва після Ready не є очікуваним результатом.

## Крок 7. Підключити ClickHouse у DBeaver

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

## Крок 8. Побудувати перший графік

```sql
SELECT period_start, target_name, ip_version, avg_rtt_ms, packet_loss_pct
FROM analytics.network_5minutes
ORDER BY period_start, target_name, ip_version;
```

У DBeaver/BI: X — period_start, Y — avg_rtt_ms або packet_loss_pct, серії — target_name та ip_version. Для завершених годин використовуйте network_hourly, для довгої історії — network_daily. Нова година має спочатку завершитися; перший день з’явиться після фіналізації о 04:00 за Києвом. Порожній період не заповнюйте нульовими втратами. Пояснення всіх графіків і формул: [FINAL_ANALYTICS.md](FINAL_ANALYTICS.md).

## Крок 9. Підключити PostgreSQL у DBeaver

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

## Крок 10. Налаштувати власного Telegram-бота

Отримайте токен власного бота через BotFather. Не публікуйте його.

```bash
python tools/configure_telegram.py
docker compose restart alerts
```

Введіть токен у прихованому запиті. Потім у Telegram надішліть цьому боту /start та дочекайтеся підтвердження. Кожен учасник підписується у своєму приватному чаті. /status перевіряє підписку, /stop вимикає її. Токен зберігається тільки в .secrets/telegram/config.json.

Конфігуратор сам не викликає getMe та не надсилає штучний інцидент. Відповідь /start перевіряє прийом команд і транспорт, а не весь шлях реальної аномалії. Не запускайте два alerts із тим самим токеном — вони конкуруватимуть за getUpdates.

## Крок 11. Запустити перевірки

```bash
docker compose run --rm --no-deps analytics python -m unittest discover -s tests -p "test_*.py"
python tools/verify_analytics_views.py
```

Тести мають завершитися OK. Перевірка в’ю виконує SELECT і звіряє наявні денні статистики. 0 поденних груп на нових томах є очікуваним і не означає перевірки історії, якої ще немає.

Для оновлення довідника після зміни схеми:

```bash
python tools/export_schema_reference.py
python tools/build_reference_docs.py
```

Експортуються метадані, не рядки вимірювань чи дані підписників.

## Крок 12. Щоденна робота й оновлення

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

## Крок 13. Підключити інший ПК

У тій самій мережі потрібні доступний IP Docker-хоста, опублікований порт та дозволений мережевий доступ. Налаштуйте BIND_ADDRESS, застосуйте Compose, у DBeaver іншого ПК вкажіть IP хоста замість localhost. Для зовнішнього доступу до NiFi задається також NIFI_PROXY_HOST; локальний localhost залишається дозволеним для конфігуратора.

Для іншої локальної мережі потрібний окремий мережевий маршрут. GitHub відкриває код, не базу. Інша людина може клонувати репозиторій і запустити власну незалежну копію; її історія буде окремою. Повні адреси й обмеження: [CONNECTIONS.md](CONNECTIONS.md).

## Діагностика

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
