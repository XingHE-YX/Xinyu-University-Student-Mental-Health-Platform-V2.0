#!/usr/bin/env python3
"""Validate static-hosting profiles and reject secret-looking values."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def validate(document: object, *, allow_placeholders: bool = False) -> list[str]:
    if not isinstance(document, dict) or not isinstance(document.get("hosting"), dict):
        return ["hosting profile must contain a hosting object"]
    hosting = document["hosting"]
    assert isinstance(hosting, dict)
    if set(hosting) != {"demo", "authorized"}:
        return ["hosting profile must contain demo and authorized entries"]
    errors: list[str] = []
    for name, value in hosting.items():
        if not isinstance(value, dict):
            errors.append(f"{name} hosting entry must be an object")
            continue
        origin = str(value.get("origin", "")).strip()
        api_base = str(value.get("apiBaseUrl", "")).strip()
        for key, item in (("origin", origin), ("apiBaseUrl", api_base)):
            if not item:
                errors.append(f"{name}.{key} is not configured")
            elif not allow_placeholders and ("${" in item or "<" in item or ">" in item):
                errors.append(f"{name}.{key} still contains a placeholder")
        origin_is_placeholder = "${" in origin or "<" in origin or ">" in origin
        api_is_placeholder = "${" in api_base or "<" in api_base or ">" in api_base
        if not (allow_placeholders and origin_is_placeholder):
            parsed_origin = urlparse(origin)
            if (
                parsed_origin.scheme != "https"
                or not parsed_origin.netloc
                or parsed_origin.path not in ("", "/")
            ):
                errors.append(f"{name}.origin must be an HTTPS origin without a path")
        if not (allow_placeholders and api_is_placeholder):
            parsed_api = urlparse(api_base)
            if (
                parsed_api.scheme != "https"
                or not parsed_api.netloc
                or parsed_api.path.rstrip("/") != "/api/v1"
            ):
                errors.append(f"{name}.apiBaseUrl must be an HTTPS URL ending in /api/v1")
        if value.get("artifact") != "admin/dist":
            errors.append(f"{name}.artifact must be admin/dist")
        if value.get("spaFallback") != "/index.html":
            errors.append(f"{name}.spaFallback must be /index.html")
        if value.get("httpsOnly") is not True:
            errors.append(f"{name}.httpsOnly must be true")
    demo = hosting["demo"]
    authorized = hosting["authorized"]
    if isinstance(demo, dict) and isinstance(authorized, dict):
        if demo.get("origin") and demo.get("origin") == authorized.get("origin"):
            errors.append("demo and authorized hosting origins must differ")
        if (
            demo.get("apiBaseUrl")
            and demo.get("apiBaseUrl") == authorized.get("apiBaseUrl")
        ):
            errors.append("demo and authorized API URLs must differ")
    return list(dict.fromkeys(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", type=Path)
    parser.add_argument("--allow-placeholders", action="store_true")
    args = parser.parse_args()
    try:
        document = json.loads(args.profile.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"hosting profile cannot be read: {type(error).__name__}")
        return 1
    errors = validate(document, allow_placeholders=args.allow_placeholders)
    if errors:
        print("\n".join(errors))
        return 1
    print("admin hosting profile is valid (non-secret values only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
