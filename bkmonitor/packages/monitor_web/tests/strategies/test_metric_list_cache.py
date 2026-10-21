"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from contextlib import ExitStack
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
from django.db import connections

from bkmonitor.models.metric_list_cache import MetricListCache
from monitor_web.strategies import metric_list_cache
from monitor_web.strategies.metric_list_cache import (
    BaseMetricCacheManager,
    BkmonitorMetricCacheManager,
    CustomMetricCacheManager,
)
from monitor_web.strategies.resources.v2 import GetMetricListV2Resource
from monitor_web.strategies.metric_cache.built_in_metrics import PROCESS_METRICS, SYSTEM_HOST_METRICS


@pytest.fixture
def custom_scope_tables():
    table = {
        "bk_biz_id": 2,
        "time_series_group_id": 10,
        "table_id": "2_bkapm_metric_demo.count",
        "time_series_group_name": "bkapm_demo_metric",
        "bk_data_id": 100,
        "label": "apm",
    }
    metric = {
        "field_name": "count",
        "description": "失败数",
        "tag_list": [{"field_name": "item_type", "description": "物品类型"}],
    }
    first = {**table, "metric_info_list": [deepcopy(metric)]}
    second = {**table, "metric_info_list": [deepcopy(metric)]}
    second["metric_info_list"][0]["tag_list"].append(
        {"field_name": "base62Mm45BOZ5eM2yBMRzB", "description": "所属品牌"}
    )
    return [first, second]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize(
    "first_description,expected_name",
    [("物品类型", "物品类型"), ("", "自定义物品别名"), (None, "自定义物品别名")],
)
def test_custom_metric_refresh_merges_scopes_before_cache_deduplication(
    monkeypatch, custom_scope_tables, reverse, existing, first_description, expected_name
):
    custom_scope_tables[0]["metric_info_list"][0]["tag_list"][0]["description"] = first_description
    custom_scope_tables[1]["metric_info_list"][0]["tag_list"][0]["description"] = expected_name
    tables = custom_scope_tables[::-1] if reverse else custom_scope_tables
    monkeypatch.setattr(metric_list_cache.api.metadata, "query_time_series_group", lambda **kwargs: tables)
    plugins = MagicMock()
    plugins.exclude.return_value.values_list.return_value = []
    monkeypatch.setattr(metric_list_cache.CollectorPluginMeta.objects, "filter", lambda **kwargs: plugins)
    monkeypatch.setattr(MetricListCache, "get_human_readable_name", lambda self: "demo.count")

    manager = CustomMetricCacheManager(bk_tenant_id="system", bk_biz_id=2)
    monkeypatch.setattr(manager, "get_label_name", lambda label: label)
    monkeypatch.setattr(manager, "refresh_metric_use_frequency", lambda: None)
    old_metric = MetricListCache(
        id=1, bk_biz_id=2, result_table_id="2_bkapm_metric_demo.__default__", metric_field="count", related_id="10"
    )
    pool = MagicMock()
    pool.filter.return_value = pool
    pool.only.return_value = [old_metric] if existing else []
    monkeypatch.setattr(manager, "get_metric_pool", lambda: pool)
    writes = []
    monkeypatch.setattr(MetricListCache.objects, "bulk_create", lambda metrics, **kwargs: writes.extend(metrics))
    monkeypatch.setattr(MetricListCache.objects, "bulk_update", lambda metrics, *args, **kwargs: writes.extend(metrics))

    manager.run(delay=False)

    [cached] = writes
    [result] = GetMetricListV2Resource.get_metric_list(2, [cached])
    assert {dimension["id"]: dimension["name"] for dimension in result["dimensions"]} == {
        "item_type": expected_name,
        "base62Mm45BOZ5eM2yBMRzB": "所属品牌",
    }
    assert result["result_table_id"] == "2_bkapm_metric_demo.__default__"
    assert result["metric_field"] == "count"
    assert cached.metric_md5

    pool.only.return_value = [cached]
    writes.clear()
    manager.run(delay=False)
    assert writes == []


@pytest.mark.parametrize("field,value", [("bk_biz_id", 3), ("time_series_group_id", 11), ("table_id", "other.count")])
def test_custom_metric_dimensions_do_not_cross_data_sources(custom_scope_tables, field, value):
    custom_scope_tables[1][field] = value

    CustomMetricCacheManager.merge_metric_dimensions(custom_scope_tables)

    assert len(custom_scope_tables[0]["metric_info_list"][0]["tag_list"]) == 1


def test_custom_metric_dimension_merge_preserves_aliases_and_other_metrics(custom_scope_tables):
    first = custom_scope_tables[0]["metric_info_list"][0]
    second = custom_scope_tables[1]["metric_info_list"][0]
    first["tag_list"][0]["description"] = "已有物品别名"
    other = {"field_name": "other_count", "tag_list": [{"field_name": "other_tag", "description": "其他维度"}]}
    custom_scope_tables[1]["metric_info_list"].extend([other, None])

    CustomMetricCacheManager.merge_metric_dimensions(custom_scope_tables)

    assert first["tag_list"][0]["description"] == "已有物品别名"
    assert len(first["tag_list"]) == 2
    assert len(second["tag_list"]) == 2
    assert other["tag_list"] == [{"field_name": "other_tag", "description": "其他维度"}]


@pytest.mark.parametrize("description_fields", [{}, {"description": ""}, {"description": None}])
def test_custom_metric_dimension_merge_keeps_first_nonempty_description(custom_scope_tables, description_fields):
    first = custom_scope_tables[0]["metric_info_list"][0]
    original_tag = {"field_name": "item_type", **description_fields}
    first["tag_list"] = [original_tag]
    second = custom_scope_tables[1]["metric_info_list"][0]
    second["tag_list"][0]["description"] = "自定义物品别名"
    third = deepcopy(custom_scope_tables[1])
    third["metric_info_list"][0]["tag_list"][0]["description"] = "后续物品别名"
    original_tags = deepcopy([original_tag, *second["tag_list"]])

    CustomMetricCacheManager.merge_metric_dimensions([*custom_scope_tables, third])

    assert first["tag_list"][0] == {"field_name": "item_type", "description": "自定义物品别名"}
    assert len(first["tag_list"]) == 2
    assert [original_tag, *second["tag_list"]] == original_tags
    assert third["metric_info_list"][0]["tag_list"][0]["description"] == "后续物品别名"


def test_custom_metric_dimension_merge_does_not_execute_sql(custom_scope_tables):
    queries = []

    def record_query(execute, sql, params, many, context):
        queries.append(sql)
        return execute(sql, params, many, context)

    with ExitStack() as stack:
        for connection in connections.all():
            stack.enter_context(connection.execute_wrapper(record_query))
        for count in (1, 100, 1000):
            tables = deepcopy(custom_scope_tables) + [deepcopy(custom_scope_tables[1]) for _ in range(count)]
            CustomMetricCacheManager.merge_metric_dimensions(tables)
            assert len(tables[0]["metric_info_list"][0]["tag_list"]) == 2

    assert queries == []


def test_process_cpu_time_metrics_use_millisecond_unit():
    cpu_time_fields = {"cpu_system", "cpu_total_ticks", "cpu_user"}
    system_proc_metrics = next(
        table["metrics"] for table in SYSTEM_HOST_METRICS if table["result_table_id"] == "system.proc"
    )

    assert {
        metric["metric_field"]: metric["unit"]
        for metric in system_proc_metrics
        if metric["metric_field"] in cpu_time_fields
    } == {field: "ms" for field in cpu_time_fields}
    assert {
        metric["metric_field"]: metric["unit"]
        for metric in PROCESS_METRICS
        if metric["metric_field"] in cpu_time_fields
    } == {field: "ms" for field in cpu_time_fields}


def test_truncate_metric_fields_by_model_field_length():
    metric = {
        "result_table_id": "a" * 257,
        "result_table_name": "索引表" * 100,
        "readable_name": "a" * 256,
        "metric_field": "count",
    }

    BaseMetricCacheManager.truncate_metric_fields(metric)

    assert metric["result_table_id"] == "a" * 256
    assert metric["result_table_name"] == ("索引表" * 100)[:256]
    assert metric["readable_name"] == "a" * 255
    assert metric["metric_field"] == "count"


class TestBkmonitorMetricCacheManager:
    def test_get_system_metric_uses_existing_cloud_dimension(self):
        manager = BkmonitorMetricCacheManager.__new__(BkmonitorMetricCacheManager)
        manager.dimension_map = {}
        manager.get_label_name = lambda label: label

        table = {
            "table_id": "bkmonitor_time_series_1100030.__default__",
            "table_name_zh": "系统基础指标",
            "label": "os",
            "source_label": "bk_monitor",
            "type_label": "time_series",
            "data_label": "system_base",
            "field_list": [
                {"field_name": "hostname", "tag": "dimension", "description": "hostname"},
                {"field_name": "bk_target_ip", "tag": "dimension", "description": "目标IP"},
                {"field_name": "bk_cloud_id", "tag": "dimension", "description": "bk_cloud_id"},
                {"field_name": "host_timesync_query_seconds_min", "tag": "metric", "alias_name": "", "unit": ""},
            ],
        }

        [metric] = manager.get_system_metric(table)

        dimensions = [dimension["id"] for dimension in metric["dimensions"]]
        assert "bk_target_ip" in dimensions
        assert "bk_cloud_id" in dimensions
        assert "bk_target_cloud_id" not in dimensions
        assert dimensions.count("bk_target_ip") == 1
        assert metric["default_dimensions"] == ["bk_target_ip", "bk_cloud_id"]
