#!/usr/bin/env python3
"""Build a deterministic CloudBase Python 3.11 HTTP-function zip package.

The package contains the application, ``scf_bootstrap`` and the exact locked
dependencies. The script never reads or writes a ``.env`` file and rejects
secret-looking files before creating the artifact.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/dist/xinyu-v2-python311.zip"),
        help="output zip path (default: backend/dist/xinyu-v2-python311.zip)",
    )
    parser.add_argument(
        "--python",
        dest="python_executable",
        type=Path,
        default=Path(sys.executable),
        help="Python executable used for dependency installation",
    )
    parser.add_argument(
        "--platform",
        default="manylinux2014_x86_64",
        help="target wheel platform for CloudBase (default: manylinux2014_x86_64)",
    )
    return parser.parse_args()


def ensure_python311(python_executable: Path) -> None:
    result = subprocess.run(
        [
            str(python_executable),
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip() != "3.11":
        raise SystemExit(
            "CloudBase package build requires Python 3.11, "
            f"got {result.stdout.strip() or 'unknown'}"
        )


def copy_tree(source_root: Path, package_root: Path) -> None:
    source_app = source_root / "backend" / "app"
    bootstrap = source_root / "backend" / "scf_bootstrap"
    if not source_app.is_dir() or not bootstrap.is_file():
        raise SystemExit("backend/app and backend/scf_bootstrap are required")
    shutil.copytree(
        source_app,
        package_root / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(bootstrap, package_root / "scf_bootstrap")
    shutil.copy2(
        source_root / "backend" / "requirements.lock",
        package_root / "requirements.lock",
    )
    os.chmod(package_root / "scf_bootstrap", 0o755)


def reject_secret_files(package_root: Path) -> None:
    # Wheels may legitimately ship a public CA bundle (for example certifi's
    # cacert.pem), so block private-key containers but not public certificates.
    blocked_suffixes = {".env", ".key", ".p12"}
    blocked_names = {"credentials", "secrets"}
    for path in package_root.rglob("*"):
        if not path.is_file():
            continue
        if (
            path.name in blocked_names
            or path.name.startswith(".env")
            or path.suffix in blocked_suffixes
        ):
            raise SystemExit(f"refusing to package secret-looking file: {path.name}")


def write_deterministic_zip(package_root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(package_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(package_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (path.stat().st_mode & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parents[2]
    python_executable = args.python_executable.resolve()
    ensure_python311(python_executable)
    requirements = root / "backend" / "requirements.lock"
    if not requirements.is_file():
        raise SystemExit("backend/requirements.lock is required")

    with tempfile.TemporaryDirectory(prefix="xinyu-function-") as temporary:
        package_root = Path(temporary)
        install_target = package_root / "_pip_target"
        subprocess.run(
            [
                str(python_executable),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-compile",
                "--only-binary",
                ":all:",
                "--platform",
                args.platform,
                "--implementation",
                "cp",
                "--python-version",
                "3.11",
                "--requirement",
                str(requirements),
                "--target",
                str(install_target),
            ],
            cwd=root,
            check=True,
        )
        for item in install_target.iterdir():
            target = package_root / item.name
            if target.exists():
                raise SystemExit(f"dependency collides with application file: {item.name}")
            shutil.move(str(item), target)
        install_target.rmdir()
        copy_tree(root, package_root)
        reject_secret_files(package_root)
        write_deterministic_zip(package_root, (root / args.output).resolve())

    print(f"built Python 3.11 function package: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
