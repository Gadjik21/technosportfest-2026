"""Create an organizer without exposing an organizer registration endpoint."""

import argparse
import getpass

from sqlalchemy.exc import IntegrityError

from app.db import get_sessionmaker
from app.modules.identity.models import User
from app.modules.identity.security import password_hash


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an organizer account")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Organizer password (12+ characters): ")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")
    with get_sessionmaker()() as db:
        db.add(User(email=args.email.strip().lower(), password_hash=password_hash.hash(password), role="organizer"))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise SystemExit("Email is already registered")
    print("Organizer created")


if __name__ == "__main__":
    main()
