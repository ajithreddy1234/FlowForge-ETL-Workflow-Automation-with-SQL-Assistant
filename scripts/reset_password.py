import argparse
import getpass

from api.database import SessionLocal, User, UserSession, hash_password


def main():
    parser = argparse.ArgumentParser(
        description="Reset an ETL Pipeline Builder user's password"
    )
    parser.add_argument("login_id")
    args = parser.parse_args()

    password = getpass.getpass("New password: ")
    confirmation = getpass.getpass("Confirm new password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if len(password) < 12:
        raise SystemExit("Password must contain at least 12 characters")

    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .filter(User.login_id == args.login_id.strip())
            .first()
        )
        if not user:
            raise SystemExit(f"Login ID does not exist: {args.login_id}")

        user.password_hash = hash_password(password)
        db.query(UserSession).filter(UserSession.user_id == user.id).delete(
            synchronize_session=False
        )
        db.commit()
        print(f"Password reset for {user.login_id}; existing sessions revoked")
    finally:
        db.close()


if __name__ == "__main__":
    main()
