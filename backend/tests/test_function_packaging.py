from pathlib import Path

import pytest

from scripts.build_function_package import reject_secret_files


def test_package_rejects_secret_looking_files(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("DEEPSEEK_API_KEY=secret", encoding="utf-8")

    with pytest.raises(SystemExit, match="secret-looking"):
        reject_secret_files(tmp_path)
