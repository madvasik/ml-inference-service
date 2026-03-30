from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from ml_inference_service.config import get_settings

settings = get_settings()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(subject: str | int, extra_claims: dict[str, Any] | None = None) -> str:
    to_encode: dict[str, Any] = {"sub": str(subject)}
    if extra_claims:
        to_encode.update(extra_claims)
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def verify_token_subject(token: str) -> str:
    try:
        payload = decode_token(token)
        sub = payload.get("sub")
        if sub is None:
            raise JWTError("missing sub")
        return str(sub)
    except JWTError as e:
        raise ValueError("invalid token") from e
