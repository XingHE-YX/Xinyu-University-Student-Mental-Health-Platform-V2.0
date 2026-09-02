"""School identity adapter boundary for the identity domain."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import httpx
from httpx import AsyncBaseTransport


@dataclass(frozen=True, slots=True)
class SchoolIdentityVerificationResult:
    status: Literal["verified", "failed", "unavailable"]
    provider_reference: str | None = None
    failed_reason_code: str | None = None


class SchoolIdentityProvider(Protocol):
    async def verify_student(
        self,
        *,
        student_name: str,
        student_number: str,
    ) -> SchoolIdentityVerificationResult: ...


class UnavailableSchoolIdentityProvider:
    async def verify_student(
        self,
        *,
        student_name: str,
        student_number: str,
    ) -> SchoolIdentityVerificationResult:
        del student_name, student_number
        return SchoolIdentityVerificationResult(status="unavailable")


class HttpSchoolIdentityProvider:
    def __init__(
        self,
        *,
        provider_url: str | None,
        timeout: float = 5.0,
        transport: AsyncBaseTransport | None = None,
    ) -> None:
        self._provider_url = provider_url
        self._timeout = timeout
        self._transport = transport

    async def verify_student(
        self,
        *,
        student_name: str,
        student_number: str,
    ) -> SchoolIdentityVerificationResult:
        if not self._provider_url:
            return SchoolIdentityVerificationResult(status="unavailable")
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
            ) as client:
                response = await client.post(
                    self._provider_url,
                    json={
                        "student_name": student_name,
                        "student_number": student_number,
                    },
                )
                response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                return SchoolIdentityVerificationResult(status="unavailable")
            status = body.get("status")
            if status == "verified":
                provider_reference = body.get("provider_reference")
                if not isinstance(provider_reference, str) or not provider_reference:
                    return SchoolIdentityVerificationResult(status="unavailable")
                return SchoolIdentityVerificationResult(
                    status="verified",
                    provider_reference=provider_reference,
                )
            if status == "failed":
                failed_reason_code = body.get("failed_reason_code")
                normalized_reason = (
                    failed_reason_code
                    if isinstance(failed_reason_code, str) and failed_reason_code
                    else None
                )
                return SchoolIdentityVerificationResult(
                    status="failed",
                    failed_reason_code=normalized_reason,
                )
            return SchoolIdentityVerificationResult(status="unavailable")
        except Exception:
            return SchoolIdentityVerificationResult(status="unavailable")
