"""Span 表达式的真实 UQ 回归，不写入测试指标。

在已配置 Django 和 UQ 的环境设置 BK_APM_UQ_TEST_BIZ_ID 后运行；默认跳过远程调用。
常量向量模拟聚合后的分子、分母，计算仍由真实 UQ 完成，不 Mock 最终结果。
"""

import math
import os
import unittest
from unittest.mock import patch
from typing import Any

from apm_web.handlers.metric_group import MetricHelper, SpanMetricGroup
from apm_web.models import Application
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.data_source.promql_expression import compile_promql_expression
from core.drf_resource import api


@unittest.skipUnless(os.getenv("BK_APM_UQ_TEST_BIZ_ID"), "需要配置真实 UQ 测试业务")
class TestSpanMetricGroupExpressions(unittest.TestCase):
    def setUp(self) -> None:
        # 仅隔离应用表名读取，表达式编译和计算仍调用真实 UQ。
        table_lookup = patch.object(Application, "get_metric_table_id", return_value="demo.__default__")
        table_lookup.start()
        self.addCleanup(table_lookup.stop)

    @staticmethod
    def vector(value: float | None, **labels: str) -> str:
        expression = f"vector({value})" if value is not None else "(vector(1) > 2)"
        for name, label in labels.items():
            expression = f'label_replace({expression}, "{name}", "{label}", "", "")'
        return expression

    def expression(self, calculation_type: str) -> str:
        bk_biz_id = int(os.environ["BK_APM_UQ_TEST_BIZ_ID"])
        group = SpanMetricGroup(
            bk_biz_id,
            "demo",
            group_by=["service_name", "db_system"],
            metric_helper=MetricHelper(bk_biz_id, "demo"),
            for_service_list=True,
        )
        return group.query_config(calculation_type, raw=True)["expression"]

    def query(
        self, expression: str, numerator: str, denominator: str
    ) -> dict[tuple[tuple[str, str], ...], list[float]]:
        queries: list[dict[str, Any]] = [
            {
                "alias": alias,
                "promql": promql,
                "data_source_label": "prometheus",
                "data_type_label": "time_series",
                "interval": 60,
            }
            for alias, promql in (("a", numerator), ("b", denominator))
        ]
        result = api.unify_query.query_data_by_promql(
            promql=compile_promql_expression(queries, expression),
            start="1700000040",
            end="1700000160",
            step="60s",
            bk_biz_ids=[os.environ["BK_APM_UQ_TEST_BIZ_ID"]],
        )
        self.assertFalse(result.get("is_partial"))
        values_by_group = {}
        for series in result.get("series", []):
            if not series["values"]:
                continue
            dimensions = tuple(sorted(zip(series.get("group_keys", []), series.get("group_values", []))))
            values = [point[1] for point in series["values"]]
            self.assertEqual(len(values), 3)
            self.assertTrue(all(math.isfinite(value) for value in values))
            values_by_group[dimensions] = values
        return values_by_group

    def test_average_duration_matches_legacy_expression(self) -> None:
        collector = {"service_name": "collector", "db_system": "mysql"}
        query = {"service_name": "query", "db_system": "mysql"}
        collector_key = tuple(sorted(collector.items()))
        query_key = tuple(sorted(query.items()))
        cases = [
            (
                "normal_precision",
                self.vector(12.3456789123, **collector),
                self.vector(3, **collector),
                {collector_key: [4.1152263041] * 3},
            ),
            ("zero_total", self.vector(0, **collector), self.vector(0, **collector), {}),
            ("positive_sum_zero_total", self.vector(5, **collector), self.vector(0, **collector), {}),
            ("missing_sum", self.vector(None), self.vector(3, **collector), {}),
            ("missing_total", self.vector(5, **collector), self.vector(None), {}),
            ("missing_sum_without_labels", self.vector(None), self.vector(3), {(): [0] * 3}),
            ("zero_duration", self.vector(0, **collector), self.vector(3, **collector), {collector_key: [0] * 3}),
            (
                "multiple_services",
                f"{self.vector(12, **collector)} or {self.vector(0, **query)}",
                f"{self.vector(3, **collector)} or {self.vector(2, **query)} or {self.vector(4, service_name='transfer')}",
                {collector_key: [4] * 3, query_key: [0] * 3},
            ),
        ]
        expression = self.expression("avg_duration")
        for name, numerator, denominator, expected in cases:
            with self.subTest(case=name):
                # 旧 AvgDurationInstance 在 sum/increase 后执行此公式。
                legacy = self.query("(a or vector(0)) / b", numerator, denominator)
                actual = self.query(expression, numerator, denominator)
                self.assertEqual(legacy, expected)
                self.assertEqual(actual, legacy)

    def test_error_rate_distinguishes_zero_from_missing(self) -> None:
        collector = {"service_name": "collector", "db_system": "mysql"}
        query = {"service_name": "query", "db_system": "mysql"}
        collector_key = tuple(sorted(collector.items()))
        query_key = tuple(sorted(query.items()))
        cases = [
            ("no_errors", self.vector(None), self.vector(10, **collector), {collector_key: [0] * 3}),
            ("all_errors", self.vector(10, **collector), self.vector(10, **collector), {collector_key: [1] * 3}),
            ("some_errors", self.vector(2, **collector), self.vector(5, **collector), {collector_key: [0.4] * 3}),
            ("zero_total", self.vector(0, **collector), self.vector(0, **collector), {}),
            ("missing_error_zero_total", self.vector(None), self.vector(0, **collector), {}),
            ("missing_total", self.vector(None), self.vector(None), {}),
            (
                "multiple_services",
                self.vector(2, **collector),
                f"{self.vector(5, **collector)} or {self.vector(4, **query)}",
                {collector_key: [0.4] * 3, query_key: [0] * 3},
            ),
        ]
        expression = self.expression("exception_rate")
        for name, numerator, denominator, expected in cases:
            with self.subTest(case=name):
                self.assertEqual(self.query(expression, numerator, denominator), expected)
                self.assertEqual(self.query("(a or (0 * b)) / (b > 0)", numerator, denominator), expected)

    def test_error_rate_compiles_nonempty_status_filter(self) -> None:
        bk_biz_id = int(os.environ["BK_APM_UQ_TEST_BIZ_ID"])
        group = SpanMetricGroup(
            bk_biz_id,
            "demo",
            group_by=["service_name", "db_system"],
            metric_helper=MetricHelper(bk_biz_id, "demo"),
            for_service_list=True,
        )
        config = group.query_config("exception_rate", raw=True)
        query = UnifyQuery(
            bk_biz_id=bk_biz_id,
            data_sources=[
                load_data_source(q["data_source_label"], q["data_type_label"])(bk_biz_id=bk_biz_id, **q)
                for q in config["query_configs"]
            ],
            expression=config["expression"],
        )
        params = query.get_unify_query_params(1700000040000, 1700000160000, True)
        compiled = api.unify_query.struct_to_promql(
            **{key: params[key] for key in ("query_list", "metric_merge", "step", "space_uid")}
        )["promql"]
        self.assertIn('status_code="2"', compiled)
        self.assertIn('status_code!=""', compiled)
        # UQ 会去掉空标签；与缺失标签一起由非空选择器排除。
        self.assertEqual(
            self.query("a", self.vector(10, service_name="collector", status_code=""), self.vector(0)),
            {(("service_name", "collector"),): [10] * 3},
        )
