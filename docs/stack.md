# Зафиксированный стек

Выбор сделан для одного FastAPI-приложения и небольшой команды. Прямые версии зависимостей закреплены в `backend/pyproject.toml` и `frontend/package-lock.json`.

| Часть | Библиотека | Причина |
|---|---|---|
| HTTP API | FastAPI 0.141.1 + Uvicorn 0.53.0 | Роуты и валидация поверх Pydantic, встроенная OpenAPI-документация. |
| Модели и запросы | SQLAlchemy 2.0.54, синхронный режим | Одна БД и простые транзакции; `async` не ускоряет эту предметную логику. |
| Драйвер PostgreSQL | psycopg 3.3.6 (`postgresql+psycopg://`) | Поддерживается SQLAlchemy 2, без второго DB-слоя. |
| Миграции | Alembic 1.20.0 | Инструмент миграций SQLAlchemy; одна последовательная история миграций. |
| Настройки | pydantic-settings 2.15.0 | Значения из окружения и локального `.env`. |
| Вход | PyJWT 2.15.0 + pwdlib 0.3.1/Argon2 | Короткий JWT в cookie; пароли хранятся только как хеш. Роли проверяются через FastAPI dependency. |
| Проверки | pytest + httpx | Тесты auth и HTTP-контракта. |
| Фронтенд | React 19.3, TypeScript 5.9, Vite 8.3 | Простой SPA-старт. TypeScript 5.9 закреплён из-за совместимости с генератором типов. |
| API-клиент | openapi-typescript 7.13 + типизированный `fetch` | Формы данных генерируются из общего `contracts/openapi.json`; обработка ошибок API и cookie сосредоточена в одном файле. |
| Инфраструктура | PostgreSQL 17, Docker Compose | Одна БД, запуск одной командой; Redis и брокер для MVP не нужны. |

Используем синхронные SQLAlchemy Session и psycopg: все записи результатов и смена статуса соревнования идут в одной транзакции. Auth middleware проверяет JWT и `Origin`; `require_role(...)` в маршрутах проверяет роль. Библиотеки вроде готового `fastapi-users` не добавляем: у нас две роли и четыре auth-маршрута.

Основные источники выбора: [FastAPI JWT и pwdlib](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [Alembic](https://alembic.sqlalchemy.org/en/latest/), [SQLAlchemy psycopg](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg), [Vite](https://vite.dev/guide/), [OpenAPI TypeScript](https://openapi-ts.dev/introduction).
