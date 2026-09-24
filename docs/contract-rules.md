# Правила API

Истина для форм запросов и ответов — `contracts/openapi.json`. Префикс всех путей `/api/v1`; он обозначает совместимость API, а не этап продукта. Версии v1/v2/v3 в `architecture.md` и расширении `x-milestone` обозначают порядок реализации.

## Общие правила

| Тема | Решение |
|---|---|
| Формат | JSON, имена полей `camelCase`, UUID в строках, даты UTC `2026-09-25T12:00:00Z`. Неизвестные поля запроса — `422`. |
| Списки | `items`, `page`, `pageSize`, `total`; страница с 1, размер по умолчанию 20, максимум 100. Пустой список — `items: []`, не `404`. |
| Сессия | Непрозрачный cookie-токен, хеш которого хранится в PostgreSQL `sessions`. `GET /auth/csrf` получает token и cookie; `POST /auth/login` или `/auth/register` ротирует сессию. `POST /auth/logout` удаляет запись, `GET /auth/me` возвращает `401` без входа. Redis и JWT в MVP не используются. |
| CSRF | На каждом `POST`, `PUT`, `PATCH`, `DELETE`: `X-CSRF-Token`. Токен связан с текущей сессией; после login/register заново вызвать `/auth/csrf`. Сервер проверяет `Origin` для изменяющих запросов. |
| Права | `401` — нет действующей сессии, `403` — нет роли или неверный CSRF/Origin. Для черновой карточки соревнования публичному посетителю — `404`. |
| Ошибка | Всегда `{ "code": "...", "message": "..." }`; `fields` — необязательная карта ошибок полей при `422`. Клиент привязывает UX к `code`, не к тексту. |
| Обновление | `PATCH` меняет только переданные поля; `null` очищает только nullable-поля. `PUT` черновика результата заменяет пару `place`/`scoreText`. |

## Последовательность запросов фронтенда

1. На загрузке вызвать `GET /auth/me`: `200` означает вошедшего, `401` — гостя. До первого изменяющего запроса вызвать `GET /auth/csrf`.
2. После входа/регистрации снова вызвать `/auth/csrf`, так как сессия сменилась.
3. Для каталога вызвать `/disciplines`, `/competitions`; для карточки `/competitions/{id}`. `registrationOpen` показывает возможность заявки по времени и статусу, а `viewerRegistrationId` — существующую заявку текущего спортсмена. Финальное право всё равно проверяет сервер.
4. Для страницы организатора: `/competitions/{id}/participants`, `/competitions/{id}/results/drafts`; сохранить каждое место через PUT; затем один раз вызвать `/competitions/{id}/results/publish`.
5. После публикации заново запросить `/competitions/{id}/results` и `/ratings`. Черновик никогда не отображается на публичной странице.

## Коды ошибок с предметным смыслом

| Условие | HTTP | `code` |
|---|---:|---|
| Неверный email или пароль | 401 | `INVALID_CREDENTIALS` |
| Нет сессии | 401 | `UNAUTHENTICATED` |
| Неверный CSRF или Origin | 403 | `CSRF_INVALID` |
| Нет роли | 403 | `FORBIDDEN` |
| Дисциплина, соревнование или заявка не найдены | 404 | `NOT_FOUND` |
| Email уже занят | 409 | `EMAIL_TAKEN` |
| Заявка уже существует | 409 | `ALREADY_REGISTERED` |
| Регистрация закрыта или соревнование не опубликовано | 409 | `REGISTRATION_CLOSED` |
| Публикация/правка не допускается в текущем статусе | 409 | `INVALID_STATE` |
| Результаты уже опубликованы | 409 | `ALREADY_COMPLETED` |
| Нет черновиков для публикации | 409 | `NO_RESULTS` |
| Некорректные поля, даты, ID дисциплин | 422 | `VALIDATION_ERROR` |

## Контракт между Б1 и Б2 внутри бэкенда

```python
class CompetitionPort:
    def lock_for_result_publication(self, competition_id: UUID, uow: UnitOfWork) -> None: ...
    def get_registration(self, competition_id: UUID, registration_id: UUID, uow: UnitOfWork) -> ParticipantSummary: ...
    def list_participants(self, competition_id: UUID, uow: UnitOfWork) -> list[ParticipantSummary]: ...
    def complete_competition(self, competition_id: UUID, uow: UnitOfWork) -> None: ...

class IdentityPort:
    def get_athlete_summaries(self, athlete_ids: list[UUID], uow: UnitOfWork) -> dict[UUID, AthleteSummary]: ...
```

`lock_for_result_publication` делает `SELECT ... FOR UPDATE` и проверяет статус `published`. Затем Б2 публикует результаты и вызывает `complete_competition` в той же транзакции. Б1 проверяет переход `published -> completed`; Б2 отвечает за атомарность. Б2 не обновляет таблицу `competitions` напрямую. Чтение данных спортсменов для рейтинга идёт через `IdentityPort` без N+1 запросов. В FastAPI статические маршруты `/results/drafts` и `/results/publish` регистрируются до параметризованного `/results/{registrationId}`.
