"""日志采集 Fast Update MCP 资源测试。"""

from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from bkmonitor.iam import ActionEnum
from kernel_api.resource import log_collection_update as update_module
from kernel_api.resource.log_collection_update import FastUpdateLogCollectorResource
from kernel_api.views.v4.log_collection_update import LogCollectionUpdateViewSet


@pytest.mark.parametrize("field", ["environment", "etl_config", "fields", "storage_cluster_id"])
def test_serializer_rejects_environment_clean_and_storage_fields(field):
    serializer = FastUpdateLogCollectorResource.RequestSerializer(
        data={"bk_biz_id": 2, "collector_config_id": 1, "description": "new", field: "forbidden"}
    )
    assert not serializer.is_valid()
    assert field in serializer.errors


def test_serializer_requires_at_least_one_update_field():
    serializer = FastUpdateLogCollectorResource.RequestSerializer(
        data={"bk_biz_id": 2, "collector_config_id": 1}
    )
    assert not serializer.is_valid()
    assert "non_field_errors" in serializer.errors


def test_update_view_requires_manage_collection_permission():
    permissions = LogCollectionUpdateViewSet().get_permissions()
    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.MANAGE_COLLECTION]


def test_host_update_injects_clean_switch_and_returns_tasks(monkeypatch):
    captured = {}

    def fast_update(**kwargs):
        captured.update(kwargs)
        return {"collector_config_id": 10, "subscription_id": 20, "task_id_list": [30]}

    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {"bk_biz_id": 2, "environment": "linux"},
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


def test_container_update_uses_container_fields(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {
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


def test_rejects_fields_from_another_environment(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {"bk_biz_id": 2, "environment": "windows"},
        fast_update_log_collector=lambda **kwargs: pytest.fail("update should not be requested"),
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    with pytest.raises(ValidationError, match="cannot be updated for a windows collector"):
        FastUpdateLogCollectorResource().perform_request(
            {"bk_biz_id": 2, "collector_config_id": 12, "configs": [{"path": "C:\\logs"}]}
        )


def test_rejects_cross_business_collector(monkeypatch):
    log_search = SimpleNamespace(
        data_bus_collectors=lambda **kwargs: {"bk_biz_id": 3, "environment": "linux"},
        fast_update_log_collector=lambda **kwargs: pytest.fail("update should not be requested"),
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    with pytest.raises(PermissionDenied):
        FastUpdateLogCollectorResource().perform_request(
            {"bk_biz_id": 2, "collector_config_id": 13, "description": "new"}
        )


def test_falls_back_to_latest_detail_for_old_backend_response(monkeypatch):
    calls = {"detail": 0}

    def detail(**kwargs):
        calls["detail"] += 1
        if calls["detail"] == 1:
            return {"bk_biz_id": 2, "environment": "linux"}
        return {"bk_biz_id": 2, "environment": "linux", "subscription_id": 21, "task_id_list": "41,42"}

    log_search = SimpleNamespace(
        data_bus_collectors=detail,
        fast_update_log_collector=lambda **kwargs: {"collector_config_id": 14},
    )
    monkeypatch.setattr(update_module, "api", SimpleNamespace(log_search=log_search))

    result = FastUpdateLogCollectorResource().perform_request(
        {"bk_biz_id": 2, "collector_config_id": 14, "description": "new"}
    )

    assert calls["detail"] == 2
    assert result["subscription_id"] == 21
    assert result["task_ids"] == ["41", "42"]
