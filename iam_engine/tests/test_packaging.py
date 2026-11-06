"""Test source references and an isolated deployment-shaped shared artifact."""

from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("product", ["bklog", "bkmonitor"])
def test_product_reference_is_same_source_and_dereferenced_artifact_imports(product, tmp_path):
    reference = ROOT / product / "iam_engine"
    assert reference.is_symlink()
    assert reference.resolve() == ROOT / "iam_engine"
    artifact = tmp_path / "code"
    artifact.mkdir()
    shutil.copytree(
        reference, artifact / "iam_engine", symlinks=False, ignore=shutil.ignore_patterns("__pycache__", "tests")
    )
    env = {**os.environ, "PYTHONPATH": str(artifact)}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from iam_engine.core.config import AuthMode; "
            "from iam_engine.provider.router import ModeRouter; "
            "from iam_engine.migration.dual_write import DualWriteGrantOrchestrator; "
            "print(AuthMode.UNION.value)",
        ],
        cwd=artifact,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "union"


def test_monitor_container_copies_source_next_to_product_symlink():
    dockerfile = (ROOT / "bkmonitor/Dockerfile").read_text()
    assert "iam_engine/ /app/iam_engine/" in dockerfile
