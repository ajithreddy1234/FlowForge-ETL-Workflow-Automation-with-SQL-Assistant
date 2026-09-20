import hashlib

from api.database import hash_password, verify_password
from src.config import PASSWORD_PEPPER


def test_new_passwords_use_argon2id():
    encoded = hash_password("correct horse battery staple")

    assert encoded.startswith("argon2id$$argon2id$")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_legacy_pbkdf2_passwords_remain_verifiable_for_login_upgrade():
    password = "legacy-password"
    salt = "0123456789abcdef0123456789abcdef"
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        f"{PASSWORD_PEPPER}:{password}".encode("utf-8"),
        salt.encode("utf-8"),
        120_000,
    ).hex()

    assert verify_password(password, f"pbkdf2_sha256${salt}${digest}")
    assert not verify_password("wrong password", f"pbkdf2_sha256${salt}${digest}")
