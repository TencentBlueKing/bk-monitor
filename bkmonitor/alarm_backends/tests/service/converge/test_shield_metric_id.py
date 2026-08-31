"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

本模块只导入 alarm_backends.service.converge.shield_conditions 与 bkmonitor.utils，
不触碰 shield 包（其 __init__ 会加载 ShieldManager 及全部 shielder），因此无需数据库、
Redis 或 Django app registry，可用 `pytest -p no:django` 单独执行。
"""

from alarm_backends.service.converge.shield_conditions import (
    DIMENSION_CONDITION_CLASSES,
    PROMQL_EXPRESSION_DIMENSION,
    PromqlAwareMetricIdCondition,
)
from bkmonitor.utils.metric_id import build_promql_metric_names
from bkmonitor.utils.range import load_field_instance
from bkmonitor.utils.range.conditions import EqualCondition, IncludeCondition, NotEqualCondition

DISK_IO_METRIC_ID = "bk_monitor.system.io.util"

# 磁盘 io 使用率的 PromQL 写法：指标名被时间聚合、维度聚合、算术和阈值层层包裹
DISK_IO_PROMQL = (
    "(avg by (bk_target_ip, bk_target_cloud_id, device_name, hostname) "
    "(avg_over_time(bkmonitor:system:io:util[1m])))*100>=80"
)

# 聚合维度更多时表达式超过 QueryConfig.metric_id 的字段长度（128），指标名会整个落在截断之外
LONG_DISK_IO_PROMQL = (
    "(avg by (bk_target_ip, bk_target_cloud_id, device_name, hostname, bk_target_service_instance_id) "
    "(avg_over_time(bkmonitor:system:io:util[1m])))*100>=80"
)
TRUNCATED_LONG_METRIC_ID = LONG_DISK_IO_PROMQL[:125] + "..."


def match_metric_id(shield_metric_ids, alert_metric_ids, promql_expressions=None) -> bool:
    """按屏蔽配置的 metric_id 判断告警维度是否命中。

    入参对应 AlertShieldObj._calculate_alert_dimension 产出的两个键。
    """
    condition = PromqlAwareMetricIdCondition(load_field_instance("metric_id", shield_metric_ids))
    dimension = {"metric_id": alert_metric_ids}
    if promql_expressions is not None:
        dimension[PROMQL_EXPRESSION_DIMENSION] = promql_expressions
    return condition.is_match(dimension)


class TestBuildPromqlMetricNames:
    def test_standard_metric_id(self):
        assert build_promql_metric_names(DISK_IO_METRIC_ID) == {
            "bkmonitor:system:io:util",
            "system:io:util",
        }

    def test_custom_and_bkdata_prefix(self):
        assert build_promql_metric_names("custom.2_bkmonitor_time_series_1234.cpu_load") == {
            "custom:2_bkmonitor_time_series_1234:cpu_load",
            "2_bkmonitor_time_series_1234:cpu_load",
        }
        assert build_promql_metric_names("bk_data.100_test_table.usage") == {
            "bkdata:100_test_table:usage",
            "100_test_table:usage",
        }

    def test_data_label_two_segments(self):
        assert build_promql_metric_names("bk_monitor.system_base.mem_usage") == {
            "bkmonitor:system_base:mem_usage",
            "system_base:mem_usage",
        }

    def test_unconvertible_metric_id(self):
        # 空值、无分隔、未登记数据源、事件型单段指标都不参与换算
        assert build_promql_metric_names("") == set()
        assert build_promql_metric_names("bk_monitor") == set()
        assert build_promql_metric_names("bk_fta.alert.some_alert") == set()
        assert build_promql_metric_names("bk_monitor.agent-gse") == set()


class TestPromqlAwareMetricIdCondition:
    def test_promql_alert_matched_by_standard_metric_id(self):
        """按标准指标建立的屏蔽应命中引用同一底层指标的 PromQL 策略告警。"""
        assert match_metric_id([DISK_IO_METRIC_ID], [DISK_IO_PROMQL], [DISK_IO_PROMQL]) is True

    def test_standard_alert_still_matched(self):
        """标准指标策略走等值匹配，不依赖 PromQL 表达式。"""
        assert match_metric_id([DISK_IO_METRIC_ID], [DISK_IO_METRIC_ID], []) is True

    def test_other_metric_not_matched(self):
        assert match_metric_id(["bk_monitor.system.mem.pct_used"], [DISK_IO_PROMQL], [DISK_IO_PROMQL]) is False

    def test_promql_without_data_source_prefix_matched(self):
        expression = "avg_over_time(system:io:util[1m])"
        assert match_metric_id([DISK_IO_METRIC_ID], [expression], [expression]) is True

    def test_same_name_under_other_data_source_not_matched(self):
        """省略前缀的候选不得命中其它数据源的同名指标。"""
        expression = "avg_over_time(bkdata:system:io:util[1m])"
        assert match_metric_id([DISK_IO_METRIC_ID], [expression], [expression]) is False

    def test_longer_metric_name_not_matched(self):
        """token 边界必须完整，不能被更长的指标名部分命中。"""
        expression = "avg_over_time(bkmonitor:system:io:util_total[1m])"
        assert match_metric_id([DISK_IO_METRIC_ID], [expression], [expression]) is False

    def test_multi_metric_promql_any_match(self):
        expression = "bkmonitor:system:disk:total - bkmonitor:system:io:util"
        assert match_metric_id([DISK_IO_METRIC_ID], [expression], [expression]) is True

    def test_truncated_metric_id_alone_cannot_match(self):
        """字段长度截断会切掉指标名，只看 metric_id 无法命中——这是单独保留原始表达式的原因。"""
        assert len(LONG_DISK_IO_PROMQL) > 128
        assert "bkmonitor:system:io:util" not in TRUNCATED_LONG_METRIC_ID
        assert match_metric_id([DISK_IO_METRIC_ID], [TRUNCATED_LONG_METRIC_ID], []) is False

    def test_untruncated_expression_restores_match(self):
        assert match_metric_id([DISK_IO_METRIC_ID], [TRUNCATED_LONG_METRIC_ID], [LONG_DISK_IO_PROMQL]) is True

    def test_unconvertible_config_does_not_widen(self):
        """配置的 metric_id 无法换算时维持不命中，不扩大屏蔽范围。"""
        assert match_metric_id(["bk_fta.alert.some_alert"], [DISK_IO_PROMQL], [DISK_IO_PROMQL]) is False

    def test_missing_or_empty_expressions(self):
        assert match_metric_id([DISK_IO_METRIC_ID], [], None) is False
        assert match_metric_id([DISK_IO_METRIC_ID], [], []) is False
        assert match_metric_id([DISK_IO_METRIC_ID], [], [""]) is False

    def test_expression_accepts_plain_string(self):
        assert match_metric_id([DISK_IO_METRIC_ID], [], DISK_IO_PROMQL) is True


class TestOtherConditionsUnaffected:
    """原始表达式独占维度键，不得影响 metric_id 上的其它条件语义。"""

    def test_metric_id_values_exclude_expression(self):
        """告警侧 metric_id 仍只有 metric_id，表达式不混入。"""
        dimension = {"metric_id": [TRUNCATED_LONG_METRIC_ID], PROMQL_EXPRESSION_DIMENSION: [LONG_DISK_IO_PROMQL]}

        # eq / include / neq 都只看 metric_id，行为与未引入本改动时一致
        include = IncludeCondition(load_field_instance("metric_id", ["bkmonitor:system:io:util"]))
        assert include.is_match(dimension) is False

        equal = EqualCondition(load_field_instance("metric_id", [LONG_DISK_IO_PROMQL]))
        assert equal.is_match(dimension) is False

        not_equal = NotEqualCondition(load_field_instance("metric_id", [LONG_DISK_IO_PROMQL]))
        assert not_equal.is_match(dimension) is True

    def test_expression_dimension_never_a_shield_config_key(self):
        """该键以下划线开头，屏蔽配置里的同名键会被 _clean_dimension 丢弃，不会构造成条件。"""
        assert PROMQL_EXPRESSION_DIMENSION.startswith("_")


class TestDimensionConditionClasses:
    def test_only_metric_id_is_overridden(self):
        """只有 metric_id 使用专用条件类，其余维度键仍是等值匹配。"""
        assert DIMENSION_CONDITION_CLASSES == {"metric_id": PromqlAwareMetricIdCondition}
        for key in ("bk_topo_node", "strategy_id", "level", "bk_host_id"):
            assert DIMENSION_CONDITION_CLASSES.get(key, EqualCondition) is EqualCondition
