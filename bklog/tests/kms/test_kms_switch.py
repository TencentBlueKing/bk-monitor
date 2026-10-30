"""Include the CI-discovered switch regression in the standalone KMS suite."""

import os
import subprocess
import sys
from pathlib import Path


def test_same_key_switch_preserves_stored_credentials():
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "apps.tests.log_extract.test_kms_switch"],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
