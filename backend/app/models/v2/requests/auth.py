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
