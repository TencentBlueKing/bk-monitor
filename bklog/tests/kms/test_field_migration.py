"""Run field identity/copy/clone and SQLite migration regression in isolation."""

import os
import subprocess
import sys
from pathlib import Path


def test_sdk_and_blueapps_fields_survive_sqlite_migration():
    result = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("field_migration_worker.py"))],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().endswith("field copy + SQLite migration apply/reverse: OK")
