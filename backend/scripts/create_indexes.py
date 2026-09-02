"""Serialize deterministic collection index definitions for deployment."""

from __future__ import annotations

import json

from app.repositories.collection_registry import build_index_projection


def serialize_index_plan() -> dict[str, list[dict[str, object]]]:
    return build_index_projection()


def main() -> int:
    print(json.dumps(serialize_index_plan(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
