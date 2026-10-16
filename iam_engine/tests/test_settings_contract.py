import ast
from pathlib import Path

import pytest

from iam_engine.settings import IAM_ENVIRONMENT, load_iam_settings


def product_values(product, environ):
    """Execute the actual shared-loader declaration without initializing SaaS apps."""
    source = Path(__file__).resolve().parents[2] / product / "config/default.py"
    tree = ast.parse(source.read_text())
    imports = [node for node in tree.body if isinstance(node, ast.ImportFrom) and node.module == "iam_engine.settings"]
    assert len(imports) == 1
    nodes = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr)
        and ast.unparse(node) == "globals().update(load_iam_settings(component_api_url=BK_COMPONENT_API_URL))"
    ]
    assert len(nodes) == 1
    namespace = {"BK_COMPONENT_API_URL": environ.get("BK_COMPONENT_API_URL")}
    namespace.update({"load_iam_settings": lambda **kw: load_iam_settings(environ, **kw), "globals": lambda: namespace})
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    return {name: namespace[name] for name in IAM_ENVIRONMENT}


@pytest.mark.parametrize(
    "environ",
    [
        {},
        {"BK_COMPONENT_API_URL": "https://components.example.test/"},
        {env: "  override  " for env, _ in IAM_ENVIRONMENT.values()},
        {"BKAPP_IAM_PERMISSION_MODE": "  UnIoN  ", "BK_IAM_V4_TIMEOUT": "0", "BK_IAM_V4_BATCH_CHUNK_SIZE": "20"},
    ],
)
def test_product_environment_contracts_are_identical(environ):
    assert product_values("bklog", environ) == product_values("bkmonitor", environ) == load_iam_settings(environ)


def test_defaults_and_normalization_preserve_bklog_contract():
    values = load_iam_settings({})
    assert values["BK_IAM_PERMISSION_MODE"] == ""
    assert values["BK_IAM_V4_TIMEOUT"] == "10"
    assert values["BK_IAM_V4_BATCH_CHUNK_SIZE"] == "100"
    assert values["BK_IAM_V4_BATCH_MAX_WORKERS"] == "4"
    assert values["BK_IAM_V4_AUTH_TOKEN_CACHE_SECONDS"] == "300"
    assert values["BK_IAM_V4_GRANT_EXPIRE_DAYS"] == "365"
    assert "BK_IAM_GRANT_MAX_ATTEMPTS" not in values
    assert load_iam_settings({"BKAPP_IAM_PERMISSION_MODE": " UnIoN "})["BK_IAM_PERMISSION_MODE"] == "union"
    assert (
        load_iam_settings({"BKAPP_IAM_V4_CALLBACK_URL": " https://example.test/callback/ "})["BK_IAM_V4_CALLBACK_URL"]
        == "https://example.test/callback/"
    )


def test_gateway_is_explicit_and_legacy_monitor_names_do_not_override():
    values = load_iam_settings({"BK_IAM_V4_API_BASE_URL": "ignored", "BK_IAM_V4_SYSTEM_ID": "ignored"})
    assert values["BK_IAM_V4_APIGATEWAY_URL"] == ""
    assert values["BK_IAM_V4_SYSTEM_ID"] == ""
    assert values["BK_IAM_V4_GRANT_EXPIRE_DAYS"] == "365"
    assert isinstance(values["BK_IAM_V4_TIMEOUT"], str)
