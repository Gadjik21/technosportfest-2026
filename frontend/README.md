# Фронтенд

React + TypeScript + Vite. `npm ci` устанавливает закреплённые версии, `npm run dev` запускает сайт на `http://localhost:5173`, `npm run build` генерирует API-типы, проверяет TypeScript и собирает SPA.

`src/api.ts` — общий типизированный клиент. Он работает с `/api/v1` на том же origin; Vite проксирует запросы в локальный FastAPI. `HttpOnly` JWT cookie отправляется браузером, JavaScript не читает токен. На старте приложения вызывайте `GET /auth/me` и показывайте форму входа при `401`. Типы обновляются через `npm run types:api` из `../contracts/openapi.json`.

Сейчас `App.tsx` — стартовая страница и индикатор доступности API. Экраны v1/v2 распределены в `../docs/work-items.md`; точные JSON-формы — в `../contracts/examples/`.
