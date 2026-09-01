"""日志采集 Fast Update MCP 资源测试。"""

from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from bkmonitor.iam import ActionEnum
from kernel_api.resource import log_collection_update as update_module
from kernel_api.resource.log_collection_update import FastUpdateLogCollectorResource
from kernel_api.views.v4.log_collection_update import CanonicalBusinessActionPermission, LogCollectionUpdateViewSet


@pytest.mark.parametrize("field", ["environment", "etl_config", "fields", "storage_cluster_id"])
def test_serializer_rejects_environment_clean_and_storage_fields(field):
    serializer = FastUpdateLogCollectorResource.RequestSerializer(
        data={"bk_biz_id": 2, "collector_config_id": 1, "description": "new", field: "forbidden"}
    )
    assert not serializer.is_valid()
    assert field in serializer.errors


def test_serializer_requires_at_least_one_update_field():
    serializer = FastUpdateLogCollectorResource.RequestSerializer(data={"bk_biz_id": 2, "collector_config_id": 1})
    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


def test_serializer_rejects_non_object_payload_without_crashing():
    serializer = FastUpdateLogCollectorResource.RequestSerializer(data=[])
    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


def test_serializer_rejects_invalid_collector_id():
    serializer = FastUpdateLogCollectorResource.RequestSerializer(
        data={"bk_biz_id": 2, "collector_config_id": 0, "description": "new"}
    )
    assert not serializer.is_valid()
    assert "collector_config_id" in serializer.errors


@pytest.mark.parametrize(
    ("payload", "error_field"),
    [
        ({"params": {"unknown": True}}, "params.unknown"),
        ({"target_nodes": [{"bk_host_id": 1, "unknown": True}]}, "target_nodes[0].unknown"),
        (
            {"configs": [{"collector_type": "container_log_config", "params": {}, "unknown": True}]},
            "configs[0].unknown",
        ),
        (
            {
                "configs": [
                    {
                        "collector_type": "container_log_config",
                        "params": {"conditions": {"type": "match", "unknown": True}},
                    }
                ]
            },
            "configs[0].params.conditions.unknown",
        ),
    ],
)
def test_serializer_rejects_unknown_nested_fields(payload, error_field):
    serializer = FastUpdateLogCollectorResource.RequestSerializer(
        data={"bk_biz_id": 2, "collector_config_id": 1, **payload}
    )
    assert not serializer.is_valid()
    assert error_field in serializer.errors


def test_update_view_requires_log_collection_mcp_permission():
    permissions = LogCollectionUpdateViewSet().get_permissions()
    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.USING_LOG_COLLECTION_MCP]


def test_update_permission_rejects_conflicting_business_alias():
    permission = CanonicalBusinessActionPermission([ActionEnum.USING_LOG_COLLECTION_MCP])
    request = SimpleNamespace(
        data={"bk_biz_id": "2", "biz_id": "3"},
        biz_id="3",
    )

    assert permission.has_permission(request, None) is False


def test_host_update_injects_clean_switch_and_returns_tasks(monkeypatch):
    captured = {}

    def fast_update(**kwargs):
        captured.update(kwargs)
        return {"collector_config_id": 10, "subscription_id": 20, "task_id_list": [30]}

    log_search = SimpleNamespace(
        log_collector_update_context=lambda **kwargs: {"bk_biz_id": 2, "environment": "linux"},
        fast_update_log_collector=fast_update,
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    result = FastUpdateLogCollectorResource().perform_request(
        {
            "bk_biz_id": 2,
            "collector_config_id": 10,
            "description": "",
            "target_nodes": [{"bk_host_id": 1}],
        }
    )

    assert captured == {
        "collector_config_id": 10,
        "update_clean_config": False,
        "enforce_permission": True,
        "description": "",
        "target_nodes": [{"bk_host_id": 1}],
    }
    assert result == {
        "collector_config_id": 10,
        "environment": "linux",
        "subscription_id": 20,
        "task_ids": ["30"],
        "updated_fields": ["description", "target_nodes"],
        "clean_config_updated": False,
    }


def test_update_forwards_parent_index_set_ids(monkeypatch):
    captured = {}
    log_search = SimpleNamespace(
        log_collector_update_context=lambda **kwargs: {"bk_biz_id": 2, "environment": "linux"},
        fast_update_log_collector=lambda **kwargs: captured.update(kwargs) or {"collector_config_id": 10},
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    result = FastUpdateLogCollectorResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 10, "parent_index_set_ids": [901, 902]}
    )

    assert captured["parent_index_set_ids"] == [901, 902]
    assert "parent_index_set_id" not in captured
    assert result["updated_fields"] == ["parent_index_set_ids"]


def test_container_update_uses_container_fields(monkeypatch):
    log_search = SimpleNamespace(
        log_collector_update_context=lambda **kwargs: {
            "bk_biz_id": 2,
            "environment": "container",
            "bcs_cluster_id": "BCS-K8S-00000",
        },
        fast_update_log_collector=lambda **kwargs: {
            "collector_config_id": 11,
            "subscription_id": None,
            "task_id_list": [31, 32],
        },
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    result = FastUpdateLogCollectorResource().perform_request(
        {
            "bk_biz_id": 2,
            "collector_config_id": 11,
            "configs": [{"collector_type": "container_log_config"}],
            "add_pod_label": False,
        }
    )

    assert result["environment"] == "container"
    assert result["task_ids"] == ["31", "32"]
    assert result["updated_fields"] == ["add_pod_label", "configs"]


def test_legacy_null_environment_routes_to_host_even_with_bcs_cluster_id(monkeypatch):
    captured = {}
    log_search = SimpleNamespace(
        log_collector_update_context=lambda **kwargs: {
            "bk_biz_id": 2,
            "environment": None,
            "bcs_cluster_id": "0",
            "collector_scenario_id": "row",
        },
        fast_update_log_collector=lambda **kwargs: (
            captured.update(kwargs) or {"collector_config_id": 15, "subscription_id": 21, "task_id_list": [41]}
        ),
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    result = FastUpdateLogCollectorResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 15, "target_nodes": []}
    )

    assert result["environment"] == "linux"
    assert captured["target_nodes"] == []
    assert captured["update_clean_config"] is False
    assert captured["enforce_permission"] is True


def test_legacy_windows_environment_uses_collector_scenario(monkeypatch):
    log_search = SimpleNamespace(
        log_collector_update_context=lambda **kwargs: {
            "bk_biz_id": 2,
            "environment": None,
            "bcs_cluster_id": "",
            "collector_scenario_id": "wineventlog",
        },
        fast_update_log_collector=lambda **kwargs: {
            "collector_config_id": 16,
            "subscription_id": 22,
            "task_id_list": [42],
        },
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    result = FastUpdateLogCollectorResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 16, "data_encoding": "GBK"}
    )

    assert result["environment"] == "windows"


def test_rejects_fields_from_another_environment(monkeypatch):
    log_search = SimpleNamespace(
        log_collector_update_context=lambda **kwargs: {"bk_biz_id": 2, "environment": "windows"},
        fast_update_log_collector=lambda **kwargs: pytest.fail("update should not be requested"),
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    with pytest.raises(ValidationError, match="cannot be updated for a windows collector"):
        FastUpdateLogCollectorResource().perform_request(
            {"bk_biz_id": 2, "collector_config_id": 12, "configs": [{"path": "C:\\logs"}]}
        )


def test_rejects_cross_business_collector(monkeypatch):
    log_search = SimpleNamespace(
        log_collector_update_context=lambda **kwargs: {"bk_biz_id": 3, "environment": "linux"},
        fast_update_log_collector=lambda **kwargs: pytest.fail("update should not be requested"),
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    with pytest.raises(PermissionDenied):
        FastUpdateLogCollectorResource().perform_request(
            {"bk_biz_id": 2, "collector_config_id": 13, "description": "new"}
        )


def test_metadata_update_does_not_return_stale_tasks(monkeypatch):
    log_search = SimpleNamespace(
        log_collector_update_context=lambda **kwargs: {
            "bk_biz_id": 2,
            "environment": "linux",
            "subscription_id": 21,
        },
        data_bus_collectors=lambda **kwargs: pytest.fail("detail fallback should not be requested"),
        fast_update_log_collector=lambda **kwargs: {"collector_config_id": 14},
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    result = FastUpdateLogCollectorResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 14, "description": "new"}
    )

    assert result["subscription_id"] == 21
    assert result["task_ids"] == []


def test_deployment_update_falls_back_to_latest_detail_for_old_backend_response(monkeypatch):
    calls = {"detail": 0}
    log_search = SimpleNamespace(
        log_collector_update_context=lambda **kwargs: {
            "bk_biz_id": 2,
            "environment": "linux",
            "subscription_id": 21,
        },
        data_bus_collectors=lambda **kwargs: (
            calls.update(detail=calls["detail"] + 1) or {"subscription_id": 21, "task_id_list": "41,42"}
        ),
        fast_update_log_collector=lambda **kwargs: {"collector_config_id": 14},
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    result = FastUpdateLogCollectorResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 14, "target_nodes": [{"bk_host_id": 1}]}
    )

    assert calls["detail"] == 1
    assert result["subscription_id"] == 21
    assert result["task_ids"] == ["41", "42"]
