Владелец Б2. Новости и ссылки на документы. Загрузки файлов в MVP нет.

Контракт не ограничивает роль для создания/правки явно (нет `description` у `createNews`/`updateNews`/`createDocument`/`updateDocument`); реализация требует `organizer`, как и остальные административные действия. Если продакт решит иначе — поменять `require_role("organizer")` на `get_current_principal` в `router.py`.
