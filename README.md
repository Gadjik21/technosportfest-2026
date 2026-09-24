# ТехноСпортФест 2026

Монорепозиторий для фронтенда и двух бэкендеров. Сейчас запускаются каркас FastAPI, авторизация, первая миграция и React/Vite. Предметные маршруты соревнований, результатов и контента остаются задачами v1/v2; их формы уже зафиксированы в OpenAPI.

## Стек и договорённости

- [Выбранные библиотеки и причины](docs/stack.md).
- [Схема системы и версии v1 → v2 → MVP](docs/architecture.md).
- [Правила API и ошибок](docs/contract-rules.md), [OpenAPI 3.0.3](contracts/openapi.json), [JSON-примеры](contracts/examples/).
- [Задачи каждого участника](docs/work-items.md).

## Запуск локально

Нужны Docker с работающим daemon, Python 3.10+ для создания локального `.env` и Node 22.12+ для фронтенда.

```bash
python3 tools/init_env.py
docker compose up --build
```

API: `http://localhost:8000/health` и `http://localhost:8000/docs`. Swagger сейчас показывает только реализованные auth-маршруты; полный согласованный контракт лежит в `contracts/openapi.json`. Локальная PostgreSQL доступна на `localhost:5433`. При старте API применяет `alembic upgrade head`.

В другом терминале:

```bash
cd frontend
npm ci
npm run dev
```

Фронтенд открывается на `http://localhost:5173` и проксирует `/api/v1` в FastAPI. Для демонстрационной учётной записи организатора:

```bash
docker compose exec api python -m app.seed --email organizer@example.com
```

Команда запросит пароль; пароль не хранится в репозитории. Публичная регистрация создаёт только спортсмена. В production задайте свой `JWT_SECRET`, `APP_ORIGINS` и `COOKIE_SECURE=true`; локальный `.env` игнорируется Git.

## Проверки

```bash
python3 tools/check_contract.py
cd backend && .venv/bin/python -m pytest -q
cd ../frontend && npm run build
```

Установите зависимости бэкенда через `cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`, если запускаете тесты без Docker. Команды Alembic выполняются из `backend/`: `.venv/bin/alembic upgrade head`, `.venv/bin/alembic revision --autogenerate -m "описание"`. Миграции в общей ветке должны сохранять один линейный head.

## Кто меняет что

Б1 владеет `backend/app/modules/identity`, `competitions`, миграциями пользователей и соревнований. Б2 владеет `results`, `content` и их миграциями. Общие `db.py`, `main.py` и конфигурацию меняют согласованно. Фронтенд получает типы через `cd frontend && npm run types:api`. Изменение внешнего API включает обновление `contracts/openapi.json` и JSON-примеров.
