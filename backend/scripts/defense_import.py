"""Preview, import, verify or roll back only the defense demo dataset."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterator, Sequence
from itertools import batched
from pathlib import Path

from app.infra.config.settings import Settings
from app.infra.config.validation import EnvironmentKind
from app.infra.database.cloudbase.client import CloudBaseStore
from app.infra.database.common import RepositoryError
from app.models.v2.documents import AssessmentModuleDocument, AssessmentQuestionnaireDocument
from app.services.v2.identity_service import HmacIdentityCipher, IdentityCipher
from scripts.defense_data import (
    COLLECTIONS,
    ENVIRONMENT_ID,
    MODULES,
    PREFIX,
    RESERVED_NUMBER,
    Bundle,
    Document,
    build_bundle,
    dashboard_snapshot,
    local_questionnaires,
    roster,
)
from scripts.initialize_cloudbase import read_environment

SECRET_FIELDS = {"student_name_ciphertext", "student_number_ciphertext"}


class ImportError(RuntimeError):
    pass


def _chunks(rows: Sequence[Document]) -> Iterator[tuple[Document, ...]]:
    return batched(rows, 24)


def equal_document(current: Document, expected: Document, cipher: IdentityCipher) -> bool:
    if current.keys() - expected.keys() - {"_openid"}:
        return False
    for key, value in expected.items():
        actual = current.get(key)
        if key in SECRET_FIELDS:
            try:
                if not isinstance(actual, str) or cipher.decrypt(actual) != cipher.decrypt(value):
                    return False
            except ValueError:
                return False
        elif actual != value:
            return False
    return True


async def _fetch(
    store: CloudBaseStore, collection: str, expected: Sequence[Document]
) -> list[Document]:
    found: list[Document] = []
    for batch in _chunks(expected):
        ids = {item["_id"] for item in batch}
        items = await store.query(collection, {"_id": {"$in": sorted(ids)}}, limit=len(ids))
        if len({item["_id"] for item in items}) != len(items) or not all(
            item["_id"] in ids for item in items
        ):
            raise ImportError(f"unexpected ID returned for {collection}")
        found.extend(items)
    return found


async def _fetch_bundle(store: CloudBaseStore, expected: Bundle) -> Bundle:
    existing = await asyncio.gather(*(_fetch(store, name, expected[name]) for name in COLLECTIONS))
    return dict(zip(COLLECTIONS, existing, strict=True))


async def _preflight_identities(
    store: CloudBaseStore, cipher: IdentityCipher
) -> tuple[Document, ...]:
    candidate_numbers = {number: user for user, (_, number) in roster().items()}
    protected: list[Document] = []
    for identity in await store.all("identity_records"):
        ciphertext = identity.get("student_number_ciphertext")
        if not ciphertext:
            continue
        try:
            number = cipher.decrypt(ciphertext)
        except ValueError:
            raise ImportError(
                "existing identity cannot be checked for student-number conflicts"
            ) from None
        if number in candidate_numbers and candidate_numbers[number] != identity["user_id"]:
            raise ImportError("student number belongs to a pre-existing account; no writes made")
        if number == RESERVED_NUMBER:
            user_id = identity["user_id"]
            if user_id.startswith(PREFIX):
                raise ImportError("reserved account unexpectedly belongs to the batch namespace")
            protected.append(identity)
            protected.append(await store.get("user_accounts", user_id))
            for collection in ("assessment_sessions", "assessment_results", "treehole_posts"):
                field = "author_user_id" if collection == "treehole_posts" else "user_id"
                protected.extend(await store.all(collection, {field: user_id}))
    return tuple(protected)


async def _cloud_questionnaires(
    store: CloudBaseStore,
) -> dict[str, AssessmentQuestionnaireDocument]:
    modules = [
        AssessmentModuleDocument.model_validate(item)
        for item in await store.all("assessment_modules")
    ]
    current = {
        item.module_code: item.current_questionnaire_version for item in modules if item.enabled
    }
    catalog = [
        AssessmentQuestionnaireDocument.model_validate(item)
        for item in await store.all("assessment_questionnaires")
    ]
    questionnaires = {
        item.module_code: item
        for item in catalog
        if item.enabled and current.get(item.module_code) == item.questionnaire_version
    }
    if set(questionnaires) != set(MODULES):
        raise ImportError("enabled cloud questionnaires do not match the three supported modules")
    return questionnaires


def _assert_matches(existing: Bundle, expected: Bundle, cipher: IdentityCipher) -> None:
    for name in COLLECTIONS:
        expected_map = {row["_id"]: row for row in expected[name]}
        for current in existing[name]:
            if not equal_document(current, expected_map[current["_id"]], cipher):
                raise ImportError(
                    f"existing {name} document differs from the batch; refusing to change it"
                )


async def manage(store: CloudBaseStore, cipher: IdentityCipher, action: str) -> tuple[Bundle, bool]:
    protected_before = await _preflight_identities(store, cipher)
    catalog = await _cloud_questionnaires(store)
    expected = build_bundle(cipher, {module: catalog[module] for module in MODULES})
    existing = await _fetch_bundle(store, expected)
    _assert_matches(existing, expected, cipher)
    if action == "apply":
        for name in COLLECTIONS:
            existing_ids = {row["_id"] for row in existing[name]}
            missing = [row for row in expected[name] if row["_id"] not in existing_ids]
            for batch in _chunks(missing):
                receipt = await store.request(
                    "POST", store.collection_path(name), body={"data": batch}
                )
                if set(receipt.get("insertedIds", [])) != {row["_id"] for row in batch}:
                    raise ImportError(
                        f"insertion receipt did not match the intended IDs in {name}; rerun verify"
                    )
    elif action == "rollback":
        for name in reversed(COLLECTIONS):
            for batch in _chunks(existing[name]):
                conditions = [{**row} for row in batch]
                await store.request(
                    "POST",
                    f"{store.collection_path(name)}/remove",
                    body={"query": {"$or": conditions}, "multi": True},
                )

    if action in {"apply", "verify", "rollback"}:
        existing = await _fetch_bundle(store, expected)
        _assert_matches(existing, expected, cipher)
        if await _preflight_identities(store, cipher) != protected_before:
            raise ImportError(
                "reserved account data changed during processing; investigate before continuing"
            )
        for name in COLLECTIONS:
            expected_count = 0 if action == "rollback" else len(expected[name])
            if len(existing[name]) != expected_count:
                raise ImportError(
                    f"verification failed for {name}: "
                    f"found {len(existing[name])} of {expected_count}"
                )
    print(
        "active batch documents:",
        ", ".join(f"{name}={len(rows)}" for name, rows in existing.items()),
    )
    return (expected if action == "preview" else existing), bool(protected_before)


def _write_snapshot(path: Path, bundle: Bundle) -> None:
    snapshot = dashboard_snapshot(bundle)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("preview", "apply", "verify", "rollback", "local"))
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--snapshot", type=Path)
    flags = parser.parse_args()
    if flags.action not in {"local", "apply", "verify"} and flags.snapshot:
        parser.error("snapshots can only be written from local, apply or verify")
    if flags.action == "local":
        bundle = build_bundle(
            HmacIdentityCipher("local-defense-fixture-only"), local_questionnaires()
        )
    else:
        if flags.env_file is None:
            parser.error("--env-file is required for a CloudBase operation")
        settings = Settings.from_environment(read_environment(flags.env_file))
        if (
            not settings.cloudbase_persistence_ready
            or settings.persistence_environment_kind is not EnvironmentKind.DEMO
            or settings.cloudbase_env_id != ENVIRONMENT_ID
            or not settings.session_secret
            or not settings.cloudbase_secret
        ):
            parser.error(
                "credentials are not configured for the registered defense demo environment"
            )
        store = CloudBaseStore(ENVIRONMENT_ID, settings.cloudbase_secret)
        try:
            bundle, protected = await manage(
                store, HmacIdentityCipher(settings.session_secret), flags.action
            )
        except (ImportError, RepositoryError) as error:
            print(f"Defense {flags.action} stopped: {error}")
            return 1
        finally:
            await store.aclose()
        print("reserved identity:", "found and excluded" if protected else "not found; not created")
    if flags.snapshot:
        _write_snapshot(flags.snapshot, bundle)
    print("dataset counts:", {name: len(rows) for name, rows in bundle.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
