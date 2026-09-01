from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from bkmonitor.iam import ActionEnum
from core.drf_resource import api
from kernel_api.resource.log_collection_clean_config import (
    SUPPORTED_ETL_CONFIGS,
    UpdateLogCollectorCleanConfigResource,
    build_clean_config_readback,
)
from kernel_api.views.v4.log_collection_clean_config import (
    CanonicalBusinessActionPermission,
    LogCollectionCleanConfigViewSet,
)


def build_request_data(**overrides):
    data = {
        "bk_biz_id": 7,
        "collector_config_id": 101,
        "table_id": "app_log",
        "etl_config": "bk_log_text",
        "etl_params": {},
        "fields": [],
        "storage_cluster_id": 501,
        "retention": 7,
        "allocation_min_days": 0,
        "storage_replies": 0,
        "es_shards": 1,
        "confirm": True,
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize(
    "field",
    [
        "etl_config",
        "etl_params",
        "fields",
        "storage_cluster_id",
        "retention",
        "allocation_min_days",
        "storage_replies",
        "es_shards",
    ],
)
def test_request_serializer_rejects_missing_clean_or_storage_fields(field):
    data = build_request_data()
    data.pop(field)

    serializer = UpdateLogCollectorCleanConfigResource.RequestSerializer(data=data)

    assert not serializer.is_valid()
    assert field in serializer.errors


def test_request_serializer_requires_explicit_confirmation():
    serializer = UpdateLogCollectorCleanConfigResource.RequestSerializer(data=build_request_data(confirm=False))

    assert not serializer.is_valid()
    assert "confirm" in serializer.errors


def test_request_serializer_preserves_explicit_empty_zero_and_false_values():
    serializer = UpdateLogCollectorCleanConfigResource.RequestSerializer(
        data=build_request_data(
            etl_config="bk_log_delimiter",
            etl_params={"separator": "", "retain_original_text": False},
            fields=[
                {
                    "field_index": 0,
                    "field_name": "",
                    "field_type": "",
                    "is_analyzed": False,
                    "is_delete": True,
                    "value": 0,
                }
            ],
            allocation_min_days=0,
            storage_replies=0,
        )
    )

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["etl_params"] == {
        "separator": "",
        "retain_original_text": False,
    }
    assert serializer.validated_data["fields"][0]["field_index"] == 0
    assert serializer.validated_data["fields"][0]["is_analyzed"] is False
    assert serializer.validated_data["fields"][0]["value"] == 0
    assert serializer.validated_data["allocation_min_days"] == 0
    assert serializer.validated_data["storage_replies"] == 0


def test_request_serializer_rejects_template_and_custom_clean_capabilities():
    template_serializer = UpdateLogCollectorCleanConfigResource.RequestSerializer(
        data=build_request_data(template_id=123)
    )
    custom_serializer = UpdateLogCollectorCleanConfigResource.RequestSerializer(
        data=build_request_data(etl_config="custom")
    )

    assert not template_serializer.is_valid()
    assert "template_id" in template_serializer.errors
    assert not custom_serializer.is_valid()
    assert "etl_config" in custom_serializer.errors
    assert "custom" not in SUPPORTED_ETL_CONFIGS


def test_update_clean_config_forwards_complete_payload_and_returns_readback(monkeypatch):
    before = {"collector_config_id": 101, "bk_biz_id": 7, "table_id": "app_log"}
    after = {
        "collector_config_id": 101,
        "bk_biz_id": 7,
        "etl_config": "bk_log_delimiter",
        "etl_params": '{"separator": "", "retain_original_text": false}',
        "fields": '[{"field_name": "message", "field_type": "string", "is_delete": false}]',
        "storage_cluster_id": 501,
        "storage_cluster_name": "es-log",
        "storage_display_name": "日志 ES",
        "storage_cluster_type": "elasticsearch",
        "retention": 7,
        "allocation_min_days": 0,
        "storage_replies": 0,
        "storage_shards_nums": 1,
        "index_set_id": 301,
        "table_id_prefix": "7_bklog_",
        "table_id": "app_log",
        "sort_fields": '["dtEventTimeStamp"]',
        "target_fields": [],
    }
    get_collector = Mock(side_effect=[before, after])
    update_clean_config = Mock(
        return_value={
            "etl_config": "bk_log_delimiter",
            "index_set_id": 301,
            "scenario_id": "log",
            "storage_cluster_id": 501,
            "retention": 7,
            "es_shards": 1,
        }
    )
    monkeypatch.setattr(api.log_search, "data_bus_collectors", get_collector)
    monkeypatch.setattr(api.log_search, "update_log_collector_clean_config", update_clean_config)
    monkeypatch.setattr(
        "kernel_api.resource.log_collection_clean_config.get_request_username",
        lambda: "alice",
    )
    serializer = UpdateLogCollectorCleanConfigResource.RequestSerializer(
        data=build_request_data(
            etl_config="bk_log_delimiter",
            etl_params={"separator": "", "retain_original_text": False},
            fields=[
                {
                    "field_name": "message",
                    "field_type": "string",
                    "is_delete": False,
                    "is_analyzed": False,
                }
            ],
        )
    )
    assert serializer.is_valid(), serializer.errors

    result = UpdateLogCollectorCleanConfigResource().perform_request(serializer.validated_data)

    update_clean_config.assert_called_once_with(
        collector_config_id=101,
        enforce_permission=True,
        bk_username="alice",
        table_id="app_log",
        etl_config="bk_log_delimiter",
        etl_params={"separator": "", "retain_original_text": False},
        fields=[
            {
                "field_name": "message",
                "field_type": "string",
                "is_delete": False,
                "is_analyzed": False,
            }
        ],
        storage_cluster_id=501,
        retention=7,
        allocation_min_days=0,
        storage_replies=0,
        es_shards=1,
    )
    assert get_collector.call_count == 2
    assert result["requested_by"] == "alice"
    assert result["readback"]["clean_config"]["etl_params"]["retain_original_text"] is False
    assert result["readback"]["storage"]["allocation_min_days"] == 0
    assert result["readback"]["storage"]["storage_replies"] == 0
    assert result["readback"]["index_set"]["index_set_id"] == 301
    assert result["status_query"] == {
        "tool": "get_log_collector",
        "arguments": {"bk_biz_id": 7, "collector_config_id": 101},
        "retry_after_seconds": 5,
    }


def test_update_clean_config_rejects_cross_business_before_write(monkeypatch):
    monkeypatch.setattr(
        api.log_search,
        "data_bus_collectors",
        Mock(return_value={"collector_config_id": 101, "bk_biz_id": 8}),
    )
    update_clean_config = Mock()
    monkeypatch.setattr(api.log_search, "update_log_collector_clean_config", update_clean_config)
    monkeypatch.setattr(
        "kernel_api.resource.log_collection_clean_config.get_request_username",
        lambda: "alice",
    )

    with pytest.raises(PermissionDenied):
        UpdateLogCollectorCleanConfigResource().perform_request(build_request_data())

    update_clean_config.assert_not_called()


def test_update_clean_config_rejects_result_table_rename_before_write(monkeypatch):
    monkeypatch.setattr(
        api.log_search,
        "data_bus_collectors",
        Mock(return_value={"collector_config_id": 101, "bk_biz_id": 7, "table_id": "current_table"}),
    )
    update_clean_config = Mock()
    monkeypatch.setattr(api.log_search, "update_log_collector_clean_config", update_clean_config)
    monkeypatch.setattr(
        "kernel_api.resource.log_collection_clean_config.get_request_username",
        lambda: "alice",
    )

    with pytest.raises(ValidationError, match="cannot rename"):
        UpdateLogCollectorCleanConfigResource().perform_request(build_request_data(table_id="new_table"))

    update_clean_config.assert_not_called()


def test_update_clean_config_requires_resolved_request_user(monkeypatch):
    monkeypatch.setattr(
        "kernel_api.resource.log_collection_clean_config.get_request_username",
        lambda: "",
    )
    get_collector = Mock()
    monkeypatch.setattr(api.log_search, "data_bus_collectors", get_collector)

    with pytest.raises(PermissionDenied):
        UpdateLogCollectorCleanConfigResource().perform_request(build_request_data())

    get_collector.assert_not_called()


def test_clean_config_view_requires_log_collection_mcp_permission():
    permissions = LogCollectionCleanConfigViewSet().get_permissions()

    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.USING_LOG_COLLECTION_MCP]


def test_clean_config_permission_rejects_conflicting_business_context():
    permission = CanonicalBusinessActionPermission([ActionEnum.USING_LOG_COLLECTION_MCP])
    request = SimpleNamespace(
        method="POST",
        data={"bk_biz_id": 7},
        query_params={},
        biz_id=8,
    )

    assert permission.has_permission(request, None) is False


def test_build_clean_config_readback_handles_non_json_values_without_leaking_unrelated_fields():
    result = build_clean_config_readback(
        {
            "collector_config_id": 101,
            "bk_biz_id": 7,
            "etl_params": "not-json",
            "fields": None,
            "raw_config": {"template_id": 1},
        }
    )

    assert result["clean_config"]["etl_params"] == {}
    assert result["clean_config"]["fields"] == []
    assert "raw_config" not in result
