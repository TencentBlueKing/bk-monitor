"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from unittest.mock import MagicMock, patch

import pytest
from rest_framework.exceptions import ValidationError

from bkmonitor.data_source.unify_query.builder import QueryConfigBuilder
from bkmonitor.data_source.utils.query import BaseQuery
from rum_web.handlers.query.span import SpanQuery


def _make_target(table_id: str = "bk_rum.default.span"):
    from bkmonitor.data_source.utils.apm import TraceDatasourceTarget

    return TraceDatasourceTarget.build(bk_biz_id=2, app_name="my_app", table_id=table_id)


class TestSumExpression:
    """BaseQuery._sum_expression：多字段求和表达式生成"""

    def test_single_field_returns_alias(self):
        """单字段直接返回别名，不做求和包裹"""
        assert BaseQuery._sum_expression(["q0"]) == "q0"

    def test_multi_field_returns_wrapped_sum(self):
        """多字段生成 (alias or other*0) 形式的容错求和，并用 + 连接"""
        expr = BaseQuery._sum_expression(["q0", "q1"])
        assert expr == "(q0 or q1 * 0) + (q1 or q0 * 0)"

    def test_three_fields(self):
        expr = BaseQuery._sum_expression(["q0", "q1", "q2"])
        # 每个 alias 的位置对其他 alias 做 *0 兜底，保证字段缺测时不影响求和
        assert expr == "(q0 or q1 * 0 or q2 * 0) + (q1 or q0 * 0 or q2 * 0) + (q2 or q0 * 0 or q1 * 0)"


class TestMetricQueries:
    """BaseQuery._metric_queries：一个字段一个引用，多结果表各出一个"""

    def test_one_field_one_query(self):
        queries = [QueryConfigBuilder(("a", "b")).table("t1")]
        result = BaseQuery._metric_queries(queries, ["f1"], "count", [])
        assert len(result) == 1
        assert isinstance(result[0], QueryConfigBuilder)

    def test_one_field_multiple_queries(self):
        """应用配置多个结果表时，每个结果表各出一个引用"""
        queries = [QueryConfigBuilder(("a", "b")).table(f"t{i}") for i in range(3)]
        result = BaseQuery._metric_queries(queries, ["f1"], "count", [])
        assert len(result) == 3

    def test_multiple_fields_multiple_queries(self):
        queries = [QueryConfigBuilder(("a", "b")).table("t1"), QueryConfigBuilder(("a", "b")).table("t2")]
        result = BaseQuery._metric_queries(queries, ["f1", "f2"], "avg", ["service"])
        assert len(result) == 4


class TestQueryFieldsAggregatedGroup:
    """BaseQuery._query_fields_aggregated_group：无维度/分组聚合"""

    @pytest.fixture
    def query(self):
        return SpanQuery([_make_target()])

    def test_single_field_no_group_uses_scalar(self, query):
        """无维度的单字段聚合走标量查询，返回 {"_result_": value}"""
        with patch.object(query, "_query_field_aggregated_value", return_value=42) as mock_value:
            result = query._query_fields_aggregated_group([], 1000, 2000, ["f1"], "count")
        mock_value.assert_called_once()
        assert result == [{"_result_": 42}]

    def test_single_field_no_group_none_value_falls_back_to_zero(self, query):
        """标量查询缺数据时回落为 0"""
        with patch.object(query, "_query_field_aggregated_value", return_value=None):
            result = query._query_fields_aggregated_group([], 1000, 2000, ["f1"], "count")
        assert result == [{"_result_": 0}]

    def test_with_group_uses_add_query(self, query):
        """带 group_by 时走分组查询，直接返回 _add_query 的执行结果"""
        fake_qs = MagicMock()
        # 方法内部通过 list(qs) 迭代结果，需 mock __iter__
        fake_qs.__iter__.return_value = iter([{"service": "a", "_result_": 10}])
        with (
            patch.object(query, "_get_time_range", return_value=(1000, 2000)),
            patch.object(query, "_add_query", return_value=fake_qs) as mock_add,
        ):
            result = query._query_fields_aggregated_group([], 1000, 2000, ["f1"], "count", group_by=["service"])
        mock_add.assert_called_once()
        assert result == [{"service": "a", "_result_": 10}]

    @pytest.mark.parametrize("group_by", [["time"], ["service", "time"]])
    @pytest.mark.parametrize("interval,expected_interval", [(3600, 3600), (None, 2880)])
    def test_time_buckets_keep_all_points(self, query, group_by, interval, expected_interval):
        queries = query.get_queries()
        with (
            patch.object(query, "_get_time_range", return_value=(1737532800000, 1737619200000)),
            patch.object(query, "_add_query", return_value=[]) as add_query,
        ):
            query._query_fields_aggregated_group(queries, 1737532800, 1737619200, ["f1"], "count", group_by, interval)
        qs, metric_queries = add_query.call_args.args
        assert qs.query.instant is False
        assert qs.query.is_time_agg is True
        assert qs.query.get_limit() == query.QUERY_MAX_LIMIT
        assert metric_queries[0].query.interval == expected_interval
        assert list(metric_queries[0].query.group_by) == [field for field in group_by if field != "time"]
        assert group_by[-1] == "time"
        assert queries[0].query.interval is None


class TestStatistics:
    @pytest.fixture
    def query(self):
        return SpanQuery([_make_target()])

    @pytest.mark.parametrize(
        "start,end", [(1737532800, 1737536400), (1737532800, None), (None, 1737536400), (None, None)]
    )
    @pytest.mark.parametrize("shift,offset", [("1d", -86400), ("3600s", -3600)])
    def test_shift_window_after_resolving_defaults(self, query, start, end, shift, offset):
        resolved_start, resolved_end = 1737532800, 1737536400
        with (
            patch.object(
                query, "_get_time_range", return_value=(resolved_start * 1000, resolved_end * 1000)
            ) as resolve,
            patch.object(query, "_query_fields_aggregated_group", return_value=[]) as group,
        ):
            result = query._statistics([], start, end, "f", "count", "0s", ["0s", shift])
        resolve.assert_called_once_with(start, end)
        assert sorted(call.args[1:3] for call in group.call_args_list) == [
            (resolved_start + offset, resolved_end + offset),
            (resolved_start, resolved_end),
        ]
        assert result == {"total": 0, "data": []}

    def test_buckets_align_before_growth_rates(self, query):
        start, end = 1737532800, 1737619200

        def aggregate(queries, shifted_start, shifted_end, fields, method, **kwargs):
            current = shifted_start == start
            return [
                {"_time_": shifted_start * 1000, "_result_": 120 if current else 100},
                {"_time_": (shifted_start + 3600) * 1000, "_result_": 80 if current else 100},
            ]

        with (
            patch.object(query, "_get_time_range", return_value=(start * 1000, end * 1000)),
            patch.object(query, "_query_fields_aggregated_group", side_effect=aggregate),
        ):
            result = query._statistics([], start, end, "f", "count", "0s", ["0s", "1d"], ["time"], 3600)
        by_time = {record["dimensions"]["time"]: record for record in result["data"]}
        assert result["total"] == 2
        assert by_time[start]["growth_rates"]["1d"] == 20
        assert by_time[start + 3600]["growth_rates"]["1d"] == -20
        assert by_time[start]["proportions"]["0s"] == 60

    @pytest.mark.parametrize("failed_shift", ["0s", "1d"])
    def test_failed_window_keeps_alias(self, query, failed_shift):
        start, end = 1737532800, 1737536400

        def aggregate(queries, shifted_start, *args, **kwargs):
            shift = "0s" if shifted_start == start else "1d"
            if shift == failed_shift:
                raise RuntimeError("查询失败")
            return [{"_result_": 100}]

        with (
            patch.object(query, "_get_time_range", return_value=(start * 1000, end * 1000)),
            patch.object(query, "_query_fields_aggregated_group", side_effect=aggregate),
        ):
            result = query._statistics([], start, end, "f", "count", "0s", ["0s", "1d"])
        assert result["data"][0][failed_shift] is None
        assert result["data"][0]["proportions"][failed_shift] is None

    def test_distinct_does_not_add_proportions(self, query):
        with (
            patch.object(query, "_get_time_range", return_value=(1737532800000, 1737536400000)),
            patch.object(query, "_query_fields_aggregated_group", return_value=[{"_result_": 12}]),
        ):
            result = query._statistics([], None, None, "attributes.user.id", "distinct", "0s", ["0s", "1h"])
        assert result["data"][0]["growth_rates"]["1h"] == 0
        assert "proportions" not in result["data"][0]

    def test_bucket_limit_with_default_time_range(self, query):
        with (
            patch.object(query, "_get_time_range", return_value=(1737532800000, 1737619200000)),
            patch.object(query, "_query_fields_aggregated_group") as group,
            pytest.raises(ValidationError, match="时间分桶过多"),
        ):
            query._statistics([], None, None, "f", "count", "0s", ["0s"], ["time"], 1)
        group.assert_not_called()

    def test_span_query_forwards_keyword_arguments(self, query):
        params = {
            "start_time": None,
            "end_time": None,
            "field": "f",
            "cal_type": "count",
            "baseline": "0s",
            "time_shifts": ["0s"],
            "group_by": ["time"],
            "interval": 3600,
        }
        filters = [{"key": "attributes.span_type", "operator": "equal", "value": ["error"]}]
        with (
            patch.object(query, "get_queries", return_value=[]) as get_queries,
            patch.object(query, "_statistics", return_value={"total": 0, "data": []}) as statistics,
        ):
            query.statistics(**params, filters=filters, query_string="error")
        get_queries.assert_called_once_with(filters, "error")
        statistics.assert_called_once_with(queries=[], **params)
