from pathlib import Path
import sys,csv,json
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'collector'))
from app.kpi_catalog import KPI,DIMENSIONS
header=['Код KPI','Назва українською','Одиниця','Агрегація','Формула','Пояснення']
with (root/'docs'/'KPI_DICTIONARY.csv').open('w',encoding='utf-8-sig',newline='') as file:
    writer=csv.writer(file,delimiter=';');writer.writerow([header[i] for i in (0,1,2,5)]);writer.writerows([[r[i] for i in (0,1,2,5)] for r in KPI])
text='# Словник KPI та правила агрегації\n\n'
text+='Словник зберігається тільки в ClickHouse: monitoring.kpi_dictionary (для прямого читання FINAL). Поля й ідентифікатори описані у monitoring.field_dictionary. PostgreSQL містить операційні дані: інциденти, Telegram та діагностику обробки.\n\n'
text+='| '+' | '.join(header)+' |\n|'+ '|'.join(['---']*len(header))+'|\n'
for row in KPI:text+='| '+' | '.join(str(v).replace('|','/').replace('\n',' ') for v in row)+' |\n'
text+='\n## Групування\n\nГодина: початок години UTC × зонд × measurement ID × IP-версія × ASN. День: календарна дата Europe/Kyiv × ті самі виміри. Різні цілі й IPv4/IPv6 не змішуються. У провайдерському зрізі прибирається вимір зонда, а кількість зондів рахується DISTINCT за всім періодом.\n\n'
text+='## Як читати звіти\n\nУ ClickHouse додано hourly_kpi, daily_kpi, hourly_provider_kpi, daily_provider_kpi. Кожен рядок містить period_start, period_end, period_name_uk, period_label, виміри групування, kpi_code, kpi_name_uk, kpi_value, unit_uk. Формули зберігаються лише в документації. Широкі hourly_network_metrics, daily_network_metrics та провайдерські views також мають period_name_uk і period_label.\n\n'
text+='## Приклад правильного середнього\n\nЗа першу годину маємо 100 коректних серій зі середнім 10 мс, за другу — 1 серію зі значенням 100 мс. Середнє дня = (100 × 10 + 1 × 100) / 101 = 10,89 мс. Усереднення двох погодинних середніх дало б неправильні 55 мс. Вага тут — кількість серій із коректним RTT, не кількість надісланих пакетів.\n\n'
text+='## Запуск за правилами зберігання\n\nУся обробка вимірювань тепер працює тільки з ClickHouse. Docker-обробник перед записом перевіряє дублікати й зберігає короткочасний журнал незавершеної операції у власному Docker-томі. Після підтвердження ClickHouse журнал видаляється. Фіксовані версії погодинних знімків дозволяють безпечно повторити незавершений запис. Materialized views ping_ingest_trigger та status_ingest_trigger фіксують INSERT у retention_runs. Згортання й очищення запускає Docker-обробник після кожної заливки та за часом; PostgreSQL у цьому не бере участі.\n\n'
text+='Сирі події зберігаються 5 годин; завершені години — 48 годин від початку години; попередній календарний день згортається о 04:00 за Києвом; дні не видаляються. Погодинні накопичувачі оновлюються на кожну подію, але готова година публікується після її завершення. Часовий обробник додатково прокидається на межі години та 04:00 без очікування нової заливки; це необхідно, бо SQL-тригер сам по собі не запускається від годинника. Реальний запуск може зсунутися на час виконання поточної транзакції або збою; після відновлення відбувається дозавершення.\n\n'
text+='На 04:00 попередня доба вже завершена; запізнілі події в межах 5 годин можуть уточнити її без подвоєння. Сирі дані старші 5 годин у звичайному потоці не приймаються. Перед видаленням годин денний запис має бути підтверджено ClickHouse. Це обробка на події INSERT з окремим часовим запуском, а не реляційний SQL-тригер PostgreSQL.\n\n'
text+='## Назви вимірів\n\n| Поле | Назва |\n|---|---|\n'
for code,label in DIMENSIONS:text+='| '+code+' | '+label+' |\n'
(root/'docs'/'KPI_DICTIONARY.md').write_text(text,encoding='utf-8')
print('Saved KPI_DICTIONARY.md and CSV with',len(KPI),'KPI definitions')
