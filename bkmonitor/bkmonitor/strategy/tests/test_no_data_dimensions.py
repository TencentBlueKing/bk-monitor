"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from types import SimpleNamespace

import pytest

from alarm_backends.constants import NO_DATA_TAG_DIMENSION
from alarm_backends.core.control.mixins.nodata import CheckMixin
from bkmonitor.data_source.data_source import LogSearchTimeSeriesDataSource
from bkmonitor.strategy.new_strategy import Item
from constants.data_source import DataSourceLabel, DataTypeLabel


def log_query(dimensions: list[str], conditions: list[dict] | None = None, *, alias: str = "a") -> dict:
    return {
        "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
        "data_type_label": DataTypeLabel.TIME_SERIES,
        "alias": alias,
        "index_set_id": 1,
        "result_table_id": "",
        "agg_method": "COUNT",
        "agg_interval": 60,
        "agg_dimension": dimensions,
        "agg_condition": conditions or [],
        "metric_field": "_index",
    }


def make_item(dimensions: list[str], query_configs: list[dict]) -> Item:
    return Item(
        strategy_id=1,
        name="test item",
        no_data_config={"is_enabled": True, "continuous": 5, "agg_dimension": dimensions},
        query_configs=query_configs,
    )


def test_nonblacklisted_log_exclude_cleans_unused_condition_dimension(settings) -> None:
    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = []
    query = log_query(["namespace"], [{"key": "body", "method": "exclude", "value": ["noise"]}])
    item = make_item(["namespace", "body", "pod"], [query])

    item.align_no_data_dimensions(2)

    assert item.no_data_config == {"is_enabled": True, "continuous": 5, "agg_dimension": ["namespace"]}


def test_blacklisted_log_preserves_extra_runtime_condition_dimension(settings) -> None:
    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = [2]
    query = log_query(
        ["namespace", "body"],
        [
            {"key": "body", "method": "exclude", "value": ["noise"]},
            {"key": "severity", "method": "eq", "value": ["error"], "condition": "and"},
        ],
    )
    item = make_item(["namespace", "body", "severity", "pod"], [query])
    source = LogSearchTimeSeriesDataSource.init_by_query_config(query, bk_biz_id=2, bk_tenant_id="system")
    assert "severity" in source.group_by

    item.align_no_data_dimensions(2)

    assert item.no_data_config["agg_dimension"] == ["namespace", "body", "severity"]


def test_structured_queries_keep_union_of_dimensions(settings) -> None:
    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = []
    item = make_item(
        ["namespace", "pod", "stale"],
        [log_query(["namespace"], alias="a"), log_query(["pod"], alias="b")],
    )

    item.align_no_data_dimensions(2)

    assert item.no_data_config["agg_dimension"] == ["namespace", "pod"]


def test_host_fuller_dimension_survives_alignment_and_is_used_by_nodata(mocker, settings) -> None:
    from alarm_backends.service.access.data.fullers import TopoNodeFuller

    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = []
    item = make_item(["bk_target_ip"], [log_query(["bk_host_id"])])
    host = SimpleNamespace(ip="127.0.0.1", bk_cloud_id=0, topo_link={})
    mocker.patch("alarm_backends.service.access.data.fullers.HostManager.get_by_id", return_value=host)
    record = SimpleNamespace(bk_tenant_id="system", dimensions={"bk_host_id": "42"}, items=[])
    TopoNodeFuller().full(record)

    item.align_no_data_dimensions(2)
    point = SimpleNamespace(dimensions=record.dimensions, timestamp=60)
    result = CheckMixin._process_dimensions(item.no_data_config["agg_dimension"], [point])

    assert item.no_data_config["agg_dimension"] == ["bk_target_ip"]
    assert result["data_dimensions"] == [{"bk_target_ip": "127.0.0.1", NO_DATA_TAG_DIMENSION: True}]


@pytest.mark.parametrize(
    "dynamic_query",
    [
        {
            "data_source_label": DataSourceLabel.PROMETHEUS,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "alias": "b",
            "promql": "sum by (service) (cpu_usage)",
            "agg_interval": 60,
        },
        {
            "data_source_label": DataSourceLabel.DASHBOARD,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "alias": "b",
            "dashboard_uid": "dashboard",
            "panel_id": 1,
            "ref_id": "A",
            "variables": {},
        },
        {
            "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
            "data_type_label": DataTypeLabel.EVENT,
            "alias": "b",
            "result_table_id": "system.event",
            "metric_field": "event",
            "agg_condition": [],
        },
    ],
)
def test_unknown_output_in_mixed_queries_preserves_nodata_dimensions(dynamic_query: dict, settings) -> None:
    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = []
    item = make_item(["namespace", "service"], [log_query(["namespace"]), dynamic_query])

    item.align_no_data_dimensions(2)

    assert item.no_data_config["agg_dimension"] == ["namespace", "service"]


def test_realtime_query_preserves_dynamic_dimensions() -> None:
    query = log_query(["namespace"])
    query["data_source_label"] = DataSourceLabel.BK_MONITOR_COLLECTOR
    query["agg_method"] = "REAL_TIME"
    item = make_item(["namespace", "service"], [query])

    item.align_no_data_dimensions(2)

    assert item.no_data_config["agg_dimension"] == ["namespace", "service"]


def test_last_removed_dimension_changes_nodata_check_to_whole_query(settings) -> None:
    settings.LOG_UNIFY_QUERY_BLACK_BIZ_LIST_ENV = []
    item = make_item(["pod"], [log_query([])])

    item.align_no_data_dimensions(2)
    point = SimpleNamespace(dimensions={"namespace": "example"}, timestamp=60)
    result = CheckMixin._process_dimensions(item.no_data_config["agg_dimension"], [point])

    assert item.no_data_config["agg_dimension"] == []
    assert result["data_dimensions"] == [{NO_DATA_TAG_DIMENSION: True}]
