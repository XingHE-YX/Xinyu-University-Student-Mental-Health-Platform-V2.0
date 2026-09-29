"""Environment classification and isolation checks for the backend."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class EnvironmentKind(StrEnum):
    DEMO = "demo"
    AUTHORIZED = "authorized"
    UNCONFIGURED = "unconfigured"


class ConfigurationError(RuntimeError):
    """Base error for an unsafe or incomplete deployment configuration."""


class EnvironmentMismatchError(ConfigurationError):
    """Raised when a known environment is paired with the wrong mode."""


@dataclass(frozen=True, slots=True)
class EnvironmentDecision:
    """The result of comparing the declared mode and the environment registry."""

    declared_kind: EnvironmentKind
    matched_kind: EnvironmentKind


def parse_demo_mode(value: str | None) -> bool | None:
    """Parse the explicit deployment switch without accepting ambiguous values."""

    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1"}:
        return True
    if normalized in {"false", "0"}:
        return False
    raise ConfigurationError("DEMO_MODE must be true or false")


def resolve_environment(
    *,
    demo_mode: bool | None,
    cloudbase_env_id: str | None,
    demo_env_ids: Iterable[str] = (),
    authorized_env_ids: Iterable[str] = (),
) -> EnvironmentDecision:
    """Resolve a mode only when the CloudBase environment is explicitly registered.

    An unknown or incomplete registry never becomes a usable environment. A known
    opposite-mode pairing raises so a real environment cannot be disguised as demo.
    """

    demo_ids = frozenset(item.strip() for item in demo_env_ids if item.strip())
    authorized_ids = frozenset(item.strip() for item in authorized_env_ids if item.strip())
    if demo_ids & authorized_ids:
        raise ConfigurationError("CloudBase environment IDs cannot overlap between modes")

    declared_kind = (
        EnvironmentKind.DEMO
        if demo_mode is True
        else EnvironmentKind.AUTHORIZED
        if demo_mode is False
        else EnvironmentKind.UNCONFIGURED
    )
    if not cloudbase_env_id or demo_mode is None:
        return EnvironmentDecision(declared_kind, EnvironmentKind.UNCONFIGURED)

    normalized_env_id = cloudbase_env_id.strip()
    if demo_mode is True:
        if normalized_env_id in authorized_ids:
            raise EnvironmentMismatchError(
                "DEMO_MODE cannot target an authorized CloudBase environment"
            )
        matched_kind = (
            EnvironmentKind.DEMO if normalized_env_id in demo_ids else EnvironmentKind.UNCONFIGURED
        )
    else:
        if normalized_env_id in demo_ids:
            raise EnvironmentMismatchError(
                "authorized mode cannot target a demo CloudBase environment"
            )
        matched_kind = (
            EnvironmentKind.AUTHORIZED
            if normalized_env_id in authorized_ids
            else EnvironmentKind.UNCONFIGURED
        )
    return EnvironmentDecision(declared_kind, matched_kind)
