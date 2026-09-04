from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from rest_framework.exceptions import PermissionDenied, ValidationError

from kernel_api.resource import log_collection_special_update as special_update_module
from kernel_api.resource.log_collection_special_update import (
    UpdateBkDataResource,
    UpdateCustomReportResource,
    UpdateThirdPartyESResource,
)


@pytest.mark.parametrize(
    "serializer_class",
    [
        UpdateCustomReportResource.RequestSerializer,
        UpdateThirdPartyESResource.RequestSerializer,
        UpdateBkDataResource.RequestSerializer,
    ],
)
def test_update_business_ids_allow_negative_business_ids(serializer_class):
    assert serializer_class().fields["bk_biz_id"].run_validation(-2) == -2


def test_update_custom_report_forwards_parent_index_set_ids(monkeypatch):
    update_custom_report = Mock(return_value=True)
    monkeypatch.setattr(
        special_update_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                data_bus_collectors=Mock(
                    return_value={
                        "bk_biz_id": 2,
                        "collector_scenario_id": "custom",
                        "custom_type": "log",
                    }
                ),
                update_custom_report=update_custom_report,
            )
        ),
    )
    serializer = UpdateCustomReportResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "collector_config_id": 21,
            "collector_config_name": "custom",
            "parent_index_set_ids": [11, 12],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    result = UpdateCustomReportResource().perform_request(serializer.validated_data)

    assert result == {
        "collector_config_id": 21,
        "updated": True,
    }
    assert update_custom_report.call_args.kwargs["parent_index_set_ids"] == [11, 12]
    assert update_custom_report.call_args.kwargs["enforce_permission"] is True


def test_update_third_party_es_forwards_space_and_parent_index_set_ids(monkeypatch):
    update_index_set = Mock(
        return_value={
            "index_set_id": 51,
            "index_set_name": "external-es-updated",
            "scenario_id": "es",
            "space_uid": "bkcc__2",
            "storage_cluster_id": 61,
        }
    )
    monkeypatch.setattr(
        special_update_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                get_index_set=Mock(return_value={"index_set_id": 51, "scenario_id": "es", "space_uid": "bkcc__2"}),
                update_index_set=update_index_set,
            )
        ),
    )
    serializer = UpdateThirdPartyESResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_id": 51,
            "index_set_name": "external-es-updated",
            "storage_cluster_id": 61,
            "indexes": [{"result_table_id": "logs-*"}],
            "time_field": "@timestamp",
            "time_field_type": "date",
            "time_field_unit": None,
            "category_id": "application",
            "is_trace_log": False,
            "target_fields": [],
            "sort_fields": [],
            "parent_index_set_ids": [11, 12],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    result = UpdateThirdPartyESResource().perform_request(serializer.validated_data)

    assert result["index_set_id"] == 51
    assert update_index_set.call_args.kwargs["space_uid"] == "bkcc__2"
    assert update_index_set.call_args.kwargs["scenario_id"] == "es"
    assert update_index_set.call_args.kwargs["indexes"] == [{"result_table_id": "logs-*", "bk_biz_id": 2}]
    assert update_index_set.call_args.kwargs["parent_index_set_ids"] == [11, 12]
    assert update_index_set.call_args.kwargs["enforce_permission"] is True


def test_update_third_party_es_leaves_parent_index_set_ids_unchanged_when_omitted(monkeypatch):
    update_index_set = Mock(return_value={})
    monkeypatch.setattr(
        special_update_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                get_index_set=Mock(return_value={"index_set_id": 51, "scenario_id": "es", "space_uid": "bkcc__2"}),
                update_index_set=update_index_set,
            )
        ),
    )
    serializer = UpdateThirdPartyESResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_id": 51,
            "index_set_name": "external-es-updated",
            "storage_cluster_id": 61,
            "indexes": [{"result_table_id": "logs-*"}],
            "time_field": "@timestamp",
            "time_field_type": "date",
            "time_field_unit": None,
            "category_id": "application",
            "is_trace_log": False,
            "target_fields": [],
            "sort_fields": [],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    UpdateThirdPartyESResource().perform_request(serializer.validated_data)

    assert "parent_index_set_ids" not in update_index_set.call_args.kwargs


def test_update_bkdata_forwards_space_and_result_tables(monkeypatch):
    update_index_set = Mock(
        return_value={
            "index_set_id": 61,
            "index_set_name": "bkdata-updated",
            "scenario_id": "bkdata",
            "space_uid": "bkcc__2",
        }
    )
    monkeypatch.setattr(
        special_update_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                get_index_set=Mock(return_value={"index_set_id": 61, "scenario_id": "bkdata", "space_uid": "bkcc__2"}),
                update_index_set=update_index_set,
            )
        ),
    )
    serializer = UpdateBkDataResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_id": 61,
            "index_set_name": "bkdata-updated",
            "indexes": [{"result_table_id": "2_rt_a"}],
            "time_field": "dtEventTime",
            "time_field_type": "date",
            "time_field_unit": None,
            "category_id": "application",
            "is_trace_log": True,
            "target_fields": ["host"],
            "sort_fields": ["dtEventTime"],
            "parent_index_set_ids": [11],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    result = UpdateBkDataResource().perform_request(serializer.validated_data)

    assert result["index_set_id"] == 61
    assert update_index_set.call_args.kwargs["space_uid"] == "bkcc__2"
    assert update_index_set.call_args.kwargs["scenario_id"] == "bkdata"
    assert update_index_set.call_args.kwargs["indexes"] == [{"result_table_id": "2_rt_a", "bk_biz_id": 2}]
    assert update_index_set.call_args.kwargs["parent_index_set_ids"] == [11]
    assert update_index_set.call_args.kwargs["category_id"] == "application"
    assert update_index_set.call_args.kwargs["is_trace_log"] is True
    assert update_index_set.call_args.kwargs["time_field"] == "dtEventTime"
    assert update_index_set.call_args.kwargs["time_field_type"] == "date"
    assert update_index_set.call_args.kwargs["time_field_unit"] is None
    assert update_index_set.call_args.kwargs["target_fields"] == ["host"]
    assert update_index_set.call_args.kwargs["sort_fields"] == ["dtEventTime"]
    assert update_index_set.call_args.kwargs["enforce_permission"] is True


def test_update_index_set_rejects_cross_business_detail(monkeypatch):
    update_index_set = Mock()
    monkeypatch.setattr(
        special_update_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                get_index_set=Mock(return_value={"index_set_id": 51, "scenario_id": "es", "space_uid": "bkcc__3"}),
                update_index_set=update_index_set,
            )
        ),
    )
    serializer = UpdateThirdPartyESResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_id": 51,
            "index_set_name": "external-es",
            "storage_cluster_id": 61,
            "indexes": [{"result_table_id": "logs-*"}],
            "time_field": "@timestamp",
            "time_field_type": "date",
            "time_field_unit": None,
            "category_id": "application",
            "is_trace_log": False,
            "target_fields": [],
            "sort_fields": [],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    with pytest.raises(PermissionDenied):
        UpdateThirdPartyESResource().perform_request(serializer.validated_data)

    update_index_set.assert_not_called()


def test_update_index_set_rejects_access_type_mismatch(monkeypatch):
    update_index_set = Mock()
    monkeypatch.setattr(
        special_update_module,
        "api",
        SimpleNamespace(
            log_search=SimpleNamespace(
                get_index_set=Mock(return_value={"index_set_id": 51, "scenario_id": "bkdata", "space_uid": "bkcc__2"}),
                update_index_set=update_index_set,
            )
        ),
    )
    serializer = UpdateThirdPartyESResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_id": 51,
            "index_set_name": "not-es",
            "storage_cluster_id": 61,
            "indexes": [{"result_table_id": "logs-*"}],
            "time_field": "@timestamp",
            "time_field_type": "date",
            "time_field_unit": None,
            "category_id": "application",
            "is_trace_log": False,
            "target_fields": [],
            "sort_fields": [],
            "confirm": True,
        }
    )
    assert serializer.is_valid(), serializer.errors

    with pytest.raises(ValidationError):
        UpdateThirdPartyESResource().perform_request(serializer.validated_data)

    update_index_set.assert_not_called()


def test_update_bkdata_requires_time_field():
    serializer = UpdateBkDataResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_id": 61,
            "index_set_name": "bkdata",
            "indexes": [{"result_table_id": "2_rt_a"}],
            "confirm": True,
        }
    )

    assert not serializer.is_valid()
    assert "time_field" in serializer.errors


def test_update_bkdata_rejects_cross_business_index(monkeypatch):
    serializer = UpdateBkDataResource.RequestSerializer(
        data={
            "bk_biz_id": 2,
            "index_set_id": 61,
            "index_set_name": "bkdata",
            "indexes": [{"result_table_id": "3_rt_a", "bk_biz_id": 3}],
            "time_field": "dtEventTime",
            "time_field_type": "date",
            "time_field_unit": None,
            "category_id": "application",
            "is_trace_log": False,
            "target_fields": [],
            "sort_fields": [],
            "confirm": True,
        }
    )

    assert not serializer.is_valid()
    assert "indexes" in serializer.errors
