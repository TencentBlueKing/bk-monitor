import ast
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from django.conf import settings

if not settings.configured:
    settings.configure(
        APP_CODE="bk_monitorv3",
        ENABLE_MULTI_TENANT_MODE=True,
        RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[],
        REST_FRAMEWORK={},
        UNIFY_QUERY_ROUTING_RULES=[],
        UNIFY_QUERY_URL="http://unify-query/",
    )

from django.test import override_settings  # noqa: E402

from api.unify_query.relation_routing import (  # noqa: E402
    RELATION_MULTI_RESOURCE_PATH,
    RELATION_MULTI_RESOURCE_RANGE_PATH,
    RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH,
    RELATION_MULTI_RESOURCE_V1BETA3_PATH,
    resolve_relation_query_path,
)
from bkmonitor.utils.graph_relation import get_relation_v1beta3_biz_ids  # noqa: E402


@pytest.mark.parametrize(
    ("legacy_path", "v1beta3_path"),
    [
        (RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH),
        (RELATION_MULTI_RESOURCE_RANGE_PATH, RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH),
    ],
)
@pytest.mark.parametrize(("bk_biz_id", "use_v1beta3"), [(2, True), (3, False)])
@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2])
def test_relation_query_uses_query_whitelist_for_v1beta3_routing(legacy_path, v1beta3_path, bk_biz_id, use_v1beta3):
    path = resolve_relation_query_path(
        legacy_path,
        v1beta3_path,
        bk_biz_id,
    )

    assert path == (v1beta3_path if use_v1beta3 else legacy_path)


@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2])
def test_relation_query_returns_to_v1_after_biz_removed_from_whitelist():
    path = resolve_relation_query_path(
        RELATION_MULTI_RESOURCE_PATH,
        RELATION_MULTI_RESOURCE_V1BETA3_PATH,
        2,
    )
    assert path == RELATION_MULTI_RESOURCE_V1BETA3_PATH

    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
        path = resolve_relation_query_path(
            RELATION_MULTI_RESOURCE_PATH,
            RELATION_MULTI_RESOURCE_V1BETA3_PATH,
            2,
        )

    assert path == RELATION_MULTI_RESOURCE_PATH


@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST="2, invalid, 3")
def test_relation_query_whitelist_ignores_invalid_values():
    assert get_relation_v1beta3_biz_ids() == {2, 3}


@pytest.mark.parametrize(
    ("legacy_path", "new_path"),
    [
        (RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH),
        (RELATION_MULTI_RESOURCE_RANGE_PATH, RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH),
    ],
)
@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2], GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST=[])
def test_relation_rollout_enables_new_query_without_old_dual_write_flag(legacy_path, new_path):
    assert resolve_relation_query_path(legacy_path, new_path, 2) == new_path
    assert resolve_relation_query_path(legacy_path, new_path, 3) == legacy_path


@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[], GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST=[2])
def test_query_rollback_does_not_fall_back_to_old_dual_write_flag():
    assert (
        resolve_relation_query_path(RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH, 2)
        == RELATION_MULTI_RESOURCE_PATH
    )


@pytest.mark.parametrize("new_value, expected", [(None, []), ("", []), ("3, -4", [3, -4])])
def test_query_environment_setting_does_not_inherit_old_dual_write_flag(monkeypatch, new_value, expected):
    monkeypatch.setenv("GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST", "2")
    if new_value is None:
        monkeypatch.delenv("RELATION_V1BETA3_BIZ_ID_WHITE_LIST", raising=False)
    else:
        monkeypatch.setenv("RELATION_V1BETA3_BIZ_ID_WHITE_LIST", new_value)

    source_path = Path(__file__).parents[3] / "config" / "default.py"
    module = ast.parse(source_path.read_text())
    # Evaluate the actual default without loading unrelated deployment settings.
    assignment = next(
        node
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "RELATION_V1BETA3_BIZ_ID_WHITE_LIST"
            for target in node.targets
        )
    )
    namespace = {"os": os}
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), str(source_path), "exec"), namespace)
    assert namespace["RELATION_V1BETA3_BIZ_ID_WHITE_LIST"] == expected


@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2])
def test_new_global_config_starts_with_environment_rollout_value():
    source_path = Path(__file__).parents[3] / "bkmonitor" / "define" / "global_config.py"
    function = next(
        node
        for node in ast.parse(source_path.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "init_or_update_global_config"
    )
    key = "RELATION_V1BETA3_BIZ_ID_WHITE_LIST"
    serializer = SimpleNamespace(default=[], label="relation rollout", _kwargs={})
    namespace = {
        "GLOBAL_CONFIGS": [key],
        "ADVANCED_OPTIONS": {key: serializer},
        "STANDARD_CONFIGS": {},
        "settings": settings,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source_path), "exec"), namespace)

    created = []

    class GlobalConfig:
        class DoesNotExist(Exception):
            pass

        objects = SimpleNamespace(get=lambda **kwargs: (_ for _ in ()).throw(GlobalConfig.DoesNotExist()))

        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self.description = ""
            self.data_type = ""
            self.options = {}

        def save(self):
            created.append(self)

    namespace["init_or_update_global_config"](GlobalConfig)
    assert len(created) == 1
    assert created[0].value == [2]


@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2])
def test_relation_query_uses_v1beta3_for_whitelisted_biz_without_binding_lookup():
    path = resolve_relation_query_path(
        RELATION_MULTI_RESOURCE_PATH,
        RELATION_MULTI_RESOURCE_V1BETA3_PATH,
        2,
    )

    assert path == RELATION_MULTI_RESOURCE_V1BETA3_PATH


def test_perform_request_routes_after_resolving_space_biz_and_tenant(monkeypatch):
    resource_module = ModuleType("core.drf_resource")
    resource_module.Resource = type("Resource", (), {})
    error_module = ModuleType("core.errors.api")
    error_module.BKAPIError = type("BKAPIError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "core.drf_resource", resource_module)
    monkeypatch.setitem(sys.modules, "core.errors.api", error_module)

    source_path = Path(__file__).parents[3] / "api" / "unify_query" / "default.py"
    spec = importlib.util.spec_from_file_location("_relation_default_under_test", source_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    route_context = {}

    def resolve_path(legacy_path, v1beta3_path, bk_biz_id):
        route_context["bk_biz_id"] = bk_biz_id
        return v1beta3_path

    sent_request = {}

    def request(**kwargs):
        sent_request.update(kwargs)
        return SimpleNamespace(status_code=200, json=lambda: {"result": True})

    monkeypatch.setattr(module, "resolve_relation_query_path", resolve_path)
    monkeypatch.setattr(module, "get_unify_query_url", lambda space_uid: "http://unify-query/")
    monkeypatch.setattr(
        module,
        "get_request",
        lambda peaceful: SimpleNamespace(user=SimpleNamespace(username=""), biz_id=None),
    )
    monkeypatch.setattr(
        module,
        "SpaceApi",
        SimpleNamespace(get_space_detail=lambda **kwargs: SimpleNamespace(is_global=False, bk_biz_id=2)),
    )
    monkeypatch.setattr(module, "requests", SimpleNamespace(request=request))

    result = module.QueryMultiResource().perform_request(
        {"space_uid": "bkcc__2", "bk_tenant_id": "tenant-a", "query_list": []}
    )

    assert result == {"result": True}
    assert route_context == {"bk_biz_id": 2}
    assert sent_request["url"] == "http://unify-query/api/v1/relation/v1beta3/multi_resource"
    assert sent_request["headers"]["X-Bk-Tenant-Id"] == "tenant-a"

    monkeypatch.setattr(module, "resolve_relation_query_path", resolve_relation_query_path)
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
        module.QueryMultiResourceV1Beta3().perform_request(
            {"space_uid": "bkcc__2", "bk_tenant_id": "tenant-a", "query_list": []}
        )
    assert sent_request["url"] == "http://unify-query/api/v1/relation/v1beta3/multi_resource"


def test_all_relation_resources_declare_v1_and_v1beta3_paths():
    source_path = Path(__file__).parents[3] / "api" / "unify_query" / "default.py"
    module = ast.parse(source_path.read_text())
    expected_paths = {
        "GetKubernetesRelationResource": {
            "path": "RELATION_MULTI_RESOURCE_PATH",
            "v1beta3_path": "RELATION_MULTI_RESOURCE_V1BETA3_PATH",
        },
        "QueryMultiResource": {
            "path": "RELATION_MULTI_RESOURCE_PATH",
            "v1beta3_path": "RELATION_MULTI_RESOURCE_V1BETA3_PATH",
        },
        "QueryMultiResourceRange": {
            "path": "RELATION_MULTI_RESOURCE_RANGE_PATH",
            "v1beta3_path": "RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH",
        },
    }

    actual_paths = {}
    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name not in expected_paths:
            continue
        actual_paths[node.name] = {
            statement.targets[0].id: statement.value.id
            for statement in node.body
            if isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id in {"path", "v1beta3_path"}
            and isinstance(statement.value, ast.Name)
        }

    assert actual_paths == expected_paths
