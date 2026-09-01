# Task 5 Report - Stage 3.5 Backend Domain/Data Layer

## Implemented

- Added `QuoteService` for one-per-call local quote selection from enabled repository entries only.
- Added `MoodService` for gated same-day Asia/Shanghai mood recording, idempotent replay, history, and single-record delete with version checks.
- Added `SupportResourceService` for narrow environment-scoped normal/safety resource projections and explicit unconfigured/empty states.
- Added `TodayService` for the minimal student projection: quote, today's mood, three fixed assessment shortcuts, and ordinary support entry.
- Extended `InMemoryDomainDataRepository` with typed daily mood, quote, and user assessment-result read/write helpers while preserving transaction snapshot rollback and version conventions.
- Tightened `DailyMoodRecordDocument.mood_code` to the six stable codes: `pleasant`, `calm`, `tired`, `anxious`, `low`, `irritable`.
- Added behavior tests covering gates, projections, mood uniqueness/idempotency/deletion/history, quote filtering, resource ordering/isolation/statuses, and no task/AI/network side effects.

## Files

- `backend/app/domain/models.py`
- `backend/app/repositories/domain_data_repository.py`
- `backend/app/services/mood_service.py`
- `backend/app/services/quote_service.py`
- `backend/app/services/support_resource_service.py`
- `backend/app/services/today_service.py`
- `backend/tests/test_today_domain_services.py`
- `.superpowers/sdd/IMPLEMENTATION_PLAN/task-5-report.md`

## TDD RED

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_today_domain_services.py -q
```

Output:

```text
ERROR backend/tests/test_today_domain_services.py
ModuleNotFoundError: No module named 'app.services.mood_service'
```

The failure was expected because the behavior tests referenced the new task services before implementation.

## GREEN

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_today_domain_services.py -q
```

Output:

```text
......                                                                   [100%]
6 passed in 0.08s
```

## Verification

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests -q
```

Output:

```text
140 passed in 0.58s
```

Command:

```bash
cd backend && .venv/bin/python -m ruff check app tests
```

Output:

```text
All checks passed!
```

Command:

```bash
cd backend && .venv/bin/python -m mypy app tests
```

Output:

```text
Success: no issues found in 63 source files
```

Command:

```bash
git diff --check
```

Output: no whitespace errors.

## Self Review

- Today projection excludes names, student numbers, anonymous IDs, task payloads, scores, answers, and safety details.
- Mood recording accepts only the six stable codes and only the injectable Asia/Shanghai current date.
- Same-day mood submissions return the original `user_id + record_date` fact and do not overwrite, duplicate, create tasks, or release the unique slot after deletion.
- Quote service reads only repository entries with enabled public-domain/project-original rights and date-window eligibility; it has no network, AI, mood, assessment, safety, or identity dependency.
- Support resources are scoped to `Settings.environment_kind`, ordered differently for normal/safety contexts, and preserve configured action targets without inventing contacts, numbers, URLs, or commitments.
- Audit calls use the existing safe-detail allowlist and do not include mood code, identity fields, task details, resource documents, answers, or scores.

## Concerns

- No student HTTP routes were added by design; stage 4 must wire these service projections into API/front-end surfaces.
- Authorized-environment production resources still depend on real configuration documents being loaded; the service returns `empty` or `unconfigured` rather than fallback placeholders when absent.

## Fix Round 1/5

### Review finding

`MoodService.delete_mood()` did not treat an already logically deleted mood record as terminal. A second request using the first delete's returned version reached `save_daily_mood_record()`, rewrote `deleted_at`, incremented the version, and emitted another success audit event.

### TDD RED

Added `test_mood_delete_rejects_already_deleted_record_without_mutation_or_second_audit` to `backend/tests/test_today_domain_services.py`. The test uses the real in-memory repository, mood service, token/session path, and audit repository. It deletes once, retries with the returned version, and checks `NOT_FOUND`/404, unchanged version and deletion timestamp, and an unchanged single delete audit.

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_today_domain_services.py -q
```

Output:

```text
...F...                                                                  [100%]
1 failed, 6 passed in 0.07s
Failed: DID NOT RAISE <class 'app.schemas.errors.ApiException'>
```

### Minimal fix and GREEN

Added a post-version-check `deleted_at` guard in `MoodService.delete_mood()`. It returns the existing stable hidden-resource error (`NOT_FOUND`, HTTP 404) before calling the repository save or success audit path. Stale versions continue to return `VERSION_CONFLICT` first.

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_today_domain_services.py -q
```

Output:

```text
.......                                                                  [100%]
7 passed in 0.09s
```

### Verification

```bash
backend/.venv/bin/python -m pytest backend/tests -q
```

```text
141 passed in 0.54s
```

```bash
backend/.venv/bin/python -m ruff check backend/app backend/tests
```

```text
All checks passed!
```

```bash
backend/.venv/bin/python -m mypy backend/app backend/tests
```

```text
Success: no issues found in 63 source files
```

```bash
git diff --check
```

Output: no whitespace errors.

### Self-review

- The new behavior is tested through the public service operation with real persistence and audit side effects; no mocks were introduced.
- The version comparison remains before the tombstone check, preserving the existing stale-version contract.
- The terminal check runs inside the repository transaction and before `save_daily_mood_record()`, so the second request cannot mutate version/timestamps or create a second success audit.
- The deferred date-format minor was not changed.

## Scoped Re-review

- Verdict: `APPROVED`.
- The repeated-deletion finding was `ADDRESSED`: the post-version-check tombstone guard returns `NOT_FOUND` before persistence and success-audit side effects.
- The reviewer found no new Critical, Important, or Minor findings in the fix diff and did not request additional code changes.
- The history `from_date`/`to_date` format-validation item remains a deferred Minor for a later hardening pass.

## Completion

The 3.5 backend domain/data scope is complete. The four services and their repository/model support cover the static daily quote pool, six-code daily mood fact with terminal single deletion, context-ordered support resources, and the minimal gated today projection. No student HTTP or treehole behavior was added because those integrations are outside the 3.5 file list and belong to the later application/API stage.
