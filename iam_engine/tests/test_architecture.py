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
