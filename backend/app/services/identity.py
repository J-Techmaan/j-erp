from functools import lru_cache
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

password_hasher = PasswordHasher()


@lru_cache(maxsize=1)
def dummy_password_hash():
    # An unknown account still performs the same expensive password verification.
    return password_hasher.hash(secrets.token_urlsafe(32))


def verify_password(stored_hash: str | None, password: str):
    try:
        password_hasher.verify(stored_hash or dummy_password_hash(), password)
        return stored_hash is not None
    except (VerificationError, InvalidHashError):
        return False
