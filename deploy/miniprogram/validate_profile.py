#!/usr/bin/env python3
"""Validate non-secret WeChat mini-program build profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def validate(document: object, *, allow_placeholders: bool = False) -> list[str]:
    if not isinstance(document, dict) or set(document) != {"demo", "authorized"}:
        return ["profile must contain demo and authorized entries"]
    errors: list[str] = []
    environments = {name: document[name] for name in ("demo", "authorized")}
    for name, profile in environments.items():
        if not isinstance(profile, dict):
            errors.append(f"{name} profile must be an object")
            continue
        for key in ("appId", "cloudbaseEnvId", "apiBaseUrl"):
            value = str(profile.get(key, "")).strip()
            if not value:
                errors.append(f"{name}.{key} is not configured")
            elif not allow_placeholders and ("${" in value or "<" in value or ">" in value):
                errors.append(f"{name}.{key} still contains a placeholder")
        api_url = urlparse(str(profile.get("apiBaseUrl", "")))
        if api_url.scheme != "https" or not api_url.netloc or api_url.query or api_url.fragment:
            errors.append(
                f"{name}.apiBaseUrl must be an HTTPS URL without query or fragment"
            )
        if api_url.path.rstrip("/") != "/api/v1":
            errors.append(f"{name}.apiBaseUrl must end with /api/v1")
    demo = environments["demo"]
    authorized = environments["authorized"]
    if isinstance(demo, dict) and isinstance(authorized, dict):
        if demo.get("appId") and demo.get("appId") == authorized.get("appId"):
            errors.append("mini-program AppIDs must differ between environments")
        if (
            demo.get("cloudbaseEnvId")
            and demo.get("cloudbaseEnvId") == authorized.get("cloudbaseEnvId")
        ):
            errors.append("CloudBase environment IDs must differ between environments")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()
    try:
        document = json.loads(args.profile.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"profile cannot be read: {type(error).__name__}")
        return 1
    errors = validate(document, allow_placeholders=args.allow_placeholders)
    if errors:
        print("\n".join(errors))
        return 1
    print("mini-program profile is valid (non-secret values only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
