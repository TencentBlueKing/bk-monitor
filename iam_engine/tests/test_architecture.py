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


def test_monitor_native_provider_assembly_has_no_intermediate_adapters():
    from bkmonitor.iam.handlers.permission import Permission
    from bkmonitor.iam.backends.v4.client import V4Client as MonitorV4Client
    from iam_engine.core.config import AuthMode
    from iam_engine.provider.router import ModeRouter
    from iam_engine.provider.base import PermissionProvider
    from iam_engine.v4.client import V4Client

    permission = Permission(username="offline", bk_tenant_id="system")
    assert isinstance(permission.mode_router, ModeRouter)
    for mode in (AuthMode.V3, AuthMode.V4):
        bundle = permission.provider_bundles[mode]
        assert isinstance(bundle.auth, PermissionProvider)
        assert bundle.auth is bundle.application is bundle.scope is permission.providers[mode.value]
        assert bundle.writer.provider is bundle.auth
    assert issubclass(MonitorV4Client, V4Client)
    product = Path(__file__).resolve().parents[2] / "bkmonitor/bkmonitor/iam"
    assert not list((product / "adapters").rglob("*.py"))
    assert not (product / "backends/auth.py").exists()
    assert not (product / "backends/grant.py").exists()
