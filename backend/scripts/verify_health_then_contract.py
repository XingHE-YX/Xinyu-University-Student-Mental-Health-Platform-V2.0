#!/usr/bin/env python3
"""Check the deployed health endpoint before running an interface contract command."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="deployed API origin, without a path")
    parser.add_argument(
        "--allow-degraded",
        action="store_true",
        help="allow an unconfigured health response for local smoke checks",
    )
    parser.add_argument(
        "--contract",
        nargs=argparse.REMAINDER,
        help="command to run after health succeeds, for example --contract pytest",
    )
    return parser.parse_args(argv)


def fetch_health(url: str) -> dict[str, object]:
    endpoint = f"{url.rstrip('/')}/api/v1/health"
    request = Request(endpoint, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=8) as response:  # noqa: S310 - operator-provided HTTPS endpoint
            raw = response.read()
    except HTTPError as error:
        raise SystemExit(f"health check failed with HTTP {error.code}") from None
    except URLError as error:
        raise SystemExit(f"health check unavailable: {error.reason}") from None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise SystemExit("health check returned invalid JSON") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
        raise SystemExit("health check returned an invalid response envelope")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    payload = fetch_health(args.url)
    data = payload["data"]
    assert isinstance(data, dict)
    status = data.get("status")
    if status != "ok" and not args.allow_degraded:
        raise SystemExit("health check returned a non-ready service status")
    print(f"health check passed: status={status}")
    command = list(args.contract or [])
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        return 0
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    print("interface contract command passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
