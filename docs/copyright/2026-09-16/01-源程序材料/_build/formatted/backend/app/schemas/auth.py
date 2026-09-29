"""Request and response models for student and fixed-account admin sessions."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WechatSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=512)
    client_version: str = Field(min_length=1, max_length=64)


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1, max_length=512)


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


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
