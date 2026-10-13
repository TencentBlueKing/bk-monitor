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
    removed = {
        "IAMFramework", "ProviderRouter", "SharedMigrationPolicy", "get_framework",
        "V4CallbackRegistry", "V4CallbackService", "V4SystemTokenProvider", "IamCallbackAuthentication",
        "SchemaRegistry", "IAMFramework", "PolicyExpression",
    }
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


def test_monitor_preserves_original_v3_public_settings():
    root = Path(__file__).resolve().parents[2]
    config = (root / "bkmonitor/config/default.py").read_text()
    assert 'BK_IAM_APP_CODE = os.getenv("BK_IAM_V3_APP_CODE", "bk_iam")' in config
    assert 'get_service_url(BK_IAM_APP_CODE, bk_paas_host=BK_PAAS_HOST)' in config
    assert 'BK_IAM_SYSTEM_NAME = _("监控平台")' in config
    assert "BK_IAM_SAAS_APP_CODE" not in config


def test_callback_products_do_not_keep_an_alternate_dispatch_or_catalog_query():
    root = Path(__file__).resolve().parents[2]
    for product in ("bkmonitor/bkmonitor/iam", "bklog/apps/iam"):
        path = root / product / "views/resources_v4.py"
        tree = ast.parse(path.read_text())
        assert not any(isinstance(node, ast.ClassDef) for node in ast.walk(tree)), path
        assert any(
            isinstance(node, ast.ImportFrom) and node.module == "iam_engine.v4.callback"
            for node in ast.walk(tree)
        ), path
        assert not any(isinstance(node, ast.Attribute) and node.attr == "objects" for node in ast.walk(tree)), path
    catalog = root / "bkmonitor/bkmonitor/iam/handlers/catalog.py"
    assert not any(
        isinstance(node, ast.Attribute) and node.attr == "objects" for node in ast.walk(ast.parse(catalog.read_text()))
    )
    views = root / "bkmonitor/bkmonitor/iam/views"
    for retired in ("callback_auth", "callback_config", "callback_registry", "callback_service", "callback_handlers"):
        assert not (views / (retired + ".py")).exists()


def test_monitor_native_provider_assembly_has_no_intermediate_adapters():
    from bkmonitor.iam.permission import Permission
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
        assert bundle.auth is bundle.application is bundle.scope is permission.get_provider(mode.value)
        assert bundle.writer.provider is bundle.auth
    assert issubclass(MonitorV4Client, V4Client)
    product = Path(__file__).resolve().parents[2] / "bkmonitor/bkmonitor/iam"
    assert not list((product / "adapters").rglob("*.py"))
    assert not (product / "backends/auth.py").exists()
    assert not (product / "backends/grant.py").exists()


def test_retired_metadata_policy_and_configuration_frameworks_are_absent():
    root = Path(__file__).resolve().parents[2]
    for file in (
        "iam_engine/schema/registry.py", "iam_engine/schema/loaders.py", "iam_engine/schema/visibility.py",
        "iam_engine/policy/expression.py", "iam_engine/policy/evaluator.py",
        "bkmonitor/bkmonitor/iam/backends/v4/config.py",
        "bkmonitor/bkmonitor/iam/backends/v3/policy_converter.py",
        "bkmonitor/bkmonitor/iam/management/commands/iam_generate_config.py",
    ):
        assert not (root / file).exists()
    action = ast.parse((root / "bkmonitor/bkmonitor/iam/action.py").read_text())
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "setattr" for n in ast.walk(action))
    resources = ast.parse((root / "bklog/apps/iam/handlers/resources.py").read_text())
    assert not any(isinstance(n, ast.Attribute) and n.attr == "objects" for n in ast.walk(resources))
