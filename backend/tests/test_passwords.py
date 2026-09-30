import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.infra.database.memory.session import InMemorySessionRepository
from app.infra.password.common import PasswordManager
from app.main import create_app
from tests.password_fixtures import ADMIN_HASH, LEGACY_HASH
from tests.test_auth_api import configured_settings


async def test_argon2id_generation_and_legacy_verification() -> None:
    passwords = PasswordManager()
    hashed = await passwords.hash("a-new-password")
    assert hashed.startswith("$argon2id$")
    assert await passwords.verify("a-new-password", hashed)
    assert not await passwords.verify("wrong", hashed)
    assert await passwords.verify("correct-password", LEGACY_HASH)
    assert not await passwords.verify("wrong", LEGACY_HASH)
    assert passwords.needs_rehash(LEGACY_HASH)
    assert not passwords.needs_rehash(hashed)


@pytest.mark.parametrize(
    "encoded",
    [
        "",
        "garbage",
        "pbkdf2_sha256$999999999999999999$a$b",
        "pbkdf2_sha256$310000$%%%$%%%",
        ADMIN_HASH.replace("m=65536", "m=99999999"),
        ADMIN_HASH.replace("t=3", "t=999"),
        ADMIN_HASH.replace("argon2id", "argon2i"),
    ],
)
async def test_malformed_or_excessive_cost_hashes_are_rejected(encoded: str) -> None:
    assert not await PasswordManager().verify("correct-password", encoded)


async def test_password_worker_does_not_block_event_loop() -> None:
    passwords = PasswordManager()
    task = asyncio.create_task(passwords.hash("a-new-password"))
    await asyncio.sleep(0.01)
    assert not task.done()
    await task


def test_existing_pbkdf2_admin_can_still_login() -> None:
    settings = configured_settings().model_copy(
        update={"admin_password_hash": SecretStr(LEGACY_HASH)}
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/admin/auth/login",
            json={
                "login_name": "心理健康中心工作人员",
                "password": "correct-password",
            },
        )
    assert response.status_code == 200


def test_password_redeployment_invalidates_existing_admin_sessions() -> None:
    sessions = InMemorySessionRepository()
    settings = configured_settings().model_copy(
        update={"admin_password_hash": SecretStr(LEGACY_HASH)}
    )
    with TestClient(create_app(settings, session_repository=sessions)) as client:
        login = client.post(
            "/api/v1/admin/auth/login",
            json={
                "login_name": "心理健康中心工作人员",
                "password": "correct-password",
            },
        ).json()["data"]
    with TestClient(create_app(configured_settings(), session_repository=sessions)) as client:
        me = client.get(
            "/api/v1/admin/me",
            headers={
                "Authorization": f"Bearer {login['access_token']}",
            },
        )
        refresh = client.post(
            "/api/v1/admin/auth/refresh",
            json={
                "refresh_token": login["refresh_token"],
            },
        )
    assert me.status_code == refresh.status_code == 401
