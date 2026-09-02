#!/usr/bin/env python3
"""Validate a rendered CloudBase manifest without printing secret values."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse


def validate(path: Path) -> list[str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    environments = document.get("environments", {})
    errors: list[str] = []
    if set(environments) != {"demo", "authorized"}:
        errors.append("manifest must contain demo and authorized environments")
        return errors
    demo, authorized = environments["demo"], environments["authorized"]
    for name, env in environments.items():
        for key in ("envId", "namespace", "hostingOrigin"):
            value = str(env.get(key, ""))
            if not value or value.startswith("${"):
                errors.append(f"{name}.{key} is not configured")
        origin = urlparse(str(env.get("hostingOrigin", "")))
        if origin.scheme != "https" or not origin.netloc or origin.path not in ("", "/"):
            errors.append(f"{name}.hostingOrigin must be an HTTPS origin without a path")
        function = env.get("function", {})
        if function.get("runtime") != "Python3.11" or function.get("httpPort") != 9000 or function.get("entrypoint") != "scf_bootstrap":
            errors.append(f"{name}.function must use Python3.11, port 9000 and scf_bootstrap")
    if demo.get("envId") == authorized.get("envId"):
        errors.append("CloudBase environment IDs must differ")
    if demo.get("namespace") == authorized.get("namespace"):
        errors.append("database namespaces must differ")
    if demo.get("demoMode") is not True or authorized.get("demoMode") is not False:
        errors.append("demoMode must be true for demo and false for authorized")
    return list(dict.fromkeys(errors))


if __name__ == "__main__":
    result = validate(Path(sys.argv[1])) if len(sys.argv) == 2 else ["usage: validate_manifest.py FILE"]
    if result:
        print("\n".join(result))
        raise SystemExit(1)
    print("manifest is valid (secret values were not displayed)")
