#!/usr/bin/env python3
"""Create a local backend/.env with a fresh JWT secret; never overwrite it."""

from pathlib import Path
from secrets import token_urlsafe

root = Path(__file__).resolve().parents[1]
target = root / "backend/.env"
if target.exists():
    print("backend/.env already exists")
else:
    template = (root / "backend/.env.example").read_text()
    target.write_text(template.replace("replace-with-a-random-secret-at-least-32-characters", token_urlsafe(48)))
    target.chmod(0o600)
    print("Created backend/.env with a random local JWT secret")
