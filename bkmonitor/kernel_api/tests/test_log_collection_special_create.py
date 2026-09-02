from types import SimpleNamespace
from unittest.mock import Mock

from core.drf_resource import api
from kernel_api.resource import log_collection_special_create as special_create_module
from kernel_api.resource.log_collection_special_create import (
    CreateBkDataResource,
    CreateCustomReportResource,
    CreateThirdPartyESResource,
)
from kernel_api.resource import log_index_set as log_index_set_module
from kernel_api.resource.log_index_set import ListLogIndexSetGroupsResource


def test_list_index_set_groups_uses_dedicated_group_api(monkeypatch):
    expected_result = {
        "total": 1,
        "list": [{"index_set_id": 11, "index_set_name": "group", "index_count": 2}],
    }
    list_index_groups = Mock(return_value=expected_result)
    monkeypatch.setattr(api.log_search, "list_index_groups", list_index_groups)
    monkeypatch.setattr(log_index_set_module, "bk_biz_id_to_space_uid", lambda _: "bkcc__2")

    result = ListLogIndexSetGroupsResource().perform_request({"bk_biz_id": 2})

    assert result == expected_result
    list_index_groups.assert_called_once_with(space_uid="bkcc__2")


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

    assert result == {"collector_config_id": 21, "index_set_id": 31, "bk_data_id": 41, "created": True}
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
    assert create_index_set.call_args.kwargs["indexes"] == [{"result_table_id": "logs-*", "bk_biz_id": 2}]
    assert create_index_set.call_args.kwargs["parent_index_set_ids"] == [11, 12]
    assert "parent_index_set_id" not in create_index_set.call_args.kwargs


def test_create_third_party_es_explicit_null_biz_falls_back_to_outer(monkeypatch):
    """索引显式传 bk_biz_id=null 时应回落到外层业务ID，而不是把 None 透传给下游。"""
    create_index_set = Mock(return_value={"index_set_id": 51})
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
            "indexes": [
                {"result_table_id": "logs-*", "bk_biz_id": None},
                {"result_table_id": "logs-2024"},
            ],
            "time_field": "@timestamp",
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    CreateThirdPartyESResource().perform_request(serializer.validated_data)

    assert create_index_set.call_args.kwargs["indexes"] == [
        {"result_table_id": "logs-*", "bk_biz_id": 2},
        {"result_table_id": "logs-2024", "bk_biz_id": 2},
    ]


def test_create_bkdata_explicit_null_biz_falls_back_to_outer(monkeypatch):
    create_index_set = Mock(return_value={"index_set_id": 71})
    monkeypatch.setattr(
        special_create_module,
        "api",
        SimpleNamespace(log_search=SimpleNamespace(create_index_set=create_index_set)),
    )
    serializer = CreateBkDataResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_name": "bkdata-index-set",
            "indexes": [{"result_table_id": "2_demo_table", "bk_biz_id": None}],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    CreateBkDataResource().perform_request(serializer.validated_data)

    assert create_index_set.call_args.kwargs["indexes"] == [{"result_table_id": "2_demo_table", "bk_biz_id": 2}]


def test_create_bkdata_index_set_forwards_space_scenario_and_business(monkeypatch):
    create_index_set = Mock(
        return_value={
            "index_set_id": 71,
            "index_set_name": "bkdata-index-set",
            "scenario_id": "bkdata",
        }
    )
    monkeypatch.setattr(
        special_create_module,
        "api",
        SimpleNamespace(log_search=SimpleNamespace(create_index_set=create_index_set)),
    )
    serializer = CreateBkDataResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_name": "bkdata-index-set",
            "indexes": [{"result_table_id": "2_demo_table"}],
            "parent_index_set_ids": [11, 12],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    result = CreateBkDataResource().perform_request(serializer.validated_data)

    assert result["index_set_id"] == 71
    assert result["scenario_id"] == "bkdata"
    assert create_index_set.call_args.kwargs["space_uid"] == "bkcc__2"
    assert create_index_set.call_args.kwargs["scenario_id"] == "bkdata"
    assert create_index_set.call_args.kwargs["indexes"] == [{"result_table_id": "2_demo_table", "bk_biz_id": 2}]
    assert create_index_set.call_args.kwargs["parent_index_set_ids"] == [11, 12]
    assert create_index_set.call_args.kwargs["enforce_permission"] is True


def test_create_bkdata_index_set_rejects_cross_business_result_table(monkeypatch):
    serializer = CreateBkDataResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_name": "bkdata-index-set",
            "indexes": [{"result_table_id": "3_demo_table", "bk_biz_id": 3}],
            "confirm": True,
        }
    )

    assert not serializer.is_valid()
    assert "indexes" in serializer.errors
