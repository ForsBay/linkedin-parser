# LinkedIn Jobs Parser

Парсер вакансий LinkedIn на Python + Django + PostgreSQL

## Как это работает

Используются публичные API LinkedIn, которые сайт вызывает при просмотре вакансий без логина
(нашел через DevTools → Network):

| Что | Запрос |
|---|---|
| Поиск | `GET /jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=...&location=...&start=0` |
| Вакансия | `GET /jobs-guest/jobs/api/jobPosting/<job_id>` |
| Компания | `GET /company/<slug>` |

Ответы приходят кусками HTML, их разбирает BeautifulSoup (`jobs/linkedin.py`)

Парсер разделен на две независимые части (две management-команды):

1. **Search** (`run_search`): берет активные поисковые запросы из админки, листает выдачу
   по 10 вакансий (параметр `start`) и сохраняет вакансии в БД со статусом `new`
   LinkedIn отдает максимум ~1000 вакансий на один поиск. Фильтры по опыту и типу занятости
   гостевой API игнорирует, а локацию учитывает, поэтому для USA поиск дополнительно идет
   по каждому штату (`California, United States` и т.д.). Так собирается в разы больше вакансий
2. **Details** (`run_details`): берет вакансии со статусом `new` (и `error`, если попыток < 3),
   скачивает полное описание, критерии (seniority, employment type, industries),
   число откликов, зарплату, признак закрытой вакансии, а также страницу компании
   (сайт, индустрия, размер, штаб-квартира, тип, год основания, специализации,
   подписчики, сотрудники в LinkedIn, описание). Статус меняется на `done` или `error`

Дубликатов нет: `job_id` вакансии и `slug` компании уникальные в БД. Если вакансия
нашлась по нескольким запросам, она одна, просто привязана к нескольким запросам (M2M)

Обработка ошибок и повторный запуск:
- при 429 / 999 / 5xx / ошибках сети запрос повторяется с паузой (до 5 раз);
- ошибка одной вакансии не останавливает парсер, она получает статус `error` и текст ошибки;
- обе команды можно перезапускать сколько угодно: search не создаст дублей, details
  продолжит с необработанных вакансий;
- в админке есть действие «Отправить на повторную обработку»

## Запуск

Нужны Python 3.9+ и PostgreSQL

```bash
# 1. PostgreSQL (если нет своего)
docker compose up -d

# 2. окружение
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # при необходимости поменять доступы к БД

# 3. база и админ
python manage.py migrate
python manage.py createsuperuser

# 4. админка
python manage.py runserver
```

Открыть http://127.0.0.1:8000/admin/ → «Поисковые запросы» → добавить запрос,
например `Python Developer` / `USA`. Можно добавить несколько запросов с разными странами

```bash
# Часть 1 — поиск
python manage.py run_search
python manage.py run_search --query-id 1      # только один запрос
python manage.py run_search --no-split        # без разбивки по штатам (быстро, до ~1000 вакансий)

# Часть 2 — детали вакансий и компаний
python manage.py run_details
python manage.py run_details --limit 100 --workers 3 --delay 1
python manage.py run_details --retry-errors   # повторить все вакансии с ошибками

# Выгрузка
python manage.py export_jobs --output jobs.csv
python manage.py export_jobs --output jobs.xlsx --only-done
```

Части можно запускать одновременно в двух терминалах: details будет обрабатывать то,
что search уже успел сохранить

## Структура

```
config/                     настройки Django
jobs/models.py              SearchQuery, Job, Company
jobs/admin.py               админка
jobs/linkedin.py            запросы к LinkedIn и парсинг HTML
jobs/management/commands/
    run_search.py           часть 1
    run_details.py          часть 2
    export_jobs.py          выгрузка в CSV / Excel
```

## Замечания

- Без авторизации LinkedIn иногда ограничивает частоту запросов (429). Если ошибок много,
  увеличьте `--delay` или уменьшите `--workers`
- Если порт 5432 уже занят локальным PostgreSQL, поменяйте в `docker-compose.yml` на `"5433:5432"` и в `.env` `DB_PORT=5433`
- «Job function» и ссылку на отклик LinkedIn без логина не отдает, поэтому их нет
- В конце `run_details` повторно скачиваются компании, которые не загрузились раньше
- Зарплата есть не у всех вакансий, LinkedIn показывает ее только если работодатель ее указал
