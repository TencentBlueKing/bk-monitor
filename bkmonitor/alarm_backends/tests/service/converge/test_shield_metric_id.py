"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.service.converge.shield.shield_obj import (
    DIMENSION_CONDITION_CLASSES,
    PromqlAwareMetricIdCondition,
)
from bkmonitor.utils.metric_id import build_promql_metric_names
from bkmonitor.utils.range import load_field_instance
from bkmonitor.utils.range.conditions import EqualCondition

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


def match_metric_id(shield_metric_ids, alert_metric_ids) -> bool:
    """按屏蔽配置的 metric_id 判断告警侧 metric_id 是否命中。"""
    condition = PromqlAwareMetricIdCondition(load_field_instance("metric_id", shield_metric_ids))
    return condition.is_match({"metric_id": alert_metric_ids})


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
        assert match_metric_id([DISK_IO_METRIC_ID], [DISK_IO_PROMQL]) is True

    def test_standard_alert_still_matched(self):
        """标准指标策略的等值匹配不受影响。"""
        assert match_metric_id([DISK_IO_METRIC_ID], [DISK_IO_METRIC_ID]) is True

    def test_other_metric_not_matched(self):
        assert match_metric_id(["bk_monitor.system.mem.pct_used"], [DISK_IO_PROMQL]) is False

    def test_promql_without_data_source_prefix_matched(self):
        assert match_metric_id([DISK_IO_METRIC_ID], ["avg_over_time(system:io:util[1m])"]) is True

    def test_same_name_under_other_data_source_not_matched(self):
        """省略前缀的候选不得命中其它数据源的同名指标。"""
        assert match_metric_id([DISK_IO_METRIC_ID], ["avg_over_time(bkdata:system:io:util[1m])"]) is False

    def test_longer_metric_name_not_matched(self):
        """token 边界必须完整，不能被更长的指标名部分命中。"""
        assert match_metric_id([DISK_IO_METRIC_ID], ["avg_over_time(bkmonitor:system:io:util_total[1m])"]) is False

    def test_multi_metric_promql_any_match(self):
        promql = "bkmonitor:system:disk:total - bkmonitor:system:io:util"
        assert match_metric_id([DISK_IO_METRIC_ID], [promql]) is True

    def test_truncated_metric_id_alone_cannot_match(self):
        """字段长度截断会切掉指标名，仅凭 metric_id 无法命中——这是补充原始表达式的原因。"""
        assert len(LONG_DISK_IO_PROMQL) > 128
        assert "bkmonitor:system:io:util" not in TRUNCATED_LONG_METRIC_ID
        assert match_metric_id([DISK_IO_METRIC_ID], [TRUNCATED_LONG_METRIC_ID]) is False

    def test_untruncated_promql_restores_match(self):
        """_calculate_alert_dimension 会同时给出截断后的 metric_id 与未截断表达式，应命中。"""
        assert match_metric_id([DISK_IO_METRIC_ID], [TRUNCATED_LONG_METRIC_ID, LONG_DISK_IO_PROMQL]) is True

    def test_unconvertible_config_does_not_widen(self):
        """配置的 metric_id 无法换算时维持不命中，不扩大屏蔽范围。"""
        assert match_metric_id(["bk_fta.alert.some_alert"], [DISK_IO_PROMQL]) is False

    def test_empty_alert_metric_id(self):
        assert match_metric_id([DISK_IO_METRIC_ID], []) is False
        assert match_metric_id([DISK_IO_METRIC_ID], [""]) is False


class TestDimensionConditionClasses:
    def test_only_metric_id_is_overridden(self):
        """只有 metric_id 使用专用条件类，其余维度键仍是等值匹配。"""
        assert DIMENSION_CONDITION_CLASSES == {"metric_id": PromqlAwareMetricIdCondition}
        for key in ("bk_topo_node", "strategy_id", "level", "bk_host_id"):
            assert DIMENSION_CONDITION_CLASSES.get(key, EqualCondition) is EqualCondition
