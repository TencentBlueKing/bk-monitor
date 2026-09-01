from types import SimpleNamespace
from unittest.mock import Mock

from core.drf_resource import api
from kernel_api.resource import log_collection_special_create as special_create_module
from kernel_api.resource.log_collection_special_create import (
    CreateCustomReportResource,
    CreateThirdPartyESResource,
)
from kernel_api.resource.log_index_set import ListLogIndexSetGroupsResource


def test_list_index_set_groups_only_returns_groups(monkeypatch):
    search_index_set = Mock(
        return_value=[
            {"index_set_id": 11, "index_set_name": "group", "space_uid": "bkcc__2", "is_group": True},
            {"index_set_id": 12, "index_set_name": "child", "space_uid": "bkcc__2", "is_group": False},
        ]
    )
    monkeypatch.setattr(api.log_search, "search_index_set", search_index_set)

    result = ListLogIndexSetGroupsResource().perform_request({"bk_biz_id": 2})

    assert result == {
        "groups": [{"index_set_id": 11, "index_set_name": "group", "space_uid": "bkcc__2", "is_group": True}]
    }
    search_index_set.assert_called_once_with(bk_biz_id=2, is_group=True)


def test_create_custom_report_forwards_parent_index_set_ids(monkeypatch):
    create_custom_report = Mock(
        return_value={"collector_config_id": 21, "index_set_id": 31, "bk_data_id": 41, "created": True}
    )
    monkeypatch.setattr(
        special_create_module,
        "api",
        SimpleNamespace(log_search=SimpleNamespace(create_custom_report=create_custom_report)),
    )
    serializer = CreateCustomReportResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "collector_config_name": "custom",
            "collector_config_name_en": "custom_report",
            "custom_type": "log",
            "parent_index_set_ids": [11, 12],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    result = CreateCustomReportResource().perform_request(serializer.validated_data)

    assert result["collector_config_id"] == 21
    assert result["parent_index_set_ids"] == [11, 12]
    assert create_custom_report.call_args.kwargs["parent_index_set_ids"] == [11, 12]
    assert "parent_index_set_id" not in create_custom_report.call_args.kwargs
    assert "confirm" not in create_custom_report.call_args.kwargs


def test_create_third_party_es_forwards_space_and_parent_index_set_ids(monkeypatch):
    create_index_set = Mock(
        return_value={
            "index_set_id": 51,
            "index_set_name": "external-es",
            "scenario_id": "es",
            "storage_cluster_id": 61,
        }
    )
    monkeypatch.setattr(
        special_create_module,
        "api",
        SimpleNamespace(log_search=SimpleNamespace(create_index_set=create_index_set)),
    )
    serializer = CreateThirdPartyESResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_name": "external-es",
            "storage_cluster_id": 61,
            "indexes": [{"result_table_id": "logs-*"}],
            "time_field": "@timestamp",
            "parent_index_set_ids": [11, 12],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    result = CreateThirdPartyESResource().perform_request(serializer.validated_data)

    assert result["index_set_id"] == 51
    assert create_index_set.call_args.kwargs["space_uid"] == "bkcc__2"
    assert create_index_set.call_args.kwargs["scenario_id"] == "es"
    assert create_index_set.call_args.kwargs["parent_index_set_ids"] == [11, 12]
    assert "parent_index_set_id" not in create_index_set.call_args.kwargs
