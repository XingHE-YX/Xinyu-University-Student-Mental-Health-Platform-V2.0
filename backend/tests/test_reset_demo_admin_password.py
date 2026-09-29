from pathlib import Path

from scripts.initialize_cloudbase import read_environment
from scripts.reset_demo_admin_password import replace_hash


def test_replace_hash_updates_only_the_private_hash_entry(tmp_path: Path) -> None:
    path = tmp_path / ".env.demo.local"
    path.write_text(
        "DEMO_MODE=true\nADMIN_PASSWORD_HASH=old-hash\nCLOUDBASE_ENV_ID=demo-env\n",
        encoding="utf-8",
    )

    replace_hash(path, "new-hash")

    assert read_environment(path) == {
        "DEMO_MODE": "true",
        "ADMIN_PASSWORD_HASH": "new-hash",
        "CLOUDBASE_ENV_ID": "demo-env",
    }
    assert path.stat().st_mode & 0o777 == 0o600
