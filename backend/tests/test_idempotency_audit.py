from datetime import UTC, datetime

import pytest

from app.audit.writer import AuditWriter
from app.repositories.audit_repository import InMemoryAuditRepository
from app.repositories.idempotency_repository import InMemoryIdempotencyRepository
from app.schemas.errors import ApiException
from app.services.idempotency_service import IdempotencyService


def test_same_idempotency_request_is_replayed_without_a_second_reservation() -> None:
    repository = InMemoryIdempotencyRepository()
    service = IdempotencyService(repository)

    first = service.begin("student", "student-1", "/treehole/posts", "post-1", {"body": "x"})
    service.complete(first, status_code=201, response_digest="digest-1")
    replay = service.begin("student", "student-1", "/treehole/posts", "post-1", {"body": "x"})

    assert replay.replayed is True
    assert replay.record.response_digest == "digest-1"


def test_completed_idempotency_record_is_terminal() -> None:
    repository = InMemoryIdempotencyRepository()
    service = IdempotencyService(repository)

    first = service.begin("student", "student-1", "/treehole/posts", "post-1", {"body": "x"})
    completed = service.complete(first, status_code=201, response_digest="digest-success")
    repeated = service.complete(
        first,
        status_code=500,
        response_digest="digest-failure",
        outcome="failure",
    )

    assert repeated == completed
    assert repeated.outcome == "success"
    assert repeated.response_status == 201
    assert repeated.response_digest == "digest-success"


def test_same_idempotency_key_with_a_different_body_is_a_conflict() -> None:
    repository = InMemoryIdempotencyRepository()
    service = IdempotencyService(repository)

    service.begin("student", "student-1", "/treehole/posts", "post-1", {"body": "x"})

    with pytest.raises(ApiException) as error:
        service.begin("student", "student-1", "/treehole/posts", "post-1", {"body": "y"})

    assert error.value.status_code == 409
    assert error.value.code == "IDEMPOTENCY_CONFLICT"


def test_duplicate_click_while_the_first_request_is_processing_is_retryable() -> None:
    repository = InMemoryIdempotencyRepository()
    service = IdempotencyService(repository)
    service.begin("student", "student-1", "/assessment/complete", "complete-1", {"answers": []})

    with pytest.raises(ApiException) as error:
        service.begin("student", "student-1", "/assessment/complete", "complete-1", {"answers": []})

    assert error.value.status_code == 409
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    assert error.value.retryable is True


def test_missing_idempotency_key_is_rejected_before_mutation() -> None:
    service = IdempotencyService(InMemoryIdempotencyRepository())

    with pytest.raises(ApiException) as error:
        service.begin("admin", "admin-1", "/admin/tasks/1/decision", "", {"action": "complete"})

    assert error.value.status_code == 400
    assert error.value.code == "INVALID_REQUEST"


def test_audit_writer_keeps_minimal_facts_and_drops_sensitive_raw_fields() -> None:
    repository = InMemoryAuditRepository()
    writer = AuditWriter(repository, environment_id="demo-env")

    event = writer.write(
        request_id="req_1",
        actor_type="admin",
        actor_id="admin-1",
        capability="super_admin",
        action="task_decision",
        resource_type="content_review_task",
        resource_id="task-1",
        data_scope="necessary_facts",
        outcome="success",
        reason_code="publish",
        occurred_at=datetime(2026, 8, 29, tzinfo=UTC),
        facts={
            "object_version": 2,
            "action_code": "publish",
            "body": "完整树洞正文",
            "answers": [1, 2, 3],
            "student_name": "真实姓名",
            "student_number": "20260001",
            "safety_confirmation": "原始确认文本",
        },
    )

    assert event.details == {"object_version": 2, "action_code": "publish"}
    assert "完整树洞正文" not in str(event)
    assert "真实姓名" not in str(event)
    assert "20260001" not in str(event)
    assert "原始确认文本" not in str(event)
