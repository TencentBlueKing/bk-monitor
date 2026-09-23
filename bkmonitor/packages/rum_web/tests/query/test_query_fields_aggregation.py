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
