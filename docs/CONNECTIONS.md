# Запуск і підключення

## Перший запуск

1. Запустіть Docker Desktop у режимі Linux containers.
2. Відкрийте папку скопійованого репозиторію.
3. Виконайте `python tools/bootstrap.py` (Windows: також можна `py -3 tools/bootstrap.py`).
4. Зачекайте завершення налаштування NiFi та повідомлення Ready.
5. Відкрийте локальний `.env`: там адреси портів, користувачі й випадково створені паролі.

Усі команди `docker compose` запускаються з кореня репозиторію. Якщо вже працює інша копія цього проєкту на тому самому комп’ютері, до запуску створіть `.env` за шаблоном, змініть `COMPOSE_PROJECT_NAME` і зайняті порти. Паролі замініть на різні випадкові значення. Для POSTGRES_PASSWORD використовуйте випадкові латинські літери й цифри: значення включається в URI підключення.

## ClickHouse у DBeaver

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

## PostgreSQL у DBeaver

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

## Адреси всередині Docker

| Клієнт | Адреса |
|---|---|
| Python / NiFi → Kafka | kafka:9092 |
| NiFi → HTTP-обробник | http://analytics:8082/ingest/ping_results |
| NiFi → довідник | http://analytics:8082/ingest/probe_directory |
| NiFi → статуси | http://analytics:8082/ingest/probe_events |
| Застосунок → ClickHouse | http://clickhouse:8123/ |
| Детектор → PostgreSQL | postgres:5432 |

`localhost` усередині контейнера означає саме цей контейнер, тому для зв’язку між сервісами використовуються їхні Docker-імена. Порт 8082 назовні не публікується.

## Інший комп’ютер у тій самій мережі

За замовчуванням порти доступні тільки на комп’ютері запуску. Щоб дозволити підключення з локальної мережі, змініть `BIND_ADDRESS` у `.env` на локальну адресу хоста або `0.0.0.0`, застосуйте `docker compose up -d` і налаштуйте дозволений доступ у брандмауері Windows. З іншого ПК у DBeaver вкажіть LAN-IP комп’ютера з Docker замість localhost та відповідний опублікований порт. Користувачі й паролі залишаються з `.env`.

Kafka додатково потребує `KAFKA_ADVERTISED_HOST`, що доступний зовнішньому клієнту, наприклад LAN-IP хоста. Для DBeaver доступ до Kafka не потрібний.

## Інша локальна мережа / Інтернет

Публічний GitHub містить код, а не запущені бази. `localhost` і Docker-імена недоступні з іншої мережі. Для доступу до єдиної запущеної БД потрібний окремо налаштований мережевий шлях до комп’ютера-хоста. Сам Docker такого зовнішнього маршруту не створює. Цей репозиторій не налаштовує роутер або зовнішній сервер. Інша людина може також клонувати репозиторій і запустити незалежну копію з власними даними.

## Зберігання та резервування

Дані знаходяться в іменованих Docker-томах: postgres_data, clickhouse_data, kafka_data, collector_state, analytics_state та томах NiFi. Реальні назви мають префікс COMPOSE_PROJECT_NAME. Ручний перенос папки репозиторію не переносить ці томи. Для перенесення накопиченої історії потрібні окремі резервні копії PostgreSQL і ClickHouse; вихідний репозиторій містить лише схеми.

Не додавайте `.env`, `.secrets`, дампи чи журнали з ідентифікаторами Telegram у Git. Каталоги резервних копій і стану вже виключені у `.gitignore`.

## Якщо щось не працює

- Docker API недоступний: перевірте, чи запущений Docker Desktop і Linux engine.
- Порт зайнятий: змініть його в `.env`, потім виконайте `docker compose up -d`.
- NiFi ще запускається: перегляньте `docker compose logs --tail 80 nifi`; скрипт початкового налаштування очікує його готовності.
- Немає даних: перевірте `analytics.data_freshness`, журнали collector та черги NiFi. Перший REST-backfill може заповнювати джерела послідовно.
- Погодинний графік порожній у новій системі: готові години публікуються після завершення години; для поточного стану використайте network_5minutes.
- Поденного рядка ще немає: попередня доба фіналізується після 04:00 за Києвом.
- Пароль змінили у `.env`, але БД відмовляє: змінні початкового користувача застосовуються при першій ініціалізації тому. Зміна `.env` сама по собі не змінює пароль у вже створеній БД.
- Telegram не відповідає: перевірте локальну конфігурацію, `/start`, журнали alerts та відсутність другої копії бота з тим самим токеном.
