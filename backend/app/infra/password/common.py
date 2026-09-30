"""Async password operations with bounded CPU and memory consumption."""

from functools import partial

import anyio

from app.infra.config.types import PasswordConfig
from app.infra.logger.common import traced
from app.infra.password.algorithm import argon2id, pbkdf2_sha256


class PasswordManager:
    def __init__(self, config: PasswordConfig | None = None) -> None:
        self.config = config or PasswordConfig()
        self._limiter = anyio.CapacityLimiter(self.config.max_concurrency)

    @traced
    async def hash(self, password: str) -> str:
        return await anyio.to_thread.run_sync(
            partial(argon2id.hash_password, password, self.config), limiter=self._limiter
        )

    @traced
    async def verify(self, password: str, encoded_hash: str) -> bool:
        if not password or len(password.encode("utf-8")) > 4096:
            return False
        verifier = (
            argon2id.verify_password
            if encoded_hash.startswith("$argon2id$")
            else pbkdf2_sha256.verify_password
        )
        return await anyio.to_thread.run_sync(
            partial(verifier, password, encoded_hash, self.config), limiter=self._limiter
        )

    @traced
    def needs_rehash(self, encoded_hash: str) -> bool:
        return argon2id.needs_rehash(encoded_hash, self.config)


_passwords = PasswordManager()
hash_password = _passwords.hash
verify_password = _passwords.verify
needs_rehash = _passwords.needs_rehash
