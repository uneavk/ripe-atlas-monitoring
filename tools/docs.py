"""Generate references and portable exports from source catalogs."""
from pathlib import Path
import argparse,ast,csv,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'collector'))
sys.path.insert(0,str(ROOT/'bi'))
from app.kpi_catalog import KPI,DIMENSIONS
from dashboards import build

FILES={'.env.example': 'Шаблон адрес, портів і користувачів. Містить лише заглушки паролів. Bootstrap копіює його '
                 'в локальний .env і генерує випадкові паролі.',
 '.gitattributes': 'Задає LF для текстових файлів і правила для двійкових зображень, щоб Windows та Linux '
                   'однаково читали код.',
 '.github/workflows/download-configuration.yml': 'Ручний workflow приватного репозиторію: готує download '
                                                 'налаштованої GitHub Secrets копії чотирьох конфігураційних '
                                                 'файлів. Перевіряє склад і контрольні суми, не показує '
                                                 'паролі й не запускає бот.',
 '.github/workflows/tests.yml': 'GitHub Actions: модульні тести, повнота документації, файли коміту й '
                                'відтворюваність згенерованих артефактів.',
 '.gitignore': 'Виключає .env, секрети, локальні БД, журнали, кеші та томи з публікації Git.',
 'README.md': 'Короткий огляд, швидкий запуск, структура та посилання на шість повних інструкцій.',
 'artifacts/evidence_snapshot.json': 'Історичний знеособлений контрольний зріз від 09.11.2026, а не поточні '
                                     'дані нової інсталяції.',
 'artifacts/screenshots/live-rtt.jpg': 'Реальний скріншот RTT у Metabase від 09.11.2026 без облікових даних.',
 'artifacts/screenshots/map-ipv6.jpg': 'Реальна карта останніх результатів K-root IPv6 від 09.11.2026. '
                                       'Містить підпис OpenStreetMap.',
 'bi/dashboard_spec.json': 'Публічний переносимий експорт специфікації дашбордів без локальних ID, адресатів '
                           'і credentials. Не є vendor-export Metabase.',
 'bi/dashboards.py': 'Джерело 3 дашбордів і 26 SQL-карток: показники, підписи, фільтри та налаштування '
                     'візуалізацій без паролів.',
 'bi/test_dashboards.py': '4 тести SQL-контрактів, пропусків даних, фільтра, геометрії й відсутності доступу '
                          'до підписників.',
 'bi/validation.json': 'Збережені результати виконання 26 карток, додаткового IPv6-фільтра та перевірки '
                       'геометрії. Не поточний live-статус.',
 'clickhouse/init.sql': 'Єдина початкова схема ClickHouse. Послідовно створює сирі таблиці, накопичувачі, '
                        'довідник, сумісні в’ю й маркери вставок.',
 'collector/.dockerignore': 'Виключає кеші, локальний стан і секрети з контексту збірки образу Python.',
 'collector/Dockerfile': 'Будує спільний Python-образ для collector, analytics та alerts. Копіює код і '
                         'тести, встановлює залежності, запускає процеси від користувача collector.',
 'collector/app/__init__.py': 'Позначає каталог app як Python-пакет; самостійного сервісу не запускає.',
 'collector/app/alert_rules.py': 'Чисті правила детекції та форматування повідомлень. Не записує БД і не '
                                 'звертається до Telegram. Отримує готовий зріз і повертає Incident.',
 'collector/app/alerts.py': 'Цикл детектора: читає дані та baseline з ClickHouse, веде епізоди в PostgreSQL, '
                            'приймає команди Telegram і запускає доставку. Підтримує --once для одного '
                            'циклу.',
 'collector/app/analytics_views.py': 'Генерує 20 користувацьких в’ю analytics: довідники, live, 5 хвилин, '
                                     'години, дні, зрізи мережі/ASN/зонда та свіжість. Тут визначені чотири '
                                     'measurement ID і зрозумілі назви полів.',
 'collector/app/checkpoint.py': 'Зберігає позиції завершеного backfill за measurement ID у JSON-файлі '
                                'Docker-тому. Оновлює файл атомарною заміною; PostgreSQL не використовує.',
 'collector/app/config.py': 'Зчитує параметри середовища: країну, вимірювання, backfill, Kafka, checkpoint і '
                            'рівень журналювання. Містить адреси RIPE API та межі reconnect.',
 'collector/app/incident_state.py': 'Операційна схема, ключ епізоду та правила відновлення. Відсутність '
                                    'даних не вважається відновленням. Зберігає актуальний стан окремо від '
                                    'історії подій.',
 'collector/app/install_kpi.py': 'Створює або оновлює словники ClickHouse та чотири сумісні довгі KPI-в’ю '
                                 'monitoring. Прибирає колонки formula_uk та aggregation із таблиці '
                                 'словника.',
 'collector/app/kafka_io.py': 'Синхронний Kafka producer: acks=all, gzip, повтори та очікування '
                              'підтвердження. Ключ повідомлення — probe ID або event ID.',
 'collector/app/kpi_catalog.py': 'Семантичний каталог 25 кодів KPI та 14 полів: назви, одиниці, пояснення й '
                                 'правила розрахунку. Формули в коді/документації не є стовпцями готових '
                                 'в’ю.',
 'collector/app/logging_config.py': 'Налаштовує структуровані JSON-журнали: час, рівень, компонент, тип '
                                    'події та контекст обробки.',
 'collector/app/main.py': 'Точка входу збирача. Завантажує довідник, перевіряє джерела, виконує '
                          'REST-backfill, слухає WebSocket, фільтрує UA, публікує Kafka-повідомлення та '
                          'відхилення. Checkpoint змінюється після завершеного REST-діапазону.',
 'collector/app/models.py': 'Нормалізація ping і статусів, розрахунок loss, стабільні SHA-256 event_id, '
                            'перевірка ідентифікаторів, AF, пакетів і RTT. При rcvd=0 очищує RTT до NULL.',
 'collector/app/operational_views.py': 'Створює 5 в’ю reporting у PostgreSQL. Формує один рядок на епізод, '
                                       'підсумки інцидентів, помилок та доставки.',
 'collector/app/pipeline_errors.py': 'Окремий Kafka consumer ripe.dead_letter. Після запису діагностики в '
                                     'PostgreSQL підтверджує offset; унікальний ключ topic/partition/offset '
                                     'захищає від повторів.',
 'collector/app/retention_clickhouse.py': 'HTTP-шлюз запису в ClickHouse. Валідує та дедуплікує записи, '
                                          'об’єднує HTTP-запити в пакети, веде короткий журнал незавершеної '
                                          'операції, оновлює години, фіналізує дні й очищує старі дані.',
 'collector/app/ripe_client.py': 'Клієнт RIPE: пагінація зондів, перевірка measurement, REST-запити '
                                 '5-хвилинними частинами та підписки WebSocket. Некоректні JSON/envelope '
                                 'передає обробнику помилок.',
 'collector/app/telegram_sender.py': 'HTTP-транспорт Telegram: виклики Bot API, HTML-повідомлення, '
                                     'повернення message_id, розбір помилок і retry_after. При помилці не '
                                     'виводить URL із токеном.',
 'collector/app/telegram_subscriptions.py': 'Обробляє /start, /stop, /status, /help у приватних чатах. Веде '
                                            'offsets команд, черги відповідей і доставки кожному підписнику; '
                                            'обробляє блокування, 429 та закінчення строку повідомлень.',
 'collector/requirements.txt': 'Фіксує прямі залежності: kafka-python для Kafka, psycopg для PostgreSQL, '
                               'requests для REST/HTTP і websocket-client для потоку RIPE.',
 'collector/tests/test_alerts.py': 'Перевіряє пороги й підтвердження аномалій, групування за ASN/AF, '
                                   'знаменники вибірки та транспорт Telegram на підставних відповідях.',
 'collector/tests/test_audit_fixes.py': 'Регресійні сценарії: повна втрата без RTT, тривалий disconnect, '
                                        'відновлення лише за новими даними, свіжість та відокремлення '
                                        'епізодів.',
 'collector/tests/test_clickhouse_daily.py': 'Підставне сховище перевіряє добове згортання, порядок '
                                             'збереження й очищення та повтор після помилки запису дня.',
 'collector/tests/test_clickhouse_store.py': 'Підставне сховище перевіряє повтор після часткового запису, '
                                             'відсутність подвійного підрахунку, накопичення статистик і '
                                             'відхилення старих даних.',
 'collector/tests/test_models.py': 'Перевіряє нормалізацію, відсоток втрат, стабільність event ID і події '
                                   'статусів.',
 'collector/tests/test_retention.py': 'Перевіряє безпосередньо ClickHouse-обробник: межу 04:00, DST, часові '
                                      'ключі, NULL RTT і пакети.',
 'collector/tests/test_subscriptions.py': 'Перевіряє дозволені Telegram-команди та приватний характер '
                                          'підписки без реальних повідомлень.',
 'compose.bi.yaml': 'Необов’язкове підключення Metabase до мережі старого Docker-стека. Для нового '
                    'встановлення достатньо основного compose.yaml.',
 'compose.yaml': 'Повний Docker-стек. На порожніх томах монтує два init.sql, запускає спільний Python-образ '
                 'і Metabase.',
 'docs/ANALYTICS.md': 'Правила KPI й агрегації, приклади SQL, повний словник і пояснення кожної з 26 карток '
                      'Metabase.',
 'docs/ARCHITECTURE.md': 'Повний аналіз джерел, компонентів, контрактів, відновлення, retention, інцидентів '
                         'і меж системи.',
 'docs/CHECKS.md': 'Протоколи перевірок із датами, результатами й межами підтверджених висновків.',
 'docs/DATABASE.md': 'Згенеровані пояснення всіх 62 прикладних об’єктів БД та 599 стовпців із типами, '
                     'ключами і зв’язками.',
 'docs/FILES.md': 'Згенерований опис кожної відстежуваної папки й файла, основних функцій і локального '
                  'робочого стану.',
 'docs/KPI_DICTIONARY.csv': 'Машиночитаний словник: код, українська назва, одиниця та пояснення; без колонки '
                            'формул.',
 'docs/SETUP.md': 'Єдина інструкція встановлення, параметрів, DBeaver, Metabase, Telegram, онлайн-копії '
                  'налаштувань і супроводу.',
 'docs/schema_reference.json': 'Версійований знімок структури: 44 об’єкти ClickHouse та 18 PostgreSQL, '
                               'стовпці, SQL визначень і обмеження. Не містить вимірювань або даних '
                               'підписників.',
 'nifi/api_client.py': 'Локальний REST-клієнт NiFi. Знаходить контейнер і опублікований порт через Compose, '
                       'читає налаштовані облікові дані з Docker, чекає готовності й отримує тимчасовий JWT '
                       'без друку секретів.',
 'nifi/build_pipeline.py': 'Відтворює 11 процесорів і зв’язки. Налаштовує Kafka, Groovy-перевірки, HTTP '
                           'sinks та відхилення; при повторі тимчасово зупиняє власні процесори й відновлює '
                           'роботу.',
 'postgres/init.sql': 'Єдина початкова схема PostgreSQL: інциденти, cooldown, outbox, підписки, доставки, '
                      'епізоди й діагностика.',
 'tools/bootstrap.py': 'Основна команда першого запуску. Створює локальні паролі, перевіряє Compose, збирає '
                       'один спільний образ, запускає стек, налаштовує NiFi та обидва шари в’ю.',
 'tools/checks.py': 'Одна команда для 41 модульного тесту, аудиту документації та перевірки файлів Git. '
                    'Підтримує --unit, --docs і --publication.',
 'tools/configure_telegram.py': 'Приховано запитує токен і записує його тільки в '
                                '.secrets/telegram/config.json. Сам не надсилає повідомлень і не перевіряє '
                                'токен через мережу.',
 'tools/docs.py': 'Одна команда для генерації довідників, словника KPI й експорту Metabase. --schema '
                  'попередньо оновлює метадані працюючих БД.',
 'tools/setup_metabase.py': 'Ідемпотентно налаштовує Metabase через API, створює BI-reader та власні картки. '
                            'Паролі й локальні ID записує лише у .secrets.',
 'tools/verify_analytics_views.py': 'Виконує SELECT до 20 analytics-в’ю, перевіряє відсутність формульних '
                                    'колонок і звіряє поденні суми, DISTINCT та зважені середні зі сховищем. '
                                    'На хості делегує перевірку Docker.',
 'tools/verify_metabase.py': 'Виконує запити всіх BI-карток, IPv6-фільтр та перевірку відсутності '
                             'перекриття. Звіт містить статуси й кількість рядків без даних адресатів.'}

FOLDERS={'.github': 'Автоматизація GitHub.',
 '.github/workflows': 'CI та ручний download приватної конфігурації.',
 'artifacts': 'Історичні докази роботи.',
 'artifacts/screenshots': 'Збережені екрани Metabase.',
 'bi': 'Специфікація, експорт і тести дашбордів.',
 'clickhouse': 'Єдина початкова аналітична схема.',
 'collector': 'Спільний Python-образ.',
 'collector/app': 'Прикладні модулі трьох сервісів.',
 'collector/tests': 'Модульні та регресійні тести.',
 'docs': 'Шість інструкцій, CSV KPI й метадані схеми.',
 'nifi': 'API та конфігуратор потоку.',
 'postgres': 'Єдина початкова операційна схема.',
 'tools': 'Запуск, документація та перевірки.'}


# Reviewed hand-in materials, dated 2026-11-16.
FILES.update({'artifacts/handin/README.md': 'Сценарій командного захисту, схеми, запуск, пояснення матеріалів і 16 '
                               'реальних скріншотів.',
 'artifacts/handin/RIPE_Atlas_Defense.pptx': 'Редагована презентація з 15 слайдів і нотатками для рівного '
                                             'виступу трьох учасниць. Датовані докази, 16.11.2026.',
 'artifacts/handin/RIPE_Atlas_Report.pdf': 'Звіт на 18 сторінках: зв’язний опис системи, 2 схеми, 16 '
                                           'реальних скріншотів, KPI, помилки, аналітика та джерела.',
 'artifacts/handin/demo_clickhouse.sql': '13 запитів лише на читання для DBeaver: структура, протоколи, '
                                         'години/дні, KPI, маркери INSERT і штучні приклади в SELECT без '
                                         'запису даних.',
 'artifacts/handin/demo_postgres.sql': '5 запитів лише на читання: епізоди, підсумки інцидентів, діагностика '
                                       'та стани доставки без адресатів Telegram.',
 'artifacts/handin/screenshots/01-docker-live.jpg': 'Реальний оригінал скріншота від 16.11.2026. Docker '
                                                    'Desktop: служби проєкту та журнал успішних публікацій '
                                                    'collector у ripe.raw. Поточний запуск, 16.11.2026.',
 'artifacts/handin/screenshots/02-github-structure.jpg': 'Реальний оригінал скріншота від 16.11.2026. README '
                                                         'репозиторію: основні папки та команди перевірки.',
 'artifacts/handin/screenshots/03-kafka-topics.jpg': 'Реальний оригінал скріншота від 16.11.2026. Теми Kafka '
                                                     'UI. Порожня ripe.validated - успадкована тема, '
                                                     'поточний потік її не використовує. Фрагмент екрана.',
 'artifacts/handin/screenshots/04-kafka-consumers.jpg': 'Реальний оригінал скріншота від 16.11.2026. Окремі '
                                                        'consumer groups NiFi та діагностики. STABLE означає '
                                                        'стабільне членство в групі. N/A у lag не означає '
                                                        'нуль відставання. Фрагмент екрана.',
 'artifacts/handin/screenshots/05-dbeaver-clickhouse-views.jpg': 'Реальний оригінал скріншота від '
                                                                 '16.11.2026. DBeaver: 8 фізичних таблиць '
                                                                 'monitoring і результат запиту до каталогу '
                                                                 '44 об’єктів ClickHouse.',
 'artifacts/handin/screenshots/06-dbeaver-ip-versions.jpg': 'Реальний оригінал скріншота від 16.11.2026. '
                                                            'data_freshness у DBeaver: чотири джерела, '
                                                            'IP-версія, давність даних і фактично '
                                                            'спостережувані зонди.',
 'artifacts/handin/screenshots/07-dbeaver-retention.jpg': 'Реальний оригінал скріншота від 16.11.2026. '
                                                          'Маркери вставок, last_maintenance і перевірка '
                                                          'raw_rows_older_than_5h=0. Час маркерів '
                                                          'зберігається в UTC.',
 'artifacts/handin/screenshots/08-dbeaver-kpi.jpg': 'Реальний оригінал скріншота від 16.11.2026. '
                                                    'network_hourly_kpi: назва, одиниця та значення KPI '
                                                    'останньої завершеної години для K-root IPv4.',
 'artifacts/handin/screenshots/09-metabase-rtt.jpg': 'Реальний оригінал скріншота від 16.11.2026. Дашборд '
                                                     'поточного стану, картка RTT: окрема лінія для кожної '
                                                     'цілі й IP-версії. Дані згруповані по 5 хвилин.',
 'artifacts/handin/screenshots/10-metabase-daily.jpg': 'Реальний оригінал скріншота від 16.11.2026. Поденні '
                                                       'середні: історія зберігає також давніші вересневі '
                                                       'дані.',
 'artifacts/handin/screenshots/11-metabase-ipv6-map.jpg': 'Реальний оригінал скріншота від 16.11.2026. Карта '
                                                          'K-root IPv6, measurement=2001, 47 рядків на '
                                                          'момент знімка. Підкладка © OpenStreetMap '
                                                          'contributors, Leaflet.',
 'artifacts/handin/screenshots/12-metabase-hourly.jpg': 'Реальний оригінал скріншота від 16.11.2026. '
                                                        'Завершені години: видимі розриви даних.',
 'artifacts/handin/screenshots/13-metabase-incidents.jpg': 'Реальний оригінал скріншота від 16.11.2026. '
                                                           'Журнал Metabase розрізняє відкриті та відновлені '
                                                           'епізоди. Знімок показує реальні спостереження, '
                                                           '16.11.2026.',
 'artifacts/handin/screenshots/14-dbeaver-postgresql.jpg': 'Реальний оригінал скріншота від 16.11.2026. '
                                                           'DBeaver/PostgreSQL: реальні епізоди з '
                                                           'протоколом, часом Києва, станом і статусом '
                                                           'сповіщення.',
 'artifacts/handin/verification.json': 'Знеособлений контрольний зріз від 16.11.2026: БД, 18 перевірених '
                                       'запитів, Docker і фактичні процесори/зв’язки NiFi. Не містить '
                                       'секретів чи сирих подій.',
 'artifacts/handin/architecture.svg': 'Векторна схема архітектури за README: RIPE → collector → Kafka → NiFi '
                                      '→ ClickHouse, операційний стан, BI та Telegram.',
 'artifacts/handin/nifi-flow.svg': 'Векторна схема трьох основних гілок NiFi та спільного маршруту '
                                   'діагностики відхилених подій.',
 'artifacts/handin/screenshots/15-nifi-summary.jpg': 'Реальний оригінал скріншота від 16.11.2026. NiFi '
                                                     'Summary, 16.11.2026: усі 11 процесорів Running. '
                                                     'Лічильники In/Out та Read/Write показують роботу за '
                                                     'останні 5 хвилин.',
 'artifacts/handin/screenshots/16-nifi-canvas.jpg': 'Реальний оригінал скріншота від 16.11.2026. Повне '
                                                    'полотно NiFi: три основні рядки та нижня гілка Describe '
                                                    'rejected events → RIPE invalid events. Це реальний '
                                                    'екран; читабельні назви наведено на схемі попередньої '
                                                    'сторінки.'})
FOLDERS.update({'artifacts/handin': 'Готові матеріали для захисту, сценарій, демонстраційні SQL та контрольний зріз.', 'artifacts/handin/screenshots': '16 оригіналів реальних екранів Docker, GitHub, Kafka, NiFi, DBeaver та Metabase від 16.11.2026.'})

FILES.update({'artifacts/handin/RIPE_Atlas_Team_Defense.docx': 'Готовий сценарій виступу Яни, Вікторії та Валерії за 15 слайдами, жива демонстрація і 50 відповідей на можливі запитання.'})

FIELDS={'active': 'Чи ввімкнена підписка адресата.',
 'address_family': 'Числова версія IP у довіднику вимірювань: 4 або 6.',
 'af': '4 — IPv4, 6 — IPv6; 0 у службових агрегатах подій підключення.',
 'asn': 'Номер автономної системи для конкретного IP-протоколу; 0 — невідомий або службовий.',
 'asn_v4': 'ASN IPv4 з довідника RIPE.',
 'asn_v6': 'ASN IPv6 з довідника RIPE.',
 'atlas_status': 'Статус зонда за останнім завантаженням довідника RIPE.',
 'attempts': 'Кількість зроблених спроб доставки.',
 'avg_rtt_ms': 'Середня RTT валідних серій, у мс; NULL без відповідей.',
 'chat_id': 'Ідентифікатор Telegram-чату; операційні дані, не для публікації.',
 'connection_event': 'Подія підключення/відключення зонда.',
 'connects': 'Кількість подій connect/connected.',
 'country': 'Код країни з довідника RIPE, у цьому потоці UA.',
 'country_code': 'Зрозуміла назва коду країни.',
 'created_at': 'Час створення операційного запису.',
 'data_age_seconds': 'Давність останнього вимірювання у секундах; NULL, якщо даних немає.',
 'data_status': 'Немає даних / Дані застаріли / Дані надходять; поріг старіння — 900 с.',
 'day': 'Дата календарного дня Europe/Kyiv.',
 'delivery_count': 'Кількість доставок адресатам; один outbox може дати багато доставок.',
 'delivery_status': 'Стан доставки окремому адресату.',
 'description_uk': 'Пояснення семантики KPI українською.',
 'destination_address': 'IP-адреса цілі вимірювання.',
 'details': 'JSONB-контекст інциденту: зонд, ASN, measurement, AF, значення, baseline, склад вибірки тощо.',
 'disconnects': 'Кількість подій disconnect/disconnected/down.',
 'dst_addr': 'IP-адреса цілі в сирому записі.',
 'dst_name': 'Назва цілі в сирому записі.',
 'duration_seconds': 'Час від початку до відновлення або до поточного моменту; оцінка за спостереженнями.',
 'episode_id': 'Ідентифікатор конкретного історичного епізоду; пов’язує початок та ескалацію.',
 'episode_key': 'Ключ поточного стану: тип + scope + measurement + AF.',
 'event': 'Тип події підключення.',
 'event_at': 'Час події підключення для відображення за Києвом.',
 'event_id': 'Стабільний ідентифікатор події для повторного читання й дедуплікації.',
 'event_time': 'Час джерельної події; у ClickHouse зберігається в UTC.',
 'event_timestamp': 'Unix timestamp останньої відомої події стану зонда.',
 'field_code': 'Внутрішній код поля.',
 'field_name_uk': 'Пояснювальна назва поля українською.',
 'full_loss_samples': 'Кількість серій із received=0.',
 'high_loss_measurements': 'Кількість серій із втратою понад 50%.',
 'hour_start': 'Початок години UTC; зберігає різні години під час переходу літнього часу.',
 'id': 'Технічний первинний ключ; у poll_state завжди 1, в outbox — послідовний номер.',
 'incident_count': 'Кількість унікальних епізодів за часом їхнього початку.',
 'incident_id': 'Ідентифікатор окремої події детектора.',
 'incident_status': 'Триває або Відновлено за відомим станом епізоду.',
 'incident_type': 'Тип: HIGH_RTT, PACKET_LOSS, PROBE_DOWN, ASN_OUTAGE, REGION_OUTAGE або PIPELINE_STALE.',
 'ingested_at': 'Час фізичного надходження до ClickHouse; версія сирого запису.',
 'interval_seconds': 'Номінальний інтервал RIPE-вимірювання, тут 240 с.',
 'ip_version': 'Підпис IPv4/IPv6; для неадресних подій у PostgreSQL — Не застосовується.',
 'ipv4_provider_asn': 'ASN IPv4 у читабельному довіднику.',
 'ipv6_provider_asn': 'ASN IPv6 у читабельному довіднику.',
 'kafka_offset': 'Позиція повідомлення в конкретній Kafka-партиції.',
 'key': 'Ключ службового маркера: last_maintenance, day:дата або вставка.',
 'kind': 'Внутрішній тип інциденту.',
 'kpi_code': 'Стабільний код KPI.',
 'kpi_name': 'Українська назва KPI в analytics.',
 'kpi_name_uk': 'Українська назва KPI в сумісному monitoring.',
 'kpi_value': 'Числове значення одного KPI.',
 'last_error': 'Збережений безпечний код останньої помилки доставки.',
 'last_queued_at': 'Час останньої постановки повідомлення у чергу для cooldown.',
 'last_seen_at': 'Час останнього підтвердження проблеми джерельними даними; не кожного запуску циклу.',
 'latest_measurement_at': 'Час останнього вимірювання джерела за Києвом; NULL без даних.',
 'latitude': 'Широта зонда.',
 'local_hour': 'Початок години для відображення Europe/Kyiv.',
 'local_time': 'Локальний час вимірювання у сумісному view.',
 'longitude': 'Довгота зонда.',
 'loss_pct': 'Втрати пакетів у конкретній сирій серії, %.',
 'loss_samples': 'Кількість серій зі втратою понад 50%.',
 'max_rtt_ms': 'Найбільша валідна RTT періоду, мс.',
 'measured_at': 'Час вимірювання у часовій зоні Europe/Kyiv.',
 'measurement_count': 'Кількість унікальних серій ping, а не пакетів.',
 'measurement_id': 'ID RIPE-вимірювання, що визначає ціль і AF.',
 'measurement_success_pct': 'Частка серій хоча б з однією відповіддю, %.',
 'measurements_last_5h': 'Кількість серій у сирій таблиці за останні 5 годин.',
 'message': 'Текст повідомлення або відповіді Telegram.',
 'min_rtt_ms': 'Найменша валідна RTT періоду, мс.',
 'msm_id': 'Внутрішня назва ID RIPE-вимірювання.',
 'next_attempt_at': 'Найраніший час наступної спроби доставки.',
 'next_update_id': 'Наступний getUpdates offset; захищає від повторної обробки команд.',
 'no_reply_measurements': 'Кількість серій без жодної відповіді.',
 'normal_rtt_count': 'Кількість серій із RTT>0 та втратою ≤50% для baseline.',
 'normal_rtt_sum': 'Сума RTT серій, придатних для baseline.',
 'notification_status': 'Стан сповіщення про подію; відрізняється від стану самого інциденту.',
 'observed_probes': 'Кількість DISTINCT зондів у сумісному агрегаті.',
 'opened_at': 'Час початку епізоду за доступними спостереженнями.',
 'opening_id': 'Подія monitoring_incidents, що відкрила епізод.',
 'outbox_id': 'Посилання доставки на спільне повідомлення outbox.',
 'packet_loss_pct': 'Зважені втрати пакетів періоду: зі співвідношення сум.',
 'packets_lost': 'Кількість надісланих пакетів без відповіді.',
 'packets_received': 'Кількість отриманих відповідей.',
 'packets_sent': 'Кількість надісланих пакетів.',
 'partition_id': 'Номер Kafka-партиції.',
 'pause_until': 'Глобальна пауза Telegram після 429.',
 'period_end': 'Права межа періоду в сумісному KPI-view.',
 'period_label': 'Текстовий підпис години/дня; не замінює часовий ключ.',
 'period_name_uk': 'Тип періоду українською.',
 'period_start': 'Початок періоду; analytics використовує DateTime Europe/Kyiv.',
 'prb_id': 'ID зонда в сирому контракті RIPE.',
 'probe_id': 'ID зонда у довідниках, агрегатах та звітах.',
 'probes_observed': 'Кількість різних зондів з вимірюваннями в цьому періоді.',
 'probes_observed_last_5h': 'Кількість різних зондів із результатами джерела за останні 5 годин.',
 'provider_asn': 'ASN відповідного протоколу в готовому звіті.',
 'provider_name': 'Позначення ASномер або Невідомий ASN; не комерційна назва оператора.',
 'rcvd': 'Кількість відповідей у сирій серії.',
 'reason': 'Причина відхилення запису.',
 'received': 'Сума отриманих відповідей у накопичувачі.',
 'received_at': 'Час отримання/запису діагностики, не обов’язково час початкової помилки.',
 'rejected_events': 'Кількість повідомлень DLQ; не кількість мережевих аварій.',
 'resolved_at': 'Час підтвердженого відновлення; NULL для відкритого епізоду.',
 'rtt_avg': 'Середня RTT однієї серії, мс.',
 'rtt_count': 'Кількість серій із не-NULL RTT; знаменник середнього.',
 'rtt_max': 'Максимум RTT.',
 'rtt_min': 'Мінімум RTT.',
 'rtt_ms': 'Середня RTT сирої серії у сумісному view.',
 'rtt_sum': 'Сума середніх RTT серій; чисельник середнього періоду.',
 'samples': 'Кількість серій ping; для службового status-рядка — 0.',
 'scope': 'Область інциденту: probe:ID, asn:ID, region:UA або measurement:ID.',
 'sent': 'Кількість пакетів у серії або сума у накопичувачі.',
 'sent_at': 'Час успішної доставки або завершення обробки outbox; дивіться також конкретний статус.',
 'severity': 'warning, critical або info.',
 'source_address': 'Адреса, яку RIPE повідомив як джерело вимірювання.',
 'source_mode': 'stream — живий потік, backfill — REST-дозавантаження.',
 'src_addr': 'Внутрішня назва адреси джерела.',
 'stage': 'Етап, на якому повідомлення відхилено: collector, websocket, RIPE або NiFi.',
 'started_at': 'Початок епізоду у reporting.',
 'status': 'Статус зонда або черги доставки залежно від таблиці.',
 'status_uk': 'Читабельний стан епізоду.',
 'subscribed_at': 'Час підписки адресата.',
 'successful_measurements_pct': 'Частка серій із хоча б однією відповіддю, %.',
 'target': 'Назва цілі у сумісному live-view.',
 'target_hostname': 'DNS-ім’я цілі вимірювання.',
 'target_name': 'Читабельна назва K-root/F-root або резервний підпис measurement.',
 'telegram_message_id': 'ID реально відправленого повідомлення Telegram.',
 'topic': 'Назва теми Kafka.',
 'unit': 'Одиниця KPI у analytics.',
 'unit_uk': 'Одиниця KPI у monitoring.',
 'update_id': 'ID Telegram update, який породив відповідь.',
 'updated_at': 'Час зміни підписки.',
 'value': 'Число KPI у довгому view або текст службового маркера в retention_runs.',
 'version': 'Версія знімка для вибору останнього запису ReplacingMergeTree.'}

OBJECTS={'analytics.data_freshness': 'Один рядок на кожне з 4 налаштованих джерел, навіть без даних. Давність '
                             'рахується за event_time і охоплює як stream, так і backfill; це не окремий '
                             'контроль WebSocket.',
 'analytics.kpi_directory': '12 публічних числових KPI: код, назва й одиниця. Частина колонок відсутня у '
                            'п’ятихвилинних views; точний склад наведено нижче.',
 'analytics.measurement_directory': 'Чотири визначення ціль+протокол. Один рядок на measurement_id; показує '
                                    'hostname, IP-версію та інтервал 240 с.',
 'analytics.measurements_live': 'Одна дедуплікована серія ping за останні 5 годин; явні measurement_id, '
                                'target_name, ip_version, ASN і координати.',
 'analytics.probe_directory': 'Читабельний поточний довідник; один рядок на probe_id з окремими ASN '
                              'IPv4/IPv6.',
 'analytics.probe_events_live': 'Події Atlas за останні 5 годин у читабельних полях; AF навмисно відсутній.',
 'monitoring.daily_metrics': 'Довгостроковий підсумок: день Europe/Kyiv × зонд × measurement × AF × ASN. '
                             'Фіналізується після 04:00; дні не видаляються. Суми, лічильники, мінімум і '
                             'максимум зберігаються окремо.',
 'monitoring.daily_probe_activity': 'Поденні connects/disconnects із рядків AF=0. Рахує події, не тривалість '
                                    'простою.',
 'monitoring.field_dictionary': '14 визначень внутрішніх назв полів. Службовий словник, а не копія '
                                'вимірювань.',
 'monitoring.hourly_metrics': 'Накопичувач: година UTC × зонд × measurement × AF × ASN. Містить достатні '
                              'статистики, включно з незавершеною годиною. Зберігається 48 годин, але старий '
                              'рядок не видаляється до підтвердження потрібного дня. AF=0/msm_id=0 — '
                              'status-події.',
 'monitoring.kpi_dictionary': '25 семантичних визначень KPI: код, назва, одиниця, пояснення. Це не часові '
                              'значення показників. Читається FINAL; формульних стовпців немає.',
 'monitoring.live_network_measurements': 'Сумісний live-view із приєднаним довідником зондів; використовує '
                                         'короткі внутрішні назви. Новим графікам рекомендований '
                                         'analytics.measurements_live.',
 'monitoring.ping_ingest_trigger': 'Materialized view на INSERT у ping_results. Пише маркер ingest_request у '
                                   'retention_runs. Не рахує самостійно всі KPI й не запускається від '
                                   'годинника.',
 'monitoring.ping_results': 'Одна сирa серія ping конкретного зонда й вимірювання. Зберігається 5 годин; '
                            'записує тільки контрольований HTTP-обробник. Ключ сортування включає event_id, '
                            'а ingested_at визначає версію.',
 'monitoring.probe_directory': 'Поточні метадані зонда. Один логічний рядок на probe_id, версії заміщуються; '
                               'містить окремі ASN IPv4/IPv6 й координати. Статус оновлюється завантаженням '
                               'довідника, не кожним ping.',
 'monitoring.probe_events': 'Одна подія підключення/відключення зонда. Зберігається 5 годин. Не має '
                            'measurement/AF: це стан зв’язку з Atlas, а не ping до певної цілі.',
 'monitoring.raw_ping_last_5h': 'Сумісний фільтр сирих ping за останні 5 годин, FINAL.',
 'monitoring.raw_probe_events_last_5h': 'Сумісний фільтр сирих status-подій за останні 5 годин, FINAL.',
 'monitoring.retention_runs': 'Поточні службові маркери: останнє очищення, ревізія збереженого дня, вставки. '
                              'Один логічний рядок на key; це не повний журнал усіх запусків.',
 'monitoring.status_ingest_trigger': 'Materialized view на INSERT у probe_events. Пише status_ingest_request '
                                     'у retention_runs; повну обробку виконує Python-шлюз.',
 'public.incident_episode_metrics': 'Внутрішній view останніх станів епізодів із тривалістю. Не повний архів '
                                    'повторних епізодів того самого ключа.',
 'public.incident_episodes': 'Останній стан за episode_key. При новому епізоді того самого типу ключ '
                             'перевикористовується; повна історія береться з monitoring_incidents, не лише з '
                             'цієї таблиці.',
 'public.incident_history_metrics': 'Внутрішній view історичних епізодів, згрупованих за episode_id, із '
                                    'початком, відновленням і тривалістю за спостереженнями.',
 'public.monitoring_incidents': 'Історія подій детектора: відкриття епізоду, ескалація та RECOVERED. Один '
                                'рядок не дорівнює одному поганому ping або одній доставці. episode_id '
                                'пов’язує події одного збою.',
 'public.notification_cooldowns': 'Один запис на ключ повідомлення епізоду з критичністю. Обмежує повторну '
                                  'постановку в outbox; сама активність інциденту визначається '
                                  'incident_episodes.',
 'public.probe_connectivity_state': 'Остання відома подія стану зонда. Оновлюється лише новішим timestamp; '
                                    'не має 5-годинного очищення сирих status-подій.',
 'public.processing_error_summary': 'Внутрішнє погодинне групування діагностики за стадією й причиною.',
 'public.processing_errors': 'Один оброблений запис Kafka DLQ за topic+partition+offset. Зберігає причину та '
                             'стадію, а не повний сирий payload. received_at — час запису діагностики, '
                             'історичне перечитування може зміщувати графік.',
 'public.telegram_command_replies': 'Одна відповідь на Telegram update, з незалежним станом і повторними '
                                    'спробами.',
 'public.telegram_deliveries': 'Одна доставка конкретному чату. Первинний ключ outbox_id+chat_id; стани '
                               'sent/pending/failed/expired/cancelled відображають реальну спробу адресату.',
 'public.telegram_outbox': 'Спільний текст одного сповіщення. Посилається на incident_id; доставки адресатам '
                           'знаходяться в telegram_deliveries.',
 'public.telegram_poll_state': 'Один singleton-рядок id=1: getUpdates offset та глобальна пауза після 429.',
 'public.telegram_subscribers': 'Один приватний Telegram-чат на chat_id. active визначає отримання майбутніх '
                                'сповіщень; містить особисті операційні ідентифікатори.',
 'reporting.incidents': 'Один рядок на епізод: перший час початку, останній запис критичності, контекст і '
                        'підтверджене відновлення. RECOVERED не рахується новою аварією.',
 'reporting.incidents_daily': 'Нові епізоди за київською датою початку, типом, measurement і протоколом. '
                              'Тривалий збій через північ не додається щодня як новий.',
 'reporting.incidents_hourly': 'Нові епізоди за годиною початку, типом, останньою критичністю, measurement і '
                               'протоколом. Не кількість активних збоїв у кожній годині.',
 'reporting.processing_errors_hourly': 'Кількість відхилених Kafka-повідомлень за часом запису діагностики, '
                                       'стадією та причиною.',
 'reporting.telegram_deliveries_daily': 'Кількість доставок за датою створення outbox і поточним статусом. '
                                        'Один інцидент × три адресати дає три доставки, а не три мережеві '
                                        'аварії.'}


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

def database_reference():
    data=json.loads((ROOT/'docs/schema_reference.json').read_text(encoding='utf-8'))
    fields={c['name'] for db in data.values() for c in db['columns']}
    if fields-set(FIELDS):raise ValueError('Missing field descriptions: '+str(sorted(fields-set(FIELDS))))
    text='# Повний довідник БД, таблиць і в’ю\n\n[Карта документації](../README.md) · [Кінцева аналітика](ANALYTICS.md)\n\n'
    text+='## Відповідальність сховищ\n\nClickHouse: 8 фізичних таблиць, 2 materialized view та 34 звичайних view (14 сумісних у monitoring і 20 користувацьких у analytics). PostgreSQL: 10 фізичних таблиць, 3 внутрішні view у public та 5 користувацьких у reporting. Разом описано 62 об’єкти. PostgreSQL не приймає мережеві вимірювання перед ClickHouse. View — запит до існуючих даних, а не нова незалежна копія.\n\nОкрема службова БД Metabase містить внутрішні таблиці продукту й його облікові записи. До 62 прикладних об’єктів і 599 описаних стовпців вони не включені; їхній формат визначає версія Metabase.\n\n'
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
    text+='\n## Межі зберігання\n\n5 годин застосовуються до сирих таблиць ClickHouse; 48 годин — до накопичувачів годин із захистом незбереженого дня; daily_metrics не очищується. Ці строки не означають автоматичного очищення PostgreSQL, Kafka, довідників або резервних копій. Публікаційний код не містить політики автоматичного видалення операційної історії PostgreSQL.\n\nПовні SQL-визначення й типи зафіксовані у [schema_reference.json](schema_reference.json). Це метадані, без прикладних рядків або секретів. Для оновлення після міграції: `python tools/docs.py --schema`, потім `python tools/docs.py`.\n'
    (ROOT/'docs/DATABASE.md').write_text(text,encoding='utf-8',newline='\n')

def run(service,code):
    result=subprocess.run(['docker','compose','run','--rm','--no-deps',service,'python','-c',code],cwd=ROOT,text=True,encoding='utf-8',capture_output=True,check=True)
    return json.loads(result.stdout)

def export_schema():
    ch=run('analytics',"""import json
from app.retention_clickhouse import ch
print(json.dumps({'objects':ch("SELECT database,name,engine,sorting_key,partition_key,create_table_query FROM system.tables WHERE database IN ('monitoring','analytics') ORDER BY database,name FORMAT JSONEachRow"),'columns':ch("SELECT database,table,name,type,default_kind,default_expression FROM system.columns WHERE database IN ('monitoring','analytics') ORDER BY database,table,position FORMAT JSONEachRow")}))""")
    pg=run('alerts',"""import json,os,psycopg
from psycopg.rows import dict_row
with psycopg.connect(os.environ['POSTGRES_DSN'],row_factory=dict_row) as conn:
 objects=conn.execute("SELECT table_schema AS schema,table_name AS name,table_type AS kind FROM information_schema.tables WHERE table_schema IN ('public','reporting') ORDER BY 1,2").fetchall()
 columns=conn.execute("SELECT table_schema AS schema,table_name AS table,column_name AS name,data_type AS type,is_nullable,column_default FROM information_schema.columns WHERE table_schema IN ('public','reporting') ORDER BY table_schema,table_name,ordinal_position").fetchall()
 constraints=conn.execute("SELECT n.nspname AS schema,c.relname AS table,con.conname AS name,pg_get_constraintdef(con.oid) AS definition FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('public','reporting') ORDER BY 1,2,3").fetchall()
 views=conn.execute("SELECT schemaname AS schema,viewname AS name,definition FROM pg_views WHERE schemaname IN ('public','reporting') ORDER BY 1,2").fetchall()
 print(json.dumps(dict(objects=objects,columns=columns,constraints=constraints,views=views)))""")
    destination=ROOT/'docs/schema_reference.json'
    destination.write_text(json.dumps({'clickhouse':ch,'postgresql':pg},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Exported metadata:',len(ch['objects']),'ClickHouse objects;',len(pg['objects']),'PostgreSQL objects')

def files_reference():
    paths=set(filter(None,subprocess.check_output(['git','ls-files','-z'],cwd=ROOT,text=True).split('\0')))
    if paths!=set(FILES):
        raise ValueError('File descriptions differ from Git: '+str(sorted(paths.symmetric_difference(FILES))))
    folders={p.as_posix() for name in paths for p in Path(name).parents if p!=Path('.')}
    if folders-set(FOLDERS):raise ValueError('Missing folder descriptions: '+str(sorted(folders-set(FOLDERS))))
    text='# Файли та структура проєкту\n\n[Головна](../README.md) · [Архітектура](ARCHITECTURE.md) · [Запуск](SETUP.md)\n\n'
    text+=f'Описано всі {len(paths)} файлів і {len(folders)} папок, які відстежує Git.\n\n'
    text+='Один Python-образ запускає три різні сервіси: collector, analytics та alerts. Початкові схеми містяться у clickhouse/init.sql та postgres/init.sql. Аналітичні в’ю створюють Python-модулі під час bootstrap. Специфікація Metabase має власний JSON-експорт.\n\n'
    text+='## Папки\n\n| Папка | Призначення |\n|---|---|\n'
    for folder in sorted(folders):text+=f'| `{folder}/` | {FOLDERS[folder]} |\n'
    for folder in ['Корінь',*sorted(folders)]:
        selected=[name for name in sorted(paths) if Path(name).parent.as_posix()==('.' if folder=='Корінь' else folder)]
        if not selected:continue
        text+='\n## '+folder+'\n\n'
        for name in selected:
            text+=f'### [{name}](../{name})\n\n{FILES[name]}\n\n'
            if name.endswith('.py'):
                tree=ast.parse((ROOT/name).read_text(encoding='utf-8-sig'))
                interfaces=[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
                if interfaces:text+='Основні інтерфейси: '+', '.join('`'+n+'`' for n in interfaces)+'.\n\n'
    text+='## Робочі файли поза комітами\n\n| Об’єкт | Призначення |\n|---|---|\n'
    for name,purpose in [
        ('.env','Паролі й порти поточної копії; погоджений знімок є в GitHub Secrets.'),
        ('.secrets/metabase/admin.json','Вхід адміністратора Metabase та пароль BI-reader.'),
        ('.secrets/metabase/manifest.json','ID та URL локальних дашбордів.'),
        ('.secrets/metabase/deployment.env','Окреме підключення BI до старого стека.'),
        ('.secrets/configuration-backup-receipt.json','Протокол звіряння онлайн-копії без значень паролів.'),
        ('.secrets/telegram/config.json','Токен власного бота, не включений до погодженого онлайн-знімка.'),
        ('Docker-томи','Бази, черги, checkpoints і журнал незавершеного запису.'),
        ('Кеші, журнали, backups','Робочий стан та діагностика, виключені .gitignore.'),
    ]:text+=f'| `{name}` | {purpose} |\n'
    (ROOT/'docs/FILES.md').write_text(text,encoding='utf-8',newline='\n')


def export_assets():
    (ROOT/'bi/dashboard_spec.json').write_text(json.dumps(build(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (ROOT/'docs/KPI_DICTIONARY.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream,delimiter=';',lineterminator='\n')
        writer.writerow(['Код KPI','Назва українською','Одиниця','Пояснення'])
        writer.writerows([[row[i] for i in (0,1,2,5)] for row in KPI])


def kpi_section():
    text='<a id="kpi-catalog"></a>\n\n## Повний словник внутрішніх KPI\n\n'
    text+='Внутрішні коди зберігаються в monitoring.kpi_dictionary. Публічні назви колонок analytics пояснені вище. Формули є в документації, а готові в’ю містять числові значення.\n\n'
    text+='| Код | Назва | Одиниця | Агрегація | Формула | Пояснення |\n|---|---|---|---|---|---|\n'
    for row in KPI:text+='| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |\n'
    text+='\n## Назви внутрішніх вимірів\n\n| Поле | Назва |\n|---|---|\n'
    for code,label in DIMENSIONS:text+=f'| {code} | {label} |\n'
    return text


def dashboard_section():
    dashboards=build()
    text='<a id="dashboard-cards"></a>\n\n## Кожна картка Metabase\n\n'
    text+='Специфікація: [bi/dashboards.py](../bi/dashboards.py). Переносимий експорт: [bi/dashboard_spec.json](../bi/dashboard_spec.json). Локальні ID залежать від інсталяції.\n\n'
    text+='Фільтр measurement: 1001 K-root IPv4, 2001 K-root IPv6, 1004 F-root IPv4, 2004 F-root IPv6. Він впливає тільки на картки з параметром. Порівняльні графіки залишають чотири серії.\n\n'
    types={'table':'Таблиця','scalar':'Одне число','line':'Лінійний графік','bar':'Стовпчиковий графік','map':'Карта'}
    for dashboard in dashboards:
        text+='### '+dashboard['name']+'\n\n'+dashboard['description']+'\n\n'
        for card in dashboard['cards']:
            sources=sorted(set(re.findall(r'\b(?:analytics|reporting|public)\.[A-Za-z_][A-Za-z0-9_]*',card['sql'])))
            text+='#### `'+card['key']+'` - '+card['name']+'\n\n'
            text+='| Властивість | Значення |\n|---|---|\n'
            text+='| Сховище | '+('PostgreSQL' if card['source']=='pg' else 'ClickHouse')+' |\n'
            text+='| Джерела | '+', '.join('`'+s+'`' for s in sources)+' |\n'
            text+='| Відображення | '+types.get(card['display'],card['display'])+' |\n'
            text+='| Фільтр measurement | '+('Так' if card['measurement'] else 'Ні')+' |\n\n'
            text+=card['description']+'\n\n'
    text+='Поточне вікно - до 5 годин, завершені години - 48 годин. Поденні графіки обмежують запит останнім роком, а денні підсумки в БД зберігаються безстроково. Нове встановлення починає без попередніх вимірювань. Скріншоти artifacts датовані 09.11.2026.\n'
    return text


def analytics_reference():
    path=ROOT/'docs/ANALYTICS.md'
    text=path.read_text(encoding='utf-8')
    for marker,content in [('KPI',kpi_section()),('DASHBOARDS',dashboard_section())]:
        start='<!-- GENERATED_'+marker+'_BEGIN -->'
        end='<!-- GENERATED_'+marker+'_END -->'
        if text.count(start)!=1 or text.count(end)!=1:raise ValueError('Missing generated section: '+marker)
        prefix,tail=text.split(start,1)
        _,suffix=tail.split(end,1)
        text=prefix+start+'\n\n'+content.strip()+'\n\n'+end+suffix
    path.write_text(text,encoding='utf-8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description='Build documentation and portable configuration exports')
    parser.add_argument('--schema',action='store_true',help='Read updated database metadata from the running stack first')
    args=parser.parse_args()
    if args.schema:export_schema()
    export_assets()
    files_reference()
    database_reference()
    analytics_reference()
    print('Built file/database references, KPI catalog and dashboard export')


if __name__=='__main__':main()
