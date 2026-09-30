"""Read-only compatibility with the historical PBKDF2-SHA256 format."""

import base64
import binascii
import hashlib
import hmac

from app.infra.config.types import PasswordConfig
from app.infra.logger.common import traced


@traced
def verify_password(password: str, encoded_hash: str, config: PasswordConfig) -> bool:
    if len(encoded_hash) > 512:
        return False
    try:
        scheme, iteration_text, salt_text, digest_text = encoded_hash.split("$")
        if scheme != "pbkdf2_sha256" or not iteration_text.isascii():
            return False
        iterations = int(iteration_text)
        if not 100_000 <= iterations <= config.max_pbkdf2_iterations:
            return False
        salt = _decode(salt_text)
        expected = _decode(digest_text)
        if not 1 <= len(salt) <= 64 or len(expected) != 32:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual, expected)
    except AttributeError, ValueError, binascii.Error:
        return False


def _decode(value: str) -> bytes:
    return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
