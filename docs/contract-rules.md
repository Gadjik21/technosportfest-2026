# Правила API

Истина для форм запросов и ответов — `contracts/openapi.json`. Префикс всех путей `/api/v1`; он обозначает совместимость API, а не этап продукта. Версии v1/v2/v3 в `architecture.md` и расширении `x-milestone` обозначают порядок реализации.

## Общие правила

| Тема | Решение |
|---|---|
| Формат | JSON, имена полей `camelCase`, UUID в строках, даты UTC `2026-09-25T12:00:00Z`. Неизвестные поля запроса — `422`. |
| Списки | `items`, `page`, `pageSize`, `total`; страница с 1, размер по умолчанию 20, максимум 100. Пустой список — `items: []`, не `404`. |
| Вход | `POST /auth/login` или `/auth/register` ставит `HttpOnly` cookie с JWT на 24 часа. Refresh-токена нет. `POST /auth/logout` очищает cookie; `GET /auth/me` возвращает `401` при отсутствии или истечении JWT. |
| CSRF | На каждом `POST`, `PUT`, `PATCH`, `DELETE` сервер требует совпадающий `Origin`; cookie имеет `SameSite=Lax`. Отдельного CSRF-токена и заголовка нет. |
| Права | `401` — нет действующего JWT, `403` — нет роли или неверный/отсутствующий Origin. Для черновой карточки соревнования публичному посетителю — `404`. |
| Ошибка | Всегда `{ "code": "...", "message": "..." }`; `fields` — необязательная карта ошибок полей при `422`. Клиент привязывает UX к `code`, не к тексту. |
| Обновление | `PATCH` меняет только переданные поля; `null` очищает только nullable-поля. `PUT` черновика результата заменяет пару `place`/`scoreText`. |

## Последовательность запросов фронтенда

1. На загрузке вызвать `GET /auth/me`: `200` означает вошедшего, `401` — гостя. JavaScript не читает JWT; браузер отправляет cookie автоматически.
2. После входа/регистрации обновить состояние пользователя из ответа `POST /auth/login` или `/auth/register`. При `401` после истечения JWT показать форму входа.
3. Для каталога вызвать `/disciplines`, `/competitions`; для карточки `/competitions/{id}`. `registrationOpen` показывает возможность заявки по времени и статусу, а `viewerRegistrationId` — существующую заявку текущего спортсмена. Финальное право всё равно проверяет сервер.
4. Для страницы организатора: `/competitions/{id}/participants`, `/competitions/{id}/results/drafts`; сохранить каждое место через PUT; затем один раз вызвать `/competitions/{id}/results/publish`.
5. После публикации заново запросить `/competitions/{id}/results` и `/ratings`. Черновик никогда не отображается на публичной странице.

## Коды ошибок с предметным смыслом

| Условие | HTTP | `code` |
|---|---:|---|
| Неверный email или пароль | 401 | `INVALID_CREDENTIALS` |
| Нет JWT или он истёк | 401 | `UNAUTHENTICATED` |
| Неверный или отсутствующий Origin | 403 | `ORIGIN_INVALID` |
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
    def lock_for_result_publication(self, competition_id: UUID, db: Session) -> None: ...
    def get_registration(self, competition_id: UUID, registration_id: UUID, db: Session) -> ParticipantSummary: ...
    def list_participants(self, competition_id: UUID, db: Session) -> list[ParticipantSummary]: ...
    def complete_competition(self, competition_id: UUID, db: Session) -> None: ...

class IdentityPort:
    def get_athlete_summaries(self, athlete_ids: list[UUID], db: Session) -> dict[UUID, AthleteSummary]: ...
```

Реальные Protocol-интерфейсы лежат в `backend/app/modules/competitions/ports.py` и `backend/app/modules/identity/ports.py`. `lock_for_result_publication` делает `SELECT ... FOR UPDATE` и проверяет статус `published`. Затем Б2 публикует результаты и вызывает `complete_competition` с тем же `Session` в одной транзакции. Б1 проверяет переход `published -> completed`; Б2 отвечает за атомарность. Б2 не обновляет таблицу `competitions` напрямую. Чтение данных спортсменов для рейтинга идёт через `IdentityPort` без N+1 запросов. В FastAPI статические маршруты `/results/drafts` и `/results/publish` регистрируются до параметризованного `/results/{registrationId}`.
