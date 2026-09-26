"""Каталог прав динамических ролей.

Роль — это именованный набор прав вида `<раздел>.<действие>` (например,
`news.create`). Системные роли (`athlete`, `organizer`, `master-admin`)
создаются миграцией/сидом; остальные роли создаёт master admin через
`/admin/roles`. Права кладутся в JWT и проверяются dependency
`require_permission` на каждом запросе.
"""

ROLE_ATHLETE = "athlete"
ROLE_ORGANIZER = "organizer"
ROLE_MASTER_ADMIN = "master-admin"

#: Действия по разделам. Ключ — слаг раздела для API/контракта,
#: отображение в UI строит фронтенд по `GET /admin/permissions`.
PERMISSION_GROUPS: dict[str, list[str]] = {
    "news": ["news.view", "news.create", "news.edit", "news.delete"],
    "documents": ["documents.view", "documents.create", "documents.edit", "documents.delete"],
    "competitions": [
        "competitions.view",
        "competitions.create",
        "competitions.edit",
        "competitions.delete",
        "competitions.publish",
    ],
    "contests": ["contests.tasks", "contests.grade"],
    "results": ["results.view", "results.save", "results.publish"],
    "users": ["users.manage"],
    "roles": ["roles.manage"],
}

PERMISSION_LABELS: dict[str, str] = {
    "news": "Новости",
    "documents": "Документы",
    "competitions": "Соревнования",
    "contests": "Контест",
    "results": "Результаты",
    "users": "Пользователи",
    "roles": "Роли и права",
}

ALL_PERMISSIONS: list[str] = sorted({code for codes in PERMISSION_GROUPS.values() for code in codes})

#: Права системных ролей. Организатор получает весь функциональный набор
#: без управления ролями/пользователями; master admin — всё.
SYSTEM_ROLE_PERMISSIONS: dict[str, list[str]] = {
    ROLE_ATHLETE: [],
    ROLE_ORGANIZER: [code for code in ALL_PERMISSIONS if code not in {"users.manage", "roles.manage"}],
    ROLE_MASTER_ADMIN: ALL_PERMISSIONS,
}

SYSTEM_ROLE_DESCRIPTIONS: dict[str, str] = {
    ROLE_ATHLETE: "Спортсмен: заявки, профиль, решения, свои результаты.",
    ROLE_ORGANIZER: "Организатор: соревнования, контесты, результаты, новости и документы.",
    ROLE_MASTER_ADMIN: "Администратор платформы: полный доступ и управление ролями и пользователями.",
}


def validate_permissions(codes: list[str]) -> None:
    """Бросает ValueError, если в списке есть неизвестный код права."""
    unknown = [code for code in codes if code not in ALL_PERMISSIONS]
    if unknown:
        raise ValueError(f"Неизвестные права: {', '.join(sorted(set(unknown)))}")