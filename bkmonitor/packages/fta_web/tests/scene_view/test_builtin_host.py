"""进程指标聚合方法变量化改造测试。

背景：scene_view/builtin/host.py 的 METRIC_METHOD 原先硬编码 sum_without_time，
导致前端工具栏切换聚合方法不生效。现改为 "${method}_without_time" 占位符，
由前端变量解析为 max_without_time / sum_without_time 等变体；
查询侧通过 normalize_metric_method 做大小写归一与未解析占位符兜底。
"""

from types import SimpleNamespace

import pytest

from bkmonitor.data_source.unify_query.functions import normalize_metric_method
from monitor_web.scene_view.builtin.host import METRIC_METHOD, get_metric_panel

PROCESS_METRIC_FIELDS = ["cpu_usage_pct", "mem_usage_pct", "mem_res", "mem_virt", "fd_num"]


def _make_metric(result_table_id: str, metric_field: str, default_dimensions: list | None = None):
    return SimpleNamespace(
        data_source_label="bk_monitor",
        data_type_label="time_series",
        result_table_id=result_table_id,
        metric_field=metric_field,
        metric_field_name=metric_field,
        default_dimensions=default_dimensions or [],
    )


def _get_panel_method(metric, view_id: str) -> str:
    panel = get_metric_panel(bk_biz_id=2, metric=metric, view_id=view_id)
    query_configs = panel["targets"][0]["data"]["query_configs"]
    return query_configs[0]["metrics"][0]["method"]


class TestMetricMethodPlaceholder:
    """面板生成的 method 占位符契约"""

    @pytest.mark.parametrize("metric_field", PROCESS_METRIC_FIELDS)
    def test_process_metrics_use_method_variable(self, metric_field):
        metric = _make_metric("system.proc", metric_field)
        assert _get_panel_method(metric, "process") == "${method}_WITHOUT_TIME"

    def test_process_uptime_keeps_max(self):
        metric = _make_metric("system.proc", "uptime")
        assert _get_panel_method(metric, "process") == "MAX"

    def test_os_metric_keeps_method_variable(self):
        metric = _make_metric("system.cpu_summary", "usage")
        assert _get_panel_method(metric, "host") == "$method"

    def test_metric_method_table_consistency(self):
        """METRIC_METHOD 声明与面板生成结果一致"""
        for metric_field in PROCESS_METRIC_FIELDS:
            metric_id = f"bk_monitor.time_series.system.proc.{metric_field}"
            assert METRIC_METHOD[metric_id] == "${method}_WITHOUT_TIME"
        assert METRIC_METHOD["bk_monitor.time_series.system.proc.uptime"] == "MAX"


class TestNormalizeMetricMethod:
    """查询侧方法名归一化与兜底"""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            # 大小写归一（前端拼接产物为全大写后缀：MAX_WITHOUT_TIME）
            ("MAX_WITHOUT_TIME", "max_without_time"),
            ("MAX_without_time", "max_without_time"),
            ("Min_Without_Time", "min_without_time"),
            ("  SUM_without_time  ", "sum_without_time"),
            # 普通方法保持小写语义
            ("MAX", "max"),
            ("avg", "avg"),
            # 未解析占位符兜底：保持进程指标历史口径 / 同族聚合口径（大小写不敏感）
            ("${method}_WITHOUT_TIME", "sum_without_time"),
            ("${method}_without_time", "sum_without_time"),
            ("$method_without_time", "sum_without_time"),
            ("$method", "sum"),
            ("${method}", "sum"),
            # 老前端 VariablesService 变量缺失时的字符串化产物兜底
            ("undefined_without_time", "sum_without_time"),
            ("undefined", "sum"),
            # 枚举校验兜底：以 _without_time 结尾但不在 AggMethods 合法枚举内 → sum
            ("distinct_without_time", "sum"),
            ("median_WITHOUT_TIME", "sum"),
            # 5 个合法变体原样通过
            ("sum_without_time", "sum_without_time"),
            ("avg_without_time", "avg_without_time"),
            ("count_without_time", "count_without_time"),
            ("min_without_time", "min_without_time"),
            ("max_without_time", "max_without_time"),
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_metric_method(raw) == expected

    def test_all_toolbar_options_resolvable(self):
        """前端工具栏四个选项经拼接+归一化后均为合法 AggMethods 键"""
        from bkmonitor.data_source.unify_query.functions import AggMethods

        for option in ["AVG", "SUM", "MIN", "MAX"]:
            composed = f"{option}_without_time"
            assert normalize_metric_method(composed) in AggMethods


class TestUnifyQueryConfigMethodHandling:
    """查询构造层（to_unify_query_config）对拼接产物的处理契约"""

    @staticmethod
    def _make_data_source(method: str):
        from bkmonitor.data_source.data_source import BkMonitorTimeSeriesDataSource

        return BkMonitorTimeSeriesDataSource(
            table="system.proc",
            metrics=[{"field": "cpu_usage_pct", "method": method, "alias": "A"}],
            interval=60,
            group_by=["display_name"],
        )

    def test_uppercase_without_time_hits_agg_methods_branch(self):
        """MAX_WITHOUT_TIME（前端拼接产物）→ 命中 AggMethods：无 time_aggregation，仅跨 series 聚合"""
        query = self._make_data_source("MAX_WITHOUT_TIME").to_unify_query_config()[0]
        assert query["time_aggregation"] == {}
        assert query["function"][0]["method"] == "max"

    def test_normal_sum_generates_over_time_window(self):
        """普通 SUM → 两层聚合：sum_over_time 窗口 + 跨维度聚合"""
        query = self._make_data_source("SUM").to_unify_query_config()[0]
        assert query["time_aggregation"]["function"] == "sum_over_time"
        assert query["time_aggregation"]["window"] == "60s"
        assert query["function"][0]["method"] == "sum"

    def test_unresolved_placeholder_falls_back_to_sum_without_time(self):
        """占位符未被前端解析时兜底为 sum_without_time（进程指标历史口径），不产生非法查询"""
        query = self._make_data_source("${method}_WITHOUT_TIME").to_unify_query_config()[0]
        assert query["time_aggregation"] == {}
        assert query["function"][0]["method"] == "sum"

    def test_legacy_sum_without_time_unchanged(self):
        """存量配置字面量 sum_without_time 行为不变"""
        query = self._make_data_source("sum_without_time").to_unify_query_config()[0]
        assert query["time_aggregation"] == {}
        assert query["function"][0]["method"] == "sum"
