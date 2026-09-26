# Бэкенд

FastAPI + PostgreSQL (Alembic). Реализованы авторизация (JWT/Origin), профиль спортсмена, дисциплины, соревнования с заявками, участники; модули Results/Rating и Content (Б2) подключены и работают через порты `CompetitionPort`/`IdentityPort`. Канонический внешний контракт — `../contracts/openapi.json`.

```text
app/config.py                      окружение
app/db.py                          SQLAlchemy Session
app/main.py                        middleware и роутеры
app/modules/identity/             Б1: auth, users, profiles (включая /me)
app/modules/competitions/         Б1: дисциплины, соревнования, заявки, CompetitionPort
app/modules/results/              Б2: результаты и рейтинг
app/modules/content/              Б2: новости и документы
app/modules/contests/             задания, решения и контракт проверки кода
migrations/                       единая цепочка Alembic (head: 0007_code_judge)
tests/                            auth, competitions/results/content/contests/judge
```

Для локального Python-запуска без Docker нужна работающая PostgreSQL и `../tools/init_env.py`. Из этой папки: `.venv/bin/pip install -e '.[dev]'`, `.venv/bin/alembic upgrade head`, `.venv/bin/uvicorn app.main:app --reload`.

Seed-данные (`python -m app.seed`):

```bash
python -m app.seed --email admin@example.com       # master admin (полный доступ и управление ролями)
python -m app.seed --demo                          # вымышленные спортсмены, соревнование, заявки
```

Пароль master admin запрашивается интерактивно и не хранится в репозитории; демо-спортсмены используют общий пароль `demo-password-123`. Публичного эндпоинта выдачи административных ролей нет: master admin создаётся только этим CLI, остальные роли — через `/admin/roles`.

## Реализовано Б1

- `GET /disciplines` — справочник дисциплин.
- `POST /competitions` (organizer) → черновик; `PATCH /competitions/{id}` (только draft); `POST /competitions/{id}/publish` (draft → published, дедлайн в будущем).
- `GET /competitions` — каталог: публично `published`/`completed`; `status=draft` только для организатора, остальным 403. Сортировка `startsAt,id`.
- `GET /competitions/{id}` — карточка: draft виден только организатору (остальным 404); `registrationOpen` и `viewerRegistrationId` для спортсмена.
- `POST /competitions/{id}/registrations` (athlete): соревнование `published`, `now < registrationDeadline`; повторная заявка — `409 ALREADY_REGISTERED`.
- `GET /me/registrations` — мои заявки; `GET /competitions/{id}/participants` — участники организатору (сортировка `fullName,registrationId`).
- `GET/PATCH /me` — профиль спортсмена: ФИО, образование, населённый пункт, дисциплины.

`CompetitionPort` (см. `app/modules/competitions/ports.py`) реализован в `app/modules/competitions/adapter.py`: `lock_for_result_publication` делает `SELECT ... FOR UPDATE` и проверяет `status=published`; `complete_competition` завершает соревнование в той же транзакции; чтения без N+1. Results/Б2 подключён к реальному адаптеру через `app/modules/results/deps.py`.

При добавлении новых моделей импортируйте их в `migrations/env.py`, чтобы Alembic видел метаданные. Для защищённого маршрута: `Depends(get_current_principal)`, `Depends(require_role("athlete"))` для спортсменских ручек или `Depends(require_permission("news.create"))` для прав раздела (каталог прав — `app/modules/identity/permissions.py`).
# Проверка программных решений

Программная задача хранит обязательные тесты и лимиты: 15 секунд и 128 МиБ по умолчанию, не более 512 МиБ. Первый `visibleTestCount` тестов виден участнику; остальные входы, ожидаемые и фактические выводы доступны только организатору. API сохраняет отправленный код и возвращает вердикт, номер первого неуспешного теста, время и наблюдаемый пик памяти. Старые задания с ручной оценкой продолжают работать.

`JUDGE_ENABLED` по умолчанию выключен. Пока отдельный исполнитель не подключён, соревнование с программными задачами нельзя опубликовать, а отправка кода возвращает `JUDGE_UNAVAILABLE`. Одинокий API не должен получать доступ к Docker хоста. Исполнитель в `app/judge_worker.py` подготовлен для отдельной изолированной среды; подключение его к рабочему серверу требует отдельного решения по безопасности и проверки на Linux с PostgreSQL и Docker. Образ компилятора Kotlin описан в `judge-kotlin.Dockerfile`.
