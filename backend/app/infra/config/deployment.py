"""Validation helpers for CloudBase deployment-time configuration.

The validator intentionally accepts mappings (rather than reading the process
environment) so CI and deployment operators can validate a rendered template
without ever printing secret values.
"""

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class DeploymentValidation:
    """Safe validation result; values and secrets are never included."""

    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


_REQUIRED = (
    "CLOUDBASE_ENV_ID_DEMO",
    "CLOUDBASE_ENV_ID_AUTHORIZED",
    "DEMO_NAMESPACE",
    "AUTHORIZED_NAMESPACE",
    "ADMIN_WEB_ORIGIN_DEMO",
    "ADMIN_WEB_ORIGIN_AUTHORIZED",
)


def validate_deployment_config(values: dict[str, str]) -> DeploymentValidation:
    """Check environment isolation and HTTPS origins without exposing secrets.

    Empty values and ``${...}`` placeholders are reported as incomplete, while
    all other values are treated as operator-provided and are never echoed.
    """

    errors: list[str] = []
    normalized = {key: (value or "").strip() for key, value in values.items()}
    for key in _REQUIRED:
        value = normalized.get(key, "")
        if not value or (value.startswith("${") and value.endswith("}")):
            errors.append(f"{key} is not configured")

    demo_env = normalized.get("CLOUDBASE_ENV_ID_DEMO", "")
    authorized_env = normalized.get("CLOUDBASE_ENV_ID_AUTHORIZED", "")
    if demo_env and authorized_env and demo_env == authorized_env:
        errors.append("CloudBase environment IDs must differ")

    demo_namespace = normalized.get("DEMO_NAMESPACE", "")
    authorized_namespace = normalized.get("AUTHORIZED_NAMESPACE", "")
    if demo_namespace and authorized_namespace and demo_namespace == authorized_namespace:
        errors.append("database namespaces must differ")

    for key in ("ADMIN_WEB_ORIGIN_DEMO", "ADMIN_WEB_ORIGIN_AUTHORIZED"):
        origin = normalized.get(key, "")
        if origin and not (origin.startswith("${") and origin.endswith("}")):
            parsed = urlparse(origin)
            if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/"):
                errors.append(f"{key} must be an HTTPS origin without a path")

    return DeploymentValidation(tuple(dict.fromkeys(errors)))
