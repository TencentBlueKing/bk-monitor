from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import PermissionDenied

from bkmonitor.iam import ActionEnum
from core.drf_resource import api
from kernel_api.resource.log_collection import (
    GetLogCollectorResource,
    GetLogIndexSetResource,
    ListLogCollectorsResource,
    mask_sensitive,
    normalize_environment,
    normalize_index_set,
)
from kernel_api.views.v4.log_collection import CanonicalBusinessActionPermission, LogCollectionViewSet


@pytest.mark.parametrize(
    ("collector", "expected"),
    [
        ({"environment": "linux", "collector_scenario_id": "row"}, "linux"),
        ({"environment": "windows", "collector_scenario_id": "wineventlog"}, "windows"),
        ({"environment": "container", "bcs_cluster_id": "BCS-K8S-00000"}, "container"),
        ({"environment": None, "collector_scenario_id": "section"}, "linux"),
        ({"environment": None, "collector_scenario_id": "wineventlog"}, "windows"),
        ({"environment": None, "bcs_cluster_id": "0", "collector_scenario_id": "row"}, "linux"),
        ({"environment": None, "collector_scenario_id": "custom", "custom_type": "log"}, "container"),
        ({"environment": "linux", "collector_scenario_id": "custom", "custom_type": "log"}, "container"),
        ({"environment": None, "collector_scenario_id": "custom"}, "unknown"),
    ],
)
def test_normalize_environment(collector, expected):
    assert normalize_environment(collector) == expected


def test_list_request_serializer_defaults_and_bounds_page_size():
    serializer = ListLogCollectorsResource.RequestSerializer(data={"bk_biz_id": 7})
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["page"] == 1
    assert serializer.validated_data["page_size"] == 20

    serializer = ListLogCollectorsResource.RequestSerializer(data={"bk_biz_id": 7, "page_size": 101})
    assert not serializer.is_valid()
    assert "page_size" in serializer.errors


def test_list_request_serializer_excludes_frontend_only_index_set_filters():
    serializer = ListLogCollectorsResource.RequestSerializer()

    assert {"parent_index_set_id", "exclude_parent_index_set_id"}.isdisjoint(serializer.fields)


@pytest.mark.parametrize("action", ["list_collectors", "get_collector", "get_index_set", "list_index_set_groups"])
def test_log_collection_view_requires_view_business_permission(action):
    view = LogCollectionViewSet()
    view.action = action
    permissions = view.get_permissions()

    assert len(permissions) == 1
    assert permissions[0].actions == [ActionEnum.VIEW_BUSINESS]


def test_log_collection_permission_rejects_conflicting_business_alias():
    permission = CanonicalBusinessActionPermission([ActionEnum.VIEW_BUSINESS])
    request = SimpleNamespace(
        query_params={"bk_biz_id": "2", "biz_id": "3"},
        biz_id="3",
    )

    assert permission.has_permission(request, None) is False


def test_mask_sensitive_handles_common_credential_keys_recursively():
    assert mask_sensitive(
        {
            "api_key": "key",
            "nested": {
                "Authorization": "Bearer token",
                "items": [{"access_key_id": "id"}, {"normal": "visible"}],
            },
        }
    ) == {
        "api_key": "******",
        "nested": {
            "Authorization": "******",
            "items": [{"access_key_id": "******"}, {"normal": "visible"}],
        },
    }


def test_normalize_index_set_preserves_unknown_searchability():
    assert normalize_index_set({"index_set_id": 301})["is_searchable"] is None
    assert normalize_index_set({"index_set_id": 301, "is_search": True})["is_searchable"] is True
    assert normalize_index_set({"index_set_id": 301, "is_search": False})["is_searchable"] is False


def test_list_collectors_uses_mixed_api_pagination_and_normalizes_response(monkeypatch):
    api_resource = Mock(
        return_value={
            "total": 3,
            "list": [
                {
                    "collector_config_id": 101,
                    "collector_config_name": "linux-app",
                    "bk_biz_id": 7,
                    "environment": None,
                    "collector_scenario_id": "row",
                    "collector_scenario_name": "行日志文件",
                    "is_active": True,
                    "bk_data_id": 1500101,
                    "subscription_id": 201,
                    "index_set_id": 301,
                    "table_id_prefix": "7_bklog_",
                    "table_id": "linux_app",
                    "is_search": True,
                    "bkdata_index_set_ids": [401],
                    "created_at": "2026-08-10 10:00:00",
                    "updated_at": "2026-08-11 10:00:00",
                },
                {
                    "collector_config_id": 102,
                    "collector_config_name": "windows-event",
                    "bk_biz_id": 7,
                    "collector_scenario_id": "wineventlog",
                    "collector_scenario_name": "win event日志",
                    "is_active": False,
                    "index_set_id": None,
                },
                {
                    "collector_config_id": 103,
                    "collector_config_name": "container-stdout",
                    "bk_biz_id": 7,
                    "environment": "container",
                    "bcs_cluster_id": "BCS-K8S-00000",
                    "collector_scenario_id": "row",
                    "collector_scenario_name": "行日志文件",
                    "is_active": True,
                },
            ],
        }
    )
    monkeypatch.setattr(api.log_search, "log_access_collector", api_resource)
    serializer = ListLogCollectorsResource.RequestSerializer(
        data={
            "bk_biz_id": 7,
            "page": 1,
            "page_size": 10,
            "keyword": "app",
            "collector_scenario_id": "row",
        }
    )

    assert serializer.is_valid(), serializer.errors
    result = ListLogCollectorsResource().perform_request(serializer.validated_data)

    assert result["page"] == 1
    assert result["page_size"] == 10
    assert result["total"] == 3
    assert result["total_pages"] == 1
    assert [item["environment"] for item in result["items"]] == ["linux", "windows", "container"]
    assert result["items"][0]["status"] == "enabled"
    assert result["items"][0]["index_set"] == {
        "index_set_id": 301,
        "table_id_prefix": "7_bklog_",
        "table_id": "linux_app",
        "is_searchable": True,
        "bkdata_index_set_ids": [401],
    }
    api_resource.assert_called_once_with(
        space_uid="bkcc__7",
        page=1,
        pagesize=10,
        keyword="app",
        ordering="-updated_at",
        conditions=[{"key": "collector_scenario_id", "value": ["row"]}],
    )


def test_list_collectors_uses_mixed_log_access_api_for_es_and_custom_report(monkeypatch):
    api_resource = Mock(
        return_value={
            "total": 2,
            "list": [
                {
                    "index_set_id": 301,
                    "index_set_name": "third-party-es",
                    "scenario_id": "es",
                    "is_active": True,
                    "log_access_type": "es",
                },
                {
                    "collector_config_id": 302,
                    "collector_config_name": "custom-report",
                    "collector_scenario_id": "custom",
                    "custom_type": "log",
                    "is_active": True,
                    "log_access_type": "custom_report",
                },
            ],
        }
    )
    monkeypatch.setattr(api.log_search, "log_access_collector", api_resource)

    result = ListLogCollectorsResource().perform_request(
        {
            "bk_biz_id": 7,
            "page": 1,
            "page_size": 20,
            "keyword": "",
            "log_access_type": ["es", "custom_report"],
        }
    )

    assert [item["log_access_type"] for item in result["items"]] == ["es", "custom_report"]
    assert result["items"][0]["collector_config_id"] is None
    assert result["items"][0]["bk_biz_id"] == 7
    api_resource.assert_called_once_with(
        space_uid="bkcc__7",
        page=1,
        pagesize=20,
        keyword="",
        ordering="-updated_at",
        conditions=[{"key": "log_access_type", "value": ["es", "custom_report"]}],
    )


def test_list_collectors_supports_bkdata_index_sets(monkeypatch):
    api_resource = Mock(
        return_value={
            "total": 1,
            "list": [
                {
                    "index_set_id": 401,
                    "index_set_name": "bkdata-result-table",
                    "scenario_id": "bkdata",
                    "is_active": True,
                    "log_access_type": "bkdata",
                }
            ],
        }
    )
    monkeypatch.setattr(api.log_search, "log_access_collector", api_resource)

    serializer = ListLogCollectorsResource.RequestSerializer(data={"bk_biz_id": 7, "log_access_type": ["bkdata"]})
    assert serializer.is_valid(), serializer.errors

    result = ListLogCollectorsResource().perform_request(serializer.validated_data)

    assert result["total"] == 1
    assert result["items"][0]["log_access_type"] == "bkdata"
    assert result["items"][0]["index_set"]["index_set_id"] == 401
    api_resource.assert_called_once_with(
        space_uid="bkcc__7",
        page=1,
        pagesize=20,
        keyword="",
        ordering="-updated_at",
        conditions=[{"key": "log_access_type", "value": ["bkdata"]}],
    )


def test_get_collector_normalizes_detail_and_omits_unrelated_raw_fields(monkeypatch):
    api_resource = Mock(
        return_value={
            "collector_config_id": 101,
            "collector_config_name": "container-app",
            "bk_biz_id": 7,
            "environment": "container",
            "bcs_cluster_id": "BCS-K8S-00000",
            "collector_scenario_id": "row",
            "collector_scenario_name": "行日志文件",
            "is_active": True,
            "description": "container logs",
            "log_access_type": "container_stdout",
            "category_id": "application",
            "category_name": "应用程序",
            "target_object_type": "CONTAINER",
            "target_node_type": "TOPO",
            "target_nodes": '[{"bk_obj_id": "namespace", "bk_inst_id": 1}]',
            "data_encoding": "UTF-8",
            "params": (
                '{"paths": ["/var/log/app.log"], "password": "plain-password", '
                '"nested": {"bearer_token": "token-value"}, '
                '"kafka_ssl_params": "{\\"sasl_passwd\\": \\"kafka-password\\", \\"mechanism\\": \\"PLAIN\\"}"}'
            ),
            "configs": [
                {
                    "id": 901,
                    "collector_type": "container_log_config",
                    "namespaces": ["default"],
                    "workload_type": "Deployment",
                    "workload_name": "api",
                    "params": {"paths": ["/var/log/app.log"], "sasl_passwd": "container-password"},
                    "raw_config": {"must": "not leak"},
                }
            ],
            "etl_config": "bk_log_json",
            "etl_params": '{"retain_original_text": true}',
            "fields": '[{"field_name": "level", "field_type": "string"}]',
            "storage_cluster_id": 501,
            "storage_cluster_name": "es-log",
            "storage_display_name": "日志 ES",
            "storage_cluster_type": "elasticsearch",
            "retention": 7,
            "index_set_id": 301,
            "table_id_prefix": "7_bklog_",
            "table_id": "container_app",
            "is_search": True,
            "kafka_password": "must-not-leak",
        }
    )
    monkeypatch.setattr(api.log_search, "data_bus_collectors", api_resource)

    result = GetLogCollectorResource().perform_request({"bk_biz_id": 7, "collector_config_id": 101})

    assert result["environment"] == "container"
    assert result["target"]["nodes"] == [{"bk_obj_id": "namespace", "bk_inst_id": 1}]
    assert result["collection_config"]["params"] == {
        "paths": ["/var/log/app.log"],
        "password": "******",
        "nested": {"bearer_token": "******"},
        "kafka_ssl_params": {"sasl_passwd": "******", "mechanism": "PLAIN"},
    }
    assert result["collection_config"]["configs"] == [
        {
            "id": 901,
            "collector_type": "container_log_config",
            "namespaces": ["default"],
            "workload_type": "Deployment",
            "workload_name": "api",
            "params": {"paths": ["/var/log/app.log"], "sasl_passwd": "******"},
        }
    ]
    assert result["clean_config"]["etl_params"] == {"retain_original_text": True}
    assert result["clean_config"]["fields"] == [{"field_name": "level", "field_type": "string"}]
    assert result["storage"]["cluster_id"] == 501
    assert "kafka_password" not in result
    api_resource.assert_called_once_with(collector_config_id=101, enforce_permission=True)


def test_get_collector_rejects_cross_business_result(monkeypatch):
    monkeypatch.setattr(
        api.log_search,
        "data_bus_collectors",
        Mock(return_value={"collector_config_id": 101, "bk_biz_id": 8}),
    )

    with pytest.raises(PermissionDenied):
        GetLogCollectorResource().perform_request({"bk_biz_id": 7, "collector_config_id": 101})


def test_get_index_set_returns_detail_from_new_api(monkeypatch):
    detail = {
        "index_set_id": 301,
        "index_set_name": "third-party-es",
        "scenario_id": "es",
        "space_uid": "bkcc__7",
        "indexes": [{"result_table_id": "logs-*", "time_field": "@timestamp"}],
    }
    get_index_set = Mock(return_value=detail)
    monkeypatch.setattr(api.log_search, "get_index_set", get_index_set)

    result = GetLogIndexSetResource().perform_request({"bk_biz_id": 7, "index_set_id": 301})

    assert result is detail
    get_index_set.assert_called_once_with(index_set_id=301)


def test_get_index_set_rejects_cross_business_result(monkeypatch):
    get_index_set = Mock(return_value={"index_set_id": 301, "space_uid": "bkcc__8"})
    monkeypatch.setattr(api.log_search, "get_index_set", get_index_set)

    with pytest.raises(PermissionDenied):
        GetLogIndexSetResource().perform_request({"bk_biz_id": 7, "index_set_id": 301})

    get_index_set.assert_called_once_with(index_set_id=301)
