#!/usr/bin/env python3
"""Provision and seed a demo CloudBase environment without printing credentials."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.infra.config.settings import Settings
from app.infra.config.validation import EnvironmentKind
from app.infra.database.cloudbase.client import CloudBaseStore
from app.infra.database.collections import COLLECTIONS, build_index_projection
from app.infra.database.common import RepositoryVersionConflict
from scripts.seed_assessments import build_assessment_seed_bundle
from scripts.seed_demo import build_demo_seed_bundle


@dataclass(frozen=True, slots=True)
class InitializationReport:
    collections_created: int
    collections_existing: int
    indexes_applied: int
    documents_inserted: int
    documents_existing: int
    support_resources_refreshed: int


def read_environment(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if not separator or not key.strip():
            raise ValueError(f"invalid environment entry on line {number}")
        values[key.strip()] = value.strip()
    return values


def demo_seed_collections() -> dict[str, list[dict[str, Any]]]:
    basic = build_demo_seed_bundle(EnvironmentKind.DEMO)["collections"]
    assessments = build_assessment_seed_bundle(
        environment_kind=EnvironmentKind.DEMO, include_demo_records=True
    )["collections"]
    return {name: [*basic.get(name, []), *assessments.get(name, [])] for name in COLLECTIONS}


async def refresh_demo_support_resources(store: CloudBaseStore) -> int:
    """Update only the three known demo placeholders using optimistic versions."""
    resources = build_demo_seed_bundle(EnvironmentKind.DEMO)["collections"]["support_resources"]
    refreshed = 0
    for desired in resources:
        current = await store.query("support_resources", {"_id": desired["_id"]}, limit=1)
        if not current:
            raise RuntimeError(f"demo support resource is missing: {desired['_id']}")
        existing = current[0]
        if existing.get("environment_scope") != "demo":
            raise RuntimeError(f"refusing to update a non-demo resource: {desired['_id']}")
        managed = {
            key: value
            for key, value in desired.items()
            if key not in {"_id", "created_at", "updated_at", "version"}
        }
        if all(existing.get(key) == value for key, value in managed.items()):
            continue
        version = existing.get("version")
        if not isinstance(version, int):
            raise RuntimeError(f"demo support resource has no integer version: {desired['_id']}")
        updated = {
            **existing,
            **managed,
            "updated_at": datetime.now(UTC),
            "version": version + 1,
        }
        (await store.replace("support_resources", updated, version))
        refreshed += 1
    return refreshed


async def initialize_demo(
    store: CloudBaseStore, *, seed: bool = True, refresh_support: bool = False
) -> InitializationReport:
    created = existing = indexes = inserted = present = 0
    index_plan = build_index_projection()
    for collection in COLLECTIONS:
        try:
            (await store.create_collection(collection))
            created += 1
        except RepositoryVersionConflict:
            existing += 1
        definitions = cast(list[dict[str, Any]], index_plan[collection])
        if definitions:
            (
                await store.commands(
                    [
                        {
                            "createIndexes": collection,
                            "indexes": [
                                {
                                    "name": item["name"],
                                    "key": {field: 1 for field in cast(list[str], item["fields"])},
                                    "unique": item["unique"],
                                }
                                for item in definitions
                            ],
                        }
                    ]
                )
            )
            indexes += len(definitions)
    if seed:
        for collection, documents in demo_seed_collections().items():
            for document in documents:
                if await store.query(collection, {"_id": document["_id"]}, limit=1):
                    present += 1
                    continue
                (await store.insert(collection, document))
                inserted += 1
    refreshed = (await refresh_demo_support_resources(store)) if refresh_support else 0
    return InitializationReport(created, existing, indexes, inserted, present, refreshed)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment_file", type=Path)
    parser.add_argument("--without-seed", action="store_true")
    parser.add_argument(
        "--refresh-demo-support-resources",
        action="store_true",
        help="replace only the three known demo support placeholders",
    )
    args = parser.parse_args()
    if args.without_seed and args.refresh_demo_support_resources:
        parser.error("support resource refresh requires demo seeding to be enabled")
    values = read_environment(args.environment_file)
    settings = Settings.from_environment(values)
    if (
        not settings.cloudbase_persistence_ready
        or settings.persistence_environment_kind is not EnvironmentKind.DEMO
    ):
        print("demo CloudBase persistence is not safely configured")
        return 1
    store = CloudBaseStore(settings.cloudbase_env_id or "", settings.cloudbase_secret or "")
    try:
        report = await initialize_demo(
            store,
            seed=not args.without_seed,
            refresh_support=args.refresh_demo_support_resources,
        )
    finally:
        await store.aclose()
    print(
        "CloudBase demo initialized: "
        f"collections_created={report.collections_created} "
        f"collections_existing={report.collections_existing} "
        f"indexes_applied={report.indexes_applied} "
        f"documents_inserted={report.documents_inserted} "
        f"documents_existing={report.documents_existing} "
        f"support_resources_refreshed={report.support_resources_refreshed}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
