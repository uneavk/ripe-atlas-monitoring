# Порядок супроводу проєкту

Основний каталог репозиторію містить вихідний код і конфігурації. Docker-томи містять БД і черги. Папка з кодом не є резервною копією всіх даних.

## Що входить до Git

Код Python, тести, Docker Compose, requirements, початкові SQL-схеми, SQL-знімки в’ю, конфігуратор NiFi, специфікація Metabase, словники, документація та історичні скріншоти.

`nifi/build_pipeline.py` відтворює потік через API. `bi/dashboard_spec.json` зберігає конфігурацію графіків без ID та паролів. Секретні connection details не потрібні для публікації: при запуску створюються локальні облікові записи.

## Що залишається локально

| Файл / об’єкт | Навіщо |
|---|---|
| `.env` | Паролі БД/NiFi, імена та порти |
| `.secrets/metabase/admin.json` | Вхід адміністратора Metabase і пароль BI-reader |
| `.secrets/metabase/manifest.json` | ID та посилання поточної інсталяції |
| `.secrets/metabase/deployment.env` | Локальне підключення BI до старого стека, якщо використовується |
| `.secrets/telegram/config.json` | Токен власного бота |
| Docker-томи | БД, агрегати, черги, checkpoints та службовий стан |

Файли з реальними паролями й токенами не додаються до комітів. Онлайн-копія чотирьох погоджених файлів збережена окремо в GitHub Secrets; [відновлення](REMOTE_CONFIGURATION.md). `.env.example` є достатнім шаблоном, bootstrap генерує випадкові значення. Паролі діючих томів не можна обертати простим редагуванням .env: потрібна окрема зміна в самій БД.

## Що можна очищувати

Python-кеші `__pycache__`, `.pytest_cache` та тимчасові локальні звіти не потрібні для розгортання. Вони ігноруються Git. Ініціалізаційні SQL, міграційні знімки й сумісні модулі залишені: вони беруть участь у відтворенні схеми або зберігають чинні інтерфейси. Це не випадкові дублікати.

Не видаляйте Docker-томи, .env, .secrets, checkpoints, журнал незавершеного запису або каталоги, які змонтовані у чинні контейнери. Старий live-каталог може використовуватися працюючими контейнерами; перед його видаленням потрібна окрема перевірена міграція запуску.

## Зміна й публікація

Новий файл спочатку опишіть у словнику FILES в tools/build_reference_docs.py. Для нових об’єктів БД оновіть знімок метаданих і пояснення полів. Зміни графіків вносьте до bi/dashboards.py.

Послідовність для актуальних файлів, включно з новими:

```bash
python tools/export_dashboard_spec.py
python tools/run_checks.py
git add .
python tools/build_reference_docs.py
git add docs/FILES_REFERENCE.md docs/DATABASE_REFERENCE.md docs/DASHBOARD_REFERENCE.md
python tools/audit_documentation.py
python tools/check_publication.py
git diff --cached --check
git diff --cached --stat
git commit -m "Update project implementation and documentation"
git push
```

Генератор читає список Git, тому нові файли потрібно додати до staging перед генерацією. Після генерації оновлені довідники теж додаються до staging. Звичайна перевірка без змін починається з python tools/audit_documentation.py і не переписує файлів.

За наявності запущеного стека додатково виконайте python tools/verify_analytics_views.py та python tools/verify_metabase.py. Вони читають дані й не надсилають Telegram-повідомлень. Локальні модульні тести використовують підставні відповіді, не зовнішніх адресатів.
