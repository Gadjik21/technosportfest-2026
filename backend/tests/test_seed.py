import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")

import pytest

from app.seed import seed_organizer


def test_seed_rejects_organizer_email_that_cannot_log_in(monkeypatch):
    monkeypatch.setattr("app.seed.getpass.getpass", lambda _: pytest.fail("Password must not be requested for an invalid email"))
    with pytest.raises(SystemExit, match="valid organizer email"):
        seed_organizer(object(), "organizer@example.test")
