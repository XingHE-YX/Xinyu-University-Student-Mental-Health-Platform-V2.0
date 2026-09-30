from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class TokenData(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class StudentSessionData(TokenData):
    account_status: Literal["active", "recovery_pending", "stopped", "purged"]
    base_consent_status: Literal["required", "accepted"]
    community_consent_status: Literal["required", "accepted"]
    identity_status: Literal["unverified", "pending", "verified", "expired"]


class AdminSessionData(TokenData):
    display_name: str
    capability_label: str


class StudentMeData(BaseModel):
    subject_type: Literal["student"]
    subject_id: str
    account_status: Literal["active", "recovery_pending", "stopped", "purged"]


class AdminMeData(BaseModel):
    display_name: str
    capability_label: str
    session_expires_at: datetime
    environment_kind: str
