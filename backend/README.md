# Бэкенд: ожидаемая структура

```text
backend/
  app/
    main.py                 # создание FastAPI, подключение роутеров
    db.py                   # UnitOfWork, подключение PostgreSQL
    modules/
      identity/             # Б1: users, profiles, JWT, auth
      competitions/         # Б1: disciplines, competitions, registrations
      results/              # Б2: results, rating, публикация
      content/              # Б2: news, documents
  migrations/               # один линейный Alembic head
  tests/                    # предметные и сквозные тесты
```

Папки модулей зарезервированы для владельцев. Б1 добавляет исполняемый каркас и миграции, Б2 добавляет свои роутеры и сервисы. Внешние маршруты и схемы заданы в `../contracts/openapi.json`; внутренние порты — в `../docs/contract-rules.md`.
