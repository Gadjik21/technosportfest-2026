import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("JWT_SECRET", "test-only-secret-with-at-least-32-characters")

import pytest

from app.seed import seed_master_admin


def test_seed_rejects_invalid_admin_email(monkeypatch):
    monkeypatch.setattr("app.seed.getpass.getpass", lambda _: pytest.fail("Password must not be requested for an invalid email"))
    with pytest.raises(SystemExit, match="valid admin email"):
        seed_master_admin(object(), "admin@example.test")
