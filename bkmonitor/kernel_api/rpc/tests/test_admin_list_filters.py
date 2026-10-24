"""Admin 核心资源列表多值过滤契约测试。"""

from unittest.mock import Mock, call

import pytest

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.functions.admin import cluster_info, custom_report, datasource
from kernel_api.rpc.functions.admin.common import (
    normalize_int_list_filter,
    normalize_string_list_filter,
)


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"bk_data_id": "50010"}, [50010]),
        ({"bk_data_ids": [50010, "50011"]}, [50010, 50011]),
        ({"bk_data_id": 50010, "bk_data_ids": [50011, 50010]}, [50010, 50011]),
    ],
)
def test_normalize_int_list_filter_merges_singular_and_plural(params, expected):
    assert normalize_int_list_filter(params, "bk_data_id", "bk_data_ids", positive=True) == expected


@pytest.mark.parametrize(
    "value",
    [None, "50010,50011", "", {}, (50010,), [50010, "abc"], [1.5], [True], [0], [-1]],
)
def test_normalize_int_list_filter_rejects_invalid_plural_values(value):
    with pytest.raises(CustomException):
        normalize_int_list_filter({"bk_data_ids": value}, "bk_data_id", "bk_data_ids", positive=True)


def test_normalize_int_list_filter_keeps_custom_report_csv_compatibility():
    assert normalize_int_list_filter(
        {"bk_data_ids": "50010,50011,50010"},
        "bk_data_id",
        "bk_data_ids",
        positive=True,
        allow_legacy_csv=True,
    ) == [50010, 50011]


def test_list_filter_normalizers_enforce_limits_and_string_items():
    with pytest.raises(CustomException, match="最多支持 100"):
        normalize_int_list_filter(
            {"ids": list(range(1, 102))},
            "id",
            "ids",
            positive=True,
        )
    with pytest.raises(CustomException, match="不能包含空值"):
        normalize_string_list_filter({"labels": ["normal", " "]}, "label", "labels")
    with pytest.raises(CustomException, match="必须是数组"):
        normalize_string_list_filter({"labels": None}, "label", "labels")
    with pytest.raises(CustomException, match="单项长度"):
        normalize_string_list_filter({"labels": ["x" * 256]}, "label", "labels")
    assert normalize_string_list_filter({"label": "normal", "labels": ["sleep", "normal"]}, "label", "labels") == [
        "normal",
        "sleep",
    ]


def test_datasource_plural_filters_use_in_and_fields_remain_and(monkeypatch):
    queryset = Mock()
    queryset.filter.return_value = queryset
    monkeypatch.setattr(datasource, "filter_by_bk_tenant_id", lambda _queryset, _tenant: queryset)

    datasource._build_datasource_queryset(
        {
            "bk_data_ids": [50010, 50011],
            "source_labels": ["bk_monitor", "custom"],
            "is_enable": True,
        },
        "system",
    )

    assert queryset.filter.call_args_list == [
        call(bk_data_id__in=[50010, 50011]),
        call(source_label__in=["bk_monitor", "custom"]),
        call(is_enable=True),
    ]


def test_cluster_info_plural_filters_use_in(monkeypatch):
    queryset = Mock()
    queryset.filter.return_value = queryset
    monkeypatch.setattr(cluster_info, "filter_by_bk_tenant_id", lambda _queryset, _tenant: queryset)

    cluster_info._build_cluster_info_queryset(
        {
            "cluster_ids": [1, 2],
            "cluster_types": ["kafka", "elasticsearch"],
            "registered_systems": ["bkmonitor", "bklog"],
        },
        "system",
    )

    assert queryset.filter.call_args_list == [
        call(cluster_id__in=[1, 2]),
        call(cluster_type__in=["kafka", "elasticsearch"]),
        call(registered_system__in=["bkmonitor", "bklog"]),
    ]


def test_custom_event_list_serializer_keeps_status():
    group = Mock(
        event_group_id=10,
        event_group_name="checkout",
        bk_tenant_id="system",
        bk_biz_id=2,
        bk_data_id=50010,
        table_id="2_bkmonitor_event.checkout",
        status="sleep",
        is_enable=True,
        last_modify_time=None,
        STORAGE_FIELD_LIST=[],
    )

    assert custom_report._serialize_event_group(group)["status"] == "sleep"


@pytest.mark.django_db(databases="__all__")
@pytest.mark.parametrize("params", [{"data_label": "alias"}, {"data_labels": ["missing", "alias"]}])
def test_admin_filters_match_any_array_label_and_ignore_legacy(params):
    from kernel_api.rpc.functions.admin import es_storage, result_table, storage

    from metadata import models

    table = models.ResultTable.objects.create(
        table_id="plugin.__default__",
        bk_tenant_id="labels_test",
        bk_biz_id=2,
        is_custom_table=False,
        data_labels=["primary", "alias"],
    )
    models.ResultTable.objects.filter(pk=table.pk).update(data_label="stale")
    models.ResultTable.objects.create(
        table_id="plugin.stale", bk_tenant_id=table.bk_tenant_id, is_custom_table=False, data_labels=["stale"]
    )
    models.ESStorage.objects.create(table_id=table.table_id, bk_tenant_id=table.bk_tenant_id, storage_cluster_id=0)
    assert list(
        result_table._build_result_table_queryset(params, table.bk_tenant_id).values_list("table_id", flat=True)
    ) == [table.table_id]
    assert storage._table_ids_by_data_filters(params, table.bk_tenant_id) == {table.table_id}
    assert list(
        es_storage._build_es_storage_queryset(params, table.bk_tenant_id).values_list("table_id", flat=True)
    ) == [table.table_id]
