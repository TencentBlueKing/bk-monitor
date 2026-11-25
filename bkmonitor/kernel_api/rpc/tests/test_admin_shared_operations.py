"""Verify shared functionality through the public Kernel RPC entry point."""

from types import SimpleNamespace

import pytest
from django.urls import include, path, resolve
from rest_framework.test import APIRequestFactory
from rest_framework.exceptions import PermissionDenied

from bkmonitor.models import ApiAuthToken
from bkmonitor.models.token import AuthType
from core.drf_resource.exceptions import CustomException
from kernel_api.resource.kernel_rpc import KernelRPCResource
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin import diagnostics
from kernel_api.rpc.functions.admin.shared_operations import SHARED_OPERATIONS
from metadata.models import DataSource


def call(name, **params):
    return KernelRPCResource().perform_request({"func_name": name, "params": params})["result"]


@pytest.mark.parametrize(("operation", "source_name", "safety"), SHARED_OPERATIONS)
def test_discovery_and_dispatch_share_source_contract(monkeypatch, operation, source_name, safety):
    name = f"admin.{operation}"
    detail = call("__meta__", action="detail", target_func_name=name)["function"]
    source = KernelRPCRegistry._functions[source_name]
    assert detail == {**source.to_detail(), "func_name": name}
    received = []

    def handler(params):
        received.append(params)
        return {"status": "ok", "operation": "test", "items": [1, 2]}

    monkeypatch.setattr(source, "handler", handler)
    params = {"bk_tenant_id": "system", "operation": "test"}
    result = call(name, **params)
    assert received == [params]
    assert result["data"]["items"] == [1, 2]
    assert result["meta"]["operation"] == operation
    assert result["meta"]["func_name"] == name
    assert result["meta"]["safety_level"] == safety
    assert result["warnings"] == []


def test_admin_info_through_v4_post_route():
    from core.drf_resource.routers import ResourceRouter
    from kernel_api.views.v4 import kernel_rpc

    router = ResourceRouter()
    router.register_module(kernel_rpc)
    url = "/api/v4/kernel_rpc/call/"
    match = resolve(url, urlconf=(path("api/v4/", include(router.urls)),))
    request = APIRequestFactory().post(url, {"func_name": "admin.environment.info"}, format="json")
    response = match.func(request, **match.kwargs)
    assert response.status_code == 200
    assert response.data["protocol"] == "call"
    assert response.data["result"]["data"] == call("info")


def test_environment_and_catalogs_through_kernel():
    assert call("admin.environment.info")["data"] == call("info")
    assert {"bkdata", "gse", "cmdb", "grafana", "nodeman"} <= {
        domain["id"] for domain in call("admin.platform.query")["data"]["domains"]
    }
    assert {
        "query_relation_v1",
        "query_relation_v1beta3",
        "query_relation_range_v1",
        "query_relation_range_v1beta3",
        "relation_schema",
    } <= {item["id"] for item in call("admin.unify_query.catalog")["data"]["operations"]}
    for key in ("admin.platform.query", "admin.unify_query.catalog"):
        with pytest.raises(CustomException) as failure:
            call(key, mode="describe", domain="missing", operation="missing")
        assert failure.value.data["error"]["code"]
        assert failure.value.data["next_call"]


@pytest.mark.parametrize(
    ("name", "params"),
    [
        ("alarm_strategy.manage", {"operation": "create"}),
        ("alarm_strategy.double_check_manage", {"operation": "enable", "strategy_id": 1}),
        ("alarm_redis.routing_apply", {"operation": "apply", "exclusive_change_window": True}),
        ("circuit_breaking.manage", {"operation": "create"}),
        ("api_auth_token.manage", {"operation": "revoke"}),
    ],
)
def test_admin_writes_keep_source_confirmation(name, params):
    with pytest.raises(CustomException, match="confirmed=true"):
        call(f"admin.{name}", bk_tenant_id="system", operator="alice", **params)


@pytest.mark.django_db(databases="__all__")
def test_revoke_and_legacy_delete_keep_distinct_database_semantics():
    def token(app):
        return ApiAuthToken.objects.create(
            bk_tenant_id="system", name=app, type=AuthType.API, namespaces=["biz#2"], params={"app_code": app}
        )

    revoked = token("shared-op-revoke")
    deleted = token("shared-op-delete")
    result = call(
        "admin.api_auth_token.manage",
        operation="revoke",
        id=revoked.id,
        bk_tenant_id="system",
        operator="alice",
        confirmed=True,
    )
    assert result["data"]["changed"] and result["meta"]["safety_level"] == "write"
    revoked.refresh_from_db()
    assert (revoked.is_enabled, revoked.is_deleted, revoked.namespaces) == (False, False, [])
    call("admin.api_auth_token.delete", id=deleted.id, bk_tenant_id="system")
    deleted.refresh_from_db()
    assert (deleted.is_enabled, deleted.is_deleted) == (False, True)


@pytest.mark.django_db(databases="__all__")
def test_report_token_uses_authenticated_tenant_for_all_requested_sources(monkeypatch, settings):
    settings.ENABLE_MULTI_TENANT_MODE = True
    monkeypatch.setattr(
        diagnostics,
        "get_request",
        lambda peaceful: SimpleNamespace(user=SimpleNamespace(is_authenticated=True, tenant_id="tenant-a")),
    )

    def source(tenant):
        return DataSource.objects.create(
            bk_tenant_id=tenant,
            data_name="report-test",
            mq_cluster_id=1,
            mq_config_id=1,
            is_custom_source=True,
            token="test-report-token",
        )

    own, other = source("tenant-a"), source("tenant-b")
    params = {"metric_data_id": own.pk, "format": "json"}
    result = call("admin.custom_report.report_token", **params)
    assert result["data"]["tokens"] == {"json": "test-report-token"}
    assert result["meta"]["sensitive_read"] and result["meta"]["effective_bk_tenant_id"] == "tenant-a"
    from bkmonitor.utils import tenant as tenant_utils
    from bkmonitor.utils.cipher import transform_data_id_to_token

    monkeypatch.setattr(tenant_utils, "bk_biz_id_to_bk_tenant_id", lambda biz: "tenant-b" if biz == 42 else "tenant-a")
    both = call("admin.custom_report.report_token", metric_data_id=own.pk, format="all")
    assert both["data"]["tokens"] == {"json": "test-report-token", "prometheus": transform_data_id_to_token(own.pk)}
    for rejected in (
        {**params, "bk_tenant_id": "tenant-b"},
        {**params, "bk_tenant_id": "tenant-a", "bk_biz_id": 42},
        {**params, "metric_data_id": other.pk},
        {**params, "format": "prometheus", "trace_data_id": other.pk},
        {**params, "format": "prometheus", "token_version": "v1", "profile_data_id": other.pk},
    ):
        with pytest.raises(PermissionDenied):
            call("admin.custom_report.report_token", **rejected)


@pytest.mark.parametrize(
    ("name", "command"),
    [
        ("environment.effective_setting", "get_effective_setting"),
        ("custom_report.metric_sync", "diagnose_ts_metric_sync"),
        ("custom_report.metric_registration", "inspect_ts_metric_metadata"),
    ],
)
def test_diagnostic_commands_cannot_be_retargeted(name, command, monkeypatch):
    from kernel_api.rpc.functions.bkm_cli import commands

    received = []

    def capture(params):
        received.append(params)
        return {"ok": True}

    monkeypatch.setitem(commands._REGISTRY, command, capture)
    assert call(f"admin.{name}", command_id="get_report_token")["data"]["command_id"] == command
    assert received == [{"command_id": "get_report_token"}]
