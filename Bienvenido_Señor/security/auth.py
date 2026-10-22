from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from typing import Any

from security.user_levels import UserLevel, coerce_user_level


@dataclass(frozen=True)
class AuthSession:
    user: str
    level: UserLevel
    authenticated: bool

    def to_dict(self) -> dict[str, Any]:
        return {"user": self.user, "level": int(self.level), "authenticated": self.authenticated}


class AuthManager:
    """Autenticacion local ligera para elevar permisos en futuras herramientas."""

    def __init__(self, password_hash: str = "", *, default_level: int = 1) -> None:
        self.password_hash = str(password_hash or "")
        self.default_level = coerce_user_level(default_level)

    def anonymous(self) -> AuthSession:
        return AuthSession("local", self.default_level, False)

    def authenticate(self, password: str, *, requested_level: int = 2) -> AuthSession:
        if not self.password_hash:
            return AuthSession("local", self.default_level, False)
        digest = hashlib.sha256(str(password or "").encode("utf-8")).hexdigest()
        ok = hmac.compare_digest(digest, self.password_hash)
        return AuthSession("local", coerce_user_level(requested_level if ok else self.default_level), ok)

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.environ.get("VIERNES_AUTH_SALT", "")
        return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
