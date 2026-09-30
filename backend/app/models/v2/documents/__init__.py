from .account import AdminAccountDocument, AuthSessionDocument, UserAccountDocument
from .ai import AIAssistSnapshotDocument
from .assessment import (
    AssessmentAnswerModel,
    AssessmentModuleDocument,
    AssessmentQuestionnaireDocument,
    AssessmentResultDocument,
    AssessmentSessionDocument,
    QuestionnaireQuestionModel,
    QuestionOptionModel,
)
from .audit import AuditEventDocument
from .common import (
    DocumentModel,
    FixedVersionOne,
    LocalDateString,
    NonEmptyString,
    NonNegativeInt,
    VersionInt,
)
from .consent import ConsentEventDocument
from .demo import DemoResetRunDocument
from .idempotency import IdempotencyRecordDocument
from .identity import (
    AnonymousIdentityDocument,
    IdentityAccessRequestDocument,
    IdentityRecordDocument,
)
from .mood import DailyMoodRecordDocument
from .quote import QuoteEntryDocument
from .support_resource import SupportResourceDocument
from .tasks import (
    ContentReviewTaskDocument,
    FollowupRecordDocument,
    SafetySupportTaskDocument,
    SupportResourceSnapshotModel,
    WorkTaskDocument,
)
from .treehole import TreeholePostDocument, TreeholeResponseDocument

COLLECTION_MODELS: dict[str, type[DocumentModel]] = {
    "user_accounts": UserAccountDocument,
    "auth_sessions": AuthSessionDocument,
    "identity_records": IdentityRecordDocument,
    "consent_records": ConsentEventDocument,
    "anonymous_identities": AnonymousIdentityDocument,
    "daily_mood_records": DailyMoodRecordDocument,
    "assessment_modules": AssessmentModuleDocument,
    "assessment_questionnaires": AssessmentQuestionnaireDocument,
    "assessment_sessions": AssessmentSessionDocument,
    "assessment_results": AssessmentResultDocument,
    "ai_assist_snapshots": AIAssistSnapshotDocument,
    "support_resources": SupportResourceDocument,
    "quote_entries": QuoteEntryDocument,
    "treehole_posts": TreeholePostDocument,
    "treehole_responses": TreeholeResponseDocument,
    "work_tasks": WorkTaskDocument,
    "content_review_tasks": ContentReviewTaskDocument,
    "safety_support_tasks": SafetySupportTaskDocument,
    "identity_access_requests": IdentityAccessRequestDocument,
    "followup_records": FollowupRecordDocument,
    "admin_accounts": AdminAccountDocument,
    "audit_events": AuditEventDocument,
    "idempotency_records": IdempotencyRecordDocument,
    "demo_reset_runs": DemoResetRunDocument,
}

__all__ = [
    "AIAssistSnapshotDocument",
    "AdminAccountDocument",
    "AnonymousIdentityDocument",
    "AssessmentAnswerModel",
    "AssessmentModuleDocument",
    "AssessmentQuestionnaireDocument",
    "AssessmentResultDocument",
    "AssessmentSessionDocument",
    "AuditEventDocument",
    "AuthSessionDocument",
    "COLLECTION_MODELS",
    "ConsentEventDocument",
    "ContentReviewTaskDocument",
    "DailyMoodRecordDocument",
    "DemoResetRunDocument",
    "DocumentModel",
    "FixedVersionOne",
    "FollowupRecordDocument",
    "IdempotencyRecordDocument",
    "IdentityAccessRequestDocument",
    "IdentityRecordDocument",
    "LocalDateString",
    "NonEmptyString",
    "NonNegativeInt",
    "QuestionOptionModel",
    "QuestionnaireQuestionModel",
    "QuoteEntryDocument",
    "SafetySupportTaskDocument",
    "SupportResourceDocument",
    "SupportResourceSnapshotModel",
    "TreeholePostDocument",
    "TreeholeResponseDocument",
    "UserAccountDocument",
    "VersionInt",
    "WorkTaskDocument",
]
