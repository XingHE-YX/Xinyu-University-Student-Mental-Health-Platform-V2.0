"""Loopback-only documentation environment using the real application services.

Only the external WeChat and school identity boundaries are replaced by local,
synthetic adapters. No production environment or external AI endpoint is used.
"""
from __future__ import annotations

import json
import secrets
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))

import uvicorn
from pydantic import SecretStr
from app.config.environments import EnvironmentKind
from app.config.settings import Settings
from app.domain.assessment_rules import build_seed_documents
from app.domain.models import QuoteEntryDocument, SupportResourceDocument, TreeholePostDocument
from app.integrations.school_identity import SchoolIdentityVerificationResult
from app.integrations.wechat_auth import WechatIdentity
from app.main import create_app
from app.repositories.domain_data_repository import InMemoryDomainDataRepository
from app.security.passwords import hash_password
from scripts.seed_demo import build_demo_seed_bundle


class LocalWechatIdentity:
    async def exchange_code(self, code: str) -> WechatIdentity:
        subject = 'manual-smoke-student' if code == 'manual-smoke' else 'manual-screenshot-student'
        return WechatIdentity(subject_id=subject)


class LocalSchoolIdentity:
    async def verify_student(self, *, student_name: str, student_number: str):
        if student_name == '演示同学' and student_number == 'DEMO20260916':
            return SchoolIdentityVerificationResult(status='verified', provider_reference='local-synthetic-student')
        return SchoolIdentityVerificationResult(status='failed', failed_reason_code='DEMO_DATA_MISMATCH')


settings = Settings(
    environment_kind=EnvironmentKind.DEMO,
    declared_environment_kind=EnvironmentKind.DEMO,
    configuration_status='ready',
    cloudbase_env_id='local-manual-demo',
    demo_env_ids=('local-manual-demo',),
    demo_mode=True,
    demo_reset_allowed=True,
    admin_password_hash=SecretStr(hash_password('LocalManual-2026!')),
    admin_session_secret=SecretStr(secrets.token_urlsafe(48)),
    support_resource_version='support-v1',
)
seed = build_demo_seed_bundle(EnvironmentKind.DEMO)['collections']
rules = build_seed_documents()
now = datetime.now(UTC)
posts = []
for i, body in enumerate([
    '今天把拖了几天的小任务完成了。给自己留一点休息的时间，明天再继续。',
    '最近课程安排比较满，散步时听到风吹过树叶，感觉放松了一些。',
], 1):
    posts.append(TreeholePostDocument(
        _id=f'manual-public-post-{i}', author_user_id=f'synthetic-author-{i}',
        anonymous_identity_id=f'synthetic-anonymous-{i}',
        display_name_snapshot=['一片云', '晚风'][i - 1],
        body_original_ciphertext='synthetic-demo-content', body_sanitized=body,
        body_hash=f'synthetic-body-{i}', visibility_state='published',
        review_state='decided', safety_state='not_triggered',
        community_consent_version='community-v1', created_at=now, updated_at=now, version=1,
    ))
repository = InMemoryDomainDataRepository(
    assessment_modules=rules['assessment_modules'],
    assessment_questionnaires=rules['assessment_questionnaires'],
    quote_entries=[QuoteEntryDocument.model_validate(q) for q in seed['quote_entries']],
    support_resources=[SupportResourceDocument.model_validate(r) for r in seed['support_resources']],
    treehole_posts=posts,
)
app = create_app(settings, wechat_client=LocalWechatIdentity(), domain_repository=repository)
app.state.identity_service.school = LocalSchoolIdentity()

if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=9000, access_log=True)
