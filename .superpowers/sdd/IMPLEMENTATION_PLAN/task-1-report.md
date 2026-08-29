# Task 1 Report: Phase 3.1 Collections, Indexes, and Seed Data

## Changed Files

- `backend/app/domain/models.py`
- `backend/app/repositories/collection_registry.py`
- `backend/scripts/__init__.py`
- `backend/scripts/create_indexes.py`
- `backend/scripts/seed_demo.py`
- `backend/tests/test_domain_data.py`

## TDD Evidence

### Red

Command:

```bash
PYTHONPATH=backend/.packages:backend /Users/xingheluqi/.local/bin/python3.11 -m pytest backend/tests/test_domain_data.py -q
```

Observed failure before implementation:

- `5 failed in 0.38s`
- Missing implementation errors for:
  - `app.repositories.collection_registry`
  - `app.domain.models`
  - `scripts.seed_demo`
  - `scripts.create_indexes`

### Green

Focused command after minimal implementation:

```bash
PYTHONPATH=backend/.packages:backend /Users/xingheluqi/.local/bin/python3.11 -m pytest backend/tests/test_domain_data.py -q
```

Observed result:

- `5 passed in 0.05s`

## Full Verification

Commands run:

```bash
PYTHONPATH=backend/.packages:backend /Users/xingheluqi/.local/bin/python3.11 -m pytest backend/tests -q
cd backend && PYTHONPATH=.packages:. /Users/xingheluqi/.local/bin/python3.11 -m ruff check app tests scripts
cd backend && PYTHONPATH=.packages:. /Users/xingheluqi/.local/bin/python3.11 -m ruff format --check app tests scripts
cd backend && PYTHONPATH=.packages:. /Users/xingheluqi/.local/bin/python3.11 -m mypy app tests
```

Observed results:

- `35 passed in 0.45s`
- `ruff check`: `All checks passed!`
- `ruff format --check`: `46 files already formatted`
- `mypy`: `Success: no issues found in 43 source files`

## Notes

- Verification used a local dependency target at `backend/.packages` because the worktree did not have a working backend virtual environment. That directory was used only for running checks and is not part of the intended code change set.

## Concerns

- The task brief says “23 collections”, but `BACKEND_STRUCTURE.md` and `IMPLEMENTATION_PLAN.md` enumerate 24 fixed collections when `ai_assist_snapshots` is included. The implementation follows the 24-collection contract.
- `BACKEND_STRUCTURE.md` index table lists `auth_sessions` index field `expires_at`, but the collection schema only defines `access_expires_at` and `refresh_expires_at`. The registry currently preserves the literal contract index name for traceability; this contract mismatch should be clarified before deployment wiring.
