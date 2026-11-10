import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import get_settings

_ph = PasswordHasher()  # Argon2id (padrão do argon2-cffi)
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _ph.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# Hash fictício para igualar o tempo de resposta quando o e-mail não existe
DUMMY_HASH = _ph.hash("senha-ficticia-para-timing")


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def create_access_token(user_id: int, role: str, csrf: str) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.access_token_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "csrf": csrf, "exp": exp}, s.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
