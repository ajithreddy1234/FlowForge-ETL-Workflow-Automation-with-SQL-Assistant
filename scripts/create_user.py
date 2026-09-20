import argparse
import getpass

from sqlalchemy.exc import IntegrityError

from api.database import SessionLocal, User, app_now, hash_password


def main():
    parser = argparse.ArgumentParser(description="Create an ETL Pipeline Builder user")
    parser.add_argument("login_id")
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--role", choices=("admin", "user"), default="user")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")

    db = SessionLocal()
    try:
        user = User(
            login_id=args.login_id.strip(),
            display_name=args.display_name.strip(),
            role=args.role,
            is_active=True,
            password_hash=hash_password(password),
            created_at=app_now(),
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise SystemExit(f"Login ID already exists: {args.login_id}") from exc
        print(f"Created {args.role} user {args.login_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
