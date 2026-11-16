import importlib.util
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
from bkmonitor.utils import graph_relation  # noqa: E402


def load_default_module(monkeypatch):
    resource_module = ModuleType("core.drf_resource")
    resource_module.Resource = type("Resource", (), {})
    error_module = ModuleType("core.errors.api")
    error_module.BKAPIError = type("BKAPIError", (Exception,), {})
    monkeypatch.setitem(sys.modules, "core.drf_resource", resource_module)
    monkeypatch.setitem(sys.modules, "core.errors.api", error_module)
    request_module = ModuleType("bkmonitor.utils.request")
    request_module.get_request = lambda **kwargs: None
    request_module.get_request_tenant_id = lambda **kwargs: "tenant-a"
    serializer_module = ModuleType("bkmonitor.utils.serializers")
    from rest_framework import serializers

    class TenantIdField(serializers.CharField):
        def __init__(self, **kwargs):
            kwargs.pop("prefer_request_tenant", None)
            super().__init__(**kwargs)

    serializer_module.TenantIdField = TenantIdField
    monkeypatch.setitem(sys.modules, "bkmonitor.utils.request", request_module)
    monkeypatch.setitem(sys.modules, "bkmonitor.utils.serializers", serializer_module)
    source_path = Path(__file__).parents[3] / "api" / "unify_query" / "default.py"
    spec = importlib.util.spec_from_file_location("_relation_default_under_test", source_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "legacy_path, v1beta3_path",
    [
        (RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH),
        (RELATION_MULTI_RESOURCE_RANGE_PATH, RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH),
    ],
)
@pytest.mark.parametrize("biz_id, enabled", [(2, True), ("2", True), (-17, True), (3, False), (None, False)])
@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2, -17])
def test_query_whitelist_selects_url(legacy_path, v1beta3_path, biz_id, enabled):
    assert resolve_relation_query_path(legacy_path, v1beta3_path, biz_id) == (v1beta3_path if enabled else legacy_path)


@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[2])
def test_removing_business_restores_legacy_url():
    assert resolve_relation_query_path(RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH, 2) == (
        RELATION_MULTI_RESOURCE_V1BETA3_PATH
    )
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[]):
        assert (
            resolve_relation_query_path(RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH, 2)
            == RELATION_MULTI_RESOURCE_PATH
        )


@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST="2, invalid, -17")
def test_query_whitelist_ignores_invalid_values():
    assert graph_relation.get_relation_v1beta3_biz_ids() == {2, -17}


@pytest.mark.parametrize("white_list", [[-1], ["-1"], [2, -1], "-1", "2, -1"])
@pytest.mark.parametrize(
    "biz_id, enabled",
    [(2, True), (5, True), ("8", True), (-57, True), (-1, True), (0, False), ("0", False), (None, False), ("x", False)],
)
def test_minus_one_enables_every_resolved_business(white_list, biz_id, enabled):
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=white_list):
        assert resolve_relation_query_path(
            RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH, biz_id
        ) == (RELATION_MULTI_RESOURCE_V1BETA3_PATH if enabled else RELATION_MULTI_RESOURCE_PATH)


@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=["*", "all", 2])
def test_other_values_do_not_enable_every_business():
    assert resolve_relation_query_path(RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH, 5) == (
        RELATION_MULTI_RESOURCE_PATH
    )
    assert resolve_relation_query_path(RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH, 2) == (
        RELATION_MULTI_RESOURCE_V1BETA3_PATH
    )


@override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[], GRAPH_RELATION_V4_BIZ_ID_WHITE_LIST=[2])
def test_old_dual_write_whitelist_does_not_enable_query():
    assert (
        resolve_relation_query_path(RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH, 2)
        == RELATION_MULTI_RESOURCE_PATH
    )


@pytest.mark.parametrize(
    "resource_name, legacy_path, v1beta3_path",
    [
        ("QueryMultiResource", RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH),
        ("QueryMultiResourceRange", RELATION_MULTI_RESOURCE_RANGE_PATH, RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH),
        ("GetKubernetesRelationResource", RELATION_MULTI_RESOURCE_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH),
        ("QueryMultiResourceV1Beta3", RELATION_MULTI_RESOURCE_V1BETA3_PATH, RELATION_MULTI_RESOURCE_V1BETA3_PATH),
        (
            "QueryMultiResourceRangeV1Beta3",
            RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH,
            RELATION_MULTI_RESOURCE_RANGE_V1BETA3_PATH,
        ),
    ],
)
@pytest.mark.parametrize("global_space", [False, True])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("biz_id", [2, -17])
def test_managed_query_changes_url_and_preserves_body_and_identity(
    monkeypatch, resource_name, legacy_path, v1beta3_path, global_space, enabled, biz_id
):
    module = load_default_module(monkeypatch)
    space_uid = "bkci__global" if global_space else f"bkcc__{biz_id}"
    sent = {}
    monkeypatch.setattr(module, "get_unify_query_url", lambda uid: "http://unify-query/")
    monkeypatch.setattr(
        module, "get_request", lambda peaceful: SimpleNamespace(user=SimpleNamespace(username=""), biz_id=None)
    )
    monkeypatch.setattr(
        module,
        "SpaceApi",
        SimpleNamespace(get_space_detail=lambda **kwargs: SimpleNamespace(is_global=global_space, bk_biz_id=biz_id)),
    )
    monkeypatch.setattr(
        module,
        "requests",
        SimpleNamespace(
            request=lambda **kwargs: (
                sent.update(kwargs) or SimpleNamespace(status_code=200, json=lambda: {"ok": True})
            )
        ),
    )
    params = {"space_uid": space_uid, "bk_tenant_id": "tenant-a", "query_list": [{"source_type": "pod"}]}
    with override_settings(RELATION_V1BETA3_BIZ_ID_WHITE_LIST=[biz_id] if enabled else []):
        assert getattr(module, resource_name)().perform_request(params.copy()) == {"ok": True}

    assert sent["url"] == "http://unify-query" + (v1beta3_path if enabled else legacy_path)
    assert sent["json"] == params
    expected_headers = {"Bk-Query-Source": "backend", "X-Bk-Tenant-Id": "tenant-a"}
    if global_space:
        expected_headers["X-Bk-Scope-Skip-Space"] = settings.APP_CODE
    else:
        expected_headers["X-Bk-Scope-Space-Uid"] = space_uid
    assert sent["headers"] == expected_headers
