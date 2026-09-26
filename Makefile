.DEFAULT_GOAL := help
.PHONY: help up down logs organizer admin

PYTHON ?= python3
COMPOSE ?= docker compose

help:
	@printf '%s\n' 'Команды из корня репозитория:' '  make up                       Собрать и запустить сайт, API и PostgreSQL' '  make admin EMAIL=you@site.ru  Создать master admin (полный доступ и роли; пароль спросит команда)' '  make logs                     Смотреть логи всех сервисов (Ctrl+C для выхода)' '  make down                     Остановить сервисы, сохранив данные БД'

up:
	@$(PYTHON) tools/init_env.py
	$(COMPOSE) up --build --wait
	@printf '%s\n' 'Сайт готов: http://localhost:8080' 'API: http://localhost:8000/docs'

# admin создаёт master admin; organizer оставлен как совместимый псевдоним.
admin organizer:
	@if [ -z "$(EMAIL)" ]; then printf '%s\n' 'Укажите почту: make admin EMAIL=you@site.ru'; exit 1; fi
	$(COMPOSE) exec api python -m app.seed --email "$(EMAIL)"

logs:
	$(COMPOSE) logs --follow --tail=100

down:
	$(COMPOSE) down
