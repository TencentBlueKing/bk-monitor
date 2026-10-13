import ast
from pathlib import Path


def test_shared_runtime_has_no_product_business_imports():
    root = Path(__file__).resolve().parents[1]
    for path in root.rglob("*.py"):
        if "tests" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [item.name for item in node.names]
                if isinstance(node, ast.Import)
                else ([node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            )
            assert not any(
                name.split(".")[0] in {"apps", "bkmonitor", "monitor_web", "kernel_api"} for name in names
            ), path


def test_monitor_has_no_private_engine_or_runtime_framework():
    root = Path(__file__).resolve().parents[2]
    product = root / "bkmonitor/bkmonitor/iam"
    assert not list((product / "iam_engine").rglob("*.py"))
    removed = {"IAMFramework", "ProviderRouter", "SharedMigrationPolicy", "get_framework"}
    for path in product.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ClassDef | ast.FunctionDef):
                assert node.name not in removed, path
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("bkmonitor.iam.iam_engine"), path
                assert not removed.intersection(alias.name for alias in node.names), path


def test_products_reference_same_common_source():
    root = Path(__file__).resolve().parents[2]
    assert (root / "bkmonitor/iam_engine").resolve() == root / "iam_engine"
    assert (root / "bklog/iam_engine").resolve() == root / "iam_engine"
