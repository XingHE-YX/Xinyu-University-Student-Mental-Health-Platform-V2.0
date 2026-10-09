"""Argon2id PHC encoding backed by argon2-cffi."""

from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError

from app.infra.config.types import PasswordConfig
from app.infra.logger.common import traced


def _hasher(config: PasswordConfig) -> PasswordHasher:
    return PasswordHasher(
        memory_cost=config.memory_cost_kib,
        time_cost=config.time_cost,
        parallelism=config.parallelism,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )


@traced
def hash_password(password: str, config: PasswordConfig) -> str:
    if not password or len(password.encode("utf-8")) > 4096:
        raise ValueError("password must contain 1 to 4096 UTF-8 bytes")
    return _hasher(config).hash(password)


@traced
def verify_password(password: str, encoded_hash: str, config: PasswordConfig) -> bool:
    if len(encoded_hash) > 512:
        return False
    try:
        params = extract_parameters(encoded_hash)
        if (
            params.type is not Type.ID
            or params.version != 19
            or not 19456 <= params.memory_cost <= config.memory_cost_kib
            or not 1 <= params.time_cost <= config.time_cost
            or not 1 <= params.parallelism <= config.parallelism
            or not 16 <= params.salt_len <= 64
            or not 16 <= params.hash_len <= 64
        ):
            return False
        return _hasher(config).verify(encoded_hash, password)
    except InvalidHashError, VerificationError, ValueError:
        return False


@traced
def needs_rehash(encoded_hash: str, config: PasswordConfig) -> bool:
    try:
        return _hasher(config).check_needs_rehash(encoded_hash)
    except InvalidHashError, ValueError:
        return True
