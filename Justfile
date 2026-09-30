set shell := ["bash", "-euo", "pipefail", "-c"]
set positional-arguments

# List available commands.
default:
    @just --list

# Create the backend virtual environment without installing dependencies.
venv:
    uv venv --project backend backend/.venv

# Create or sync the backend environment, including development dependencies.
init:
    uv sync --project backend --locked

# Start a development service: backend or admin.
run target:
    #!/usr/bin/env bash
    set -euo pipefail
    case "$1" in
      backend)
        exec uv run --directory backend --locked python -m uvicorn app.main:app \
          --reload --host "${BACKEND_HOST:-127.0.0.1}" --port "${BACKEND_PORT:-9000}"
        ;;
      admin) exec npm --prefix admin run dev ;;
      *) printf 'Unknown service: %s (expected backend or admin)\n' "$1" >&2; exit 2 ;;
    esac

# Check backend lint, formatting and types.
check target="backend":
    #!/usr/bin/env bash
    set -euo pipefail
    case "$1" in
      backend)
        uv run --directory backend --locked ruff check .
        uv run --directory backend --locked ruff format --check .
        uv run --directory backend --locked mypy
        ;;
      *) printf 'Unknown check target: %s (expected backend)\n' "$1" >&2; exit 2 ;;
    esac

# Run the backend test suite.
test target="backend":
    #!/usr/bin/env bash
    set -euo pipefail
    case "$1" in
      backend) exec uv run --directory backend --locked python -m pytest ;;
      *) printf 'Unknown test target: %s (expected backend)\n' "$1" >&2; exit 2 ;;
    esac
