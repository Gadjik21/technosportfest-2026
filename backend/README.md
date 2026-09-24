# Бэкенд

Каркас включает FastAPI, регистрацию спортсмена, вход, выход, `/auth/me`, JWT/Origin middleware, Pydantic-ошибки, SQLAlchemy Session и миграцию `0001_auth`. Предметные роутеры подключены в `app/main.py`, но пока пусты. Канонический внешний контракт — `../contracts/openapi.json`.

```text
app/config.py                      окружение
app/db.py                          SQLAlchemy Session
app/main.py                        middleware и роутеры
app/modules/identity/             Б1: auth, users, profiles
app/modules/competitions/         Б1: соревнования и заявки
app/modules/results/              Б2: результаты и рейтинг
app/modules/content/              Б2: новости и документы
migrations/                       единая цепочка Alembic
tests/                            проверки auth
```

Для локального Python-запуска без Docker нужна работающая PostgreSQL и `../tools/init_env.py`. Из этой папки: `.venv/bin/pip install -e '.[dev]'`, `.venv/bin/alembic upgrade head`, `.venv/bin/uvicorn app.main:app --reload`. У `app.seed` только CLI для организатора; публичного эндпоинта выдачи этой роли нет.

При добавлении новых моделей импортируйте их в `migrations/env.py`, чтобы Alembic видел метаданные. Б2 использует `CompetitionPort` и `IdentityPort` из модулей Б1, не пишет в их ORM-таблицы напрямую. Для защищённого маршрута: `Depends(get_current_principal)` или `Depends(require_role("organizer"))`.
