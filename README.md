# ТехноСпортФест 2026

Монорепозиторий FastAPI и React/Vite. Реализованы авторизация, профиль, соревнования, заявки, результаты, рейтинг, новости, документы и фронтенд MVP. Формы всех API зафиксированы в OpenAPI. [Ручной сквозной прогон](docs/manual-qa.md) выполнен в браузере Codex на локальном API.

## Стек и договорённости

- [Выбранные библиотеки и причины](docs/stack.md).
- [Схема системы и версии v1 → v2 → MVP](docs/architecture.md).
- [Правила API и ошибок](docs/contract-rules.md), [OpenAPI 3.0.3](contracts/openapi.json), [JSON-примеры](contracts/examples/).
- [Задачи каждого участника](docs/work-items.md).

## Запуск локально

Нужны запущенный Docker Desktop (с Docker Compose), `make` и Python 3.10+. Node отдельно устанавливать не нужно: фронтенд собирается внутри Docker. Из корня репозитория:

```bash
make up
```

Команда создаёт локальный `backend/.env`, собирает и запускает PostgreSQL, FastAPI и Nginx с фронтендом, ждёт проверки готовности сервисов. Сайт: `http://localhost:8080`. API: `http://localhost:8000/health` и `http://localhost:8000/docs`. Swagger показывает реализованные маршруты, полный согласованный контракт лежит в `contracts/openapi.json`. Локальная PostgreSQL доступна на `localhost:5433`. При старте API применяет `alembic upgrade head`. Nginx отдаёт SPA и проксирует `/api/v1` в FastAPI; JWT остаётся в `HttpOnly` cookie.

Основные команды:

```bash
make admin EMAIL=you@example.com  # создать master admin (полный доступ + управление ролями), пароль вводится интерактивно
make logs                             # смотреть логи; Ctrl+C завершает просмотр
make down                             # остановить сервисы, данные PostgreSQL сохранятся
```

Публичная регистрация создаёт только спортсмена. `make down` сохраняет данные в Docker volume, повторный `make up` их не сбрасывает. Для отдельной разработки фронтенда при работающем `make up`:

```bash
cd frontend && npm ci && npm run dev
```

Vite откроется на `http://localhost:5173` и проксирует `/api/v1` в FastAPI. Пароль администратора не хранится в репозитории. Роли создаются master admin в разделе «Роли и права» (`/manage/roles`): например, роль «Копирайтер» с доступом только к новостям. В production задайте свой `JWT_SECRET`, `APP_ORIGINS` и `COOKIE_SECURE=true`; локальный `.env` игнорируется Git.

## Деплой и CD

Продакшен живёт на сервере **Beget VPS** (`http://90.156.169.166`) и поднимается Docker Compose: базовый [`compose.yaml`](compose.yaml) + продовый оверлей [`compose.prod.yaml`](compose.prod.yaml). Оверлей открывает порт `80` наружу, держит API и PostgreSQL внутри docker-сети и задаёт продовые переменные (JWT-секрет, `APP_ORIGINS`).

**Как работает CD:** каждый push в `main` прогоняет проверки (контракт, тесты бэкенда, тесты фронтенда, smoke-тест). После зелёных проверок джоба `deploy` из [`.github/workflows/checks.yml`](.github/workflows/checks.yml) синхронизирует файлы репозитория на сервер по `rsync` (через SSH-ключ `DEPLOY_KEY`) и пересобирает контейнеры (`docker compose up -d --build`). Серверу не нужен собственный доступ к GitHub: код ему присылает сам воркфлоу. Миграции Alembic применяются автоматически при старте API. Локально ничего запускать не нужно.

Ссылки на сервере:

- Сайт: http://90.156.169.166
- Health-проверка: http://90.156.169.166/health
- API: http://90.156.169.166/api/v1/

### Секреты GitHub (Settings → Secrets and variables → Actions)

| Тип | Имя | Значение |
|---|---|---|
| Variable | `DEPLOY_HOST` | `90.156.169.166` |
| Variable | `DEPLOY_USER` | `root` |
| Secret | `DEPLOY_KEY` | приватный SSH-ключ (публичная часть прописана в `~/.ssh/authorized_keys` на сервере) |

Ручной деплой без пуша: вкладка **Actions** → **Checks** → **Run workflow**.

### Первичная настройка сервера (выполняется один раз)

Код на сервер доставляет `rsync` из GitHub Actions, поэтому серверу достаточно Docker, rsync и пустой директории `/opt/tsf`.

```bash
# на сервере от root:
apt-get update && apt-get install -y curl git rsync
curl -fsSL https://get.docker.com | sh && systemctl enable --now docker
mkdir -p /opt/tsf
```

Дальше публичный ключ SSH (от `DEPLOY_KEY`) прописывается в `/root/.ssh/authorized_keys`, после чего воркфлоу сам кладёт файлы в `/opt/tsf` и пересобирает стек (`backend/.env` на сервере не перезаписывается — он исключён из синхронизации).

Дальше обновления приходят сами через `git pull` в джобе `deploy`.

> ⚠️ Пока это dev-окружение: `JWT_SECRET` временно лежит в [`compose.prod.yaml`](compose.prod.yaml), HTTPS не настроен (`COOKIE_SECURE=false`). Перед реальным запуском фестиваля секрет нужно вынести в GitHub Secret, сменить пароль `root` на сервере и добавить HTTPS.

## Проверки

```bash
python3 tools/check_contract.py
cd backend && .venv/bin/python -m pytest -q
cd ../frontend && npm test && npm run build
```

Установите зависимости бэкенда через `cd backend && python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'`, если запускаете тесты без Docker. Команды Alembic выполняются из `backend/`: `.venv/bin/alembic upgrade head`, `.venv/bin/alembic revision --autogenerate -m "описание"`. Миграции в общей ветке должны сохранять один линейный head. Тесты фронтенда проверяют вход, заявку, черновик и публикацию с подменённым API; тест Б1 проверяет интеграцию с настоящим `CompetitionPort`. CI запускает `make up` с PostgreSQL и Nginx и проверяет `/health`, `/api/v1/disciplines` и главную страницу. Полный ручной сценарий через контейнерный стек перед развёртыванием ещё нужен.

## Кто меняет что

Б1 владеет `backend/app/modules/identity`, `competitions`, миграциями пользователей и соревнований. Б2 владеет `results`, `content` и их миграциями. Общие `db.py`, `main.py` и конфигурацию меняют согласованно. Фронтенд получает типы через `cd frontend && npm run types:api`. Изменение внешнего API включает обновление `contracts/openapi.json` и JSON-примеров.
