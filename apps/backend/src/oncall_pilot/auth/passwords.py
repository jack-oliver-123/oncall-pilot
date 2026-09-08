"""密码计算边界；实例仅在显式初始化时创建。"""

import secrets

from pwdlib import PasswordHash


class PasswordManager:
    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()
        self._dummy_hash = self._hasher.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password: str, encoded: str | None) -> bool:
        valid = self._hasher.verify(password, encoded if encoded is not None else self._dummy_hash)
        return valid and encoded is not None
