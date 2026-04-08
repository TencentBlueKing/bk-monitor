"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
access-detect 合并处理单元测试

测试场景：
1. 场景 1：单一静态阈值策略 + 开关启用 → 触发合并处理
2. 场景 2：多 Item 全静态阈值 + 开关启用 → 触发合并处理
3. 场景 3：混合算法策略 + 开关启用 → 走原有流程
4. 场景 4：静态阈值策略 + 开关关闭 → 走原有流程
5. 场景 5：静态阈值策略 + 灰度列表不包含 → 走原有流程
"""

import copy
from collections import defaultdict
from unittest import mock

import pytest
from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.service.access.data import AccessDataProcess
from bkmonitor.models import CacheNode

from .config import RAW_DATA, RAW_DATA_ZERO, STRATEGY_CONFIG_V3

# 测试数据
query_record = [RAW_DATA, RAW_DATA_ZERO]

pytestmark = pytest.mark.django_db


# 静态阈值策略配置（所有算法都是 Threshold）
STATIC_THRESHOLD_STRATEGY = copy.deepcopy(STRATEGY_CONFIG_V3)

# 混合算法策略配置（包含非 Threshold 算法）
MIXED_ALGORITHM_STRATEGY = copy.deepcopy(STRATEGY_CONFIG_V3)
MIXED_ALGORITHM_STRATEGY["items"][0]["algorithms"].append(
    {
        "config": {"floor": 1, "ceil": 10},
        "level": 1,
        "type": "SimpleRingRatio",  # 非静态阈值算法
        "id": 4,
    }
)

# 多 Item 策略配置
MULTI_ITEM_STRATEGY = copy.deepcopy(STRATEGY_CONFIG_V3)
MULTI_ITEM_STRATEGY["items"].append(
    {
        "query_configs": [
            {
                "metric_field": "load1",
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                "unit_conversion": 1.0,
                "id": 3,
                "agg_method": "AVG",
                "agg_condition": [],
                "agg_interval": 60,
                "result_table_id": "system.cpu_load",
                "unit": "%",
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "metric_id": "system.cpu_detail.load1",
            }
        ],
        "algorithms": [
            {
                "config": [{"threshold": 5.0, "method": "gte"}],
                "level": 1,
                "type": "Threshold",
                "id": 5,
            },
        ],
        "name": "load1",
        "no_data_config": {"is_enabled": False, "continuous": 5},
        "id": 2,
        "create_time": 1569044491,
        "update_time": 1569044491,
    }
)


class MockRecord:
    """模拟 DataRecord"""

    def __init__(self, attrs):
        self.data = copy.deepcopy(attrs)
        self.__dict__.update(attrs)
        self.time = attrs.get("_time_", 0)
        self.is_duplicate = False
        self.inhibitions = defaultdict(lambda: False)
        self.is_retains = defaultdict(lambda: True)


class TestAccessDetectMerge:
    """access-detect 合并处理测试类"""

    def setup_method(self):
        CacheNode.refresh_from_settings()
        c = key.ACCESS_BATCH_DATA_KEY.client
        c.flushall()

    def teardown_method(self):
        pass

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
        return_value=STATIC_THRESHOLD_STRATEGY,
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail",
        return_value={"1": [1]},
    )
    def test_scenario_1_static_threshold_enabled(self, mock_strategy_group, mock_strategy):
        """
        场景 1：单一静态阈值策略 + 开关启用 → 触发合并处理
        """
        strategy_group_key = "test_merge_1"
        acc_data = AccessDataProcess(strategy_group_key)

        # 启用合并处理开关
        with mock.patch.object(settings, "ACCESS_DETECT_MERGE_ENABLED", True):
            with mock.patch.object(settings, "ACCESS_DETECT_MERGE_STRATEGY_IDS", []):
                # 验证 _can_merge_access_detect 返回 True
                assert acc_data._can_merge_access_detect() is True

                # 验证 _is_all_static_threshold 返回 True
                for item in acc_data.items:
                    assert acc_data._is_all_static_threshold(item) is True

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
        return_value=MULTI_ITEM_STRATEGY,
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail",
        return_value={"1": [1, 2]},
    )
    def test_scenario_2_multi_item_static_threshold(self, mock_strategy_group, mock_strategy):
        """
        场景 2：多 Item 全静态阈值 + 开关启用 → 触发合并处理
        """
        strategy_group_key = "test_merge_2"
        acc_data = AccessDataProcess(strategy_group_key)

        with mock.patch.object(settings, "ACCESS_DETECT_MERGE_ENABLED", True):
            with mock.patch.object(settings, "ACCESS_DETECT_MERGE_STRATEGY_IDS", []):
                # 验证所有 Item 都是静态阈值
                for item in acc_data.items:
                    assert acc_data._is_all_static_threshold(item) is True

                # 验证 _can_merge_access_detect 返回 True
                assert acc_data._can_merge_access_detect() is True

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
        return_value=MIXED_ALGORITHM_STRATEGY,
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail",
        return_value={"1": [1]},
    )
    def test_scenario_3_mixed_algorithm_enabled(self, mock_strategy_group, mock_strategy):
        """
        场景 3：混合算法策略 + 开关启用 → 走原有流程
        """
        strategy_group_key = "test_merge_3"
        acc_data = AccessDataProcess(strategy_group_key)

        with mock.patch.object(settings, "ACCESS_DETECT_MERGE_ENABLED", True):
            with mock.patch.object(settings, "ACCESS_DETECT_MERGE_STRATEGY_IDS", []):
                # 验证 _is_all_static_threshold 返回 False（因为包含非 Threshold 算法）
                for item in acc_data.items:
                    assert acc_data._is_all_static_threshold(item) is False

                # 验证 _can_merge_access_detect 返回 False
                assert acc_data._can_merge_access_detect() is False

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
        return_value=STATIC_THRESHOLD_STRATEGY,
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail",
        return_value={"1": [1]},
    )
    def test_scenario_4_static_threshold_disabled(self, mock_strategy_group, mock_strategy):
        """
        场景 4：静态阈值策略 + 开关关闭 → 走原有流程
        """
        strategy_group_key = "test_merge_4"
        acc_data = AccessDataProcess(strategy_group_key)

        # 关闭合并处理开关
        with mock.patch.object(settings, "ACCESS_DETECT_MERGE_ENABLED", False):
            # 验证 _is_all_static_threshold 仍返回 True
            for item in acc_data.items:
                assert acc_data._is_all_static_threshold(item) is True

            # 验证 _can_merge_access_detect 返回 False（因为开关关闭）
            assert acc_data._can_merge_access_detect() is False

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
        return_value=STATIC_THRESHOLD_STRATEGY,
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail",
        return_value={"1": [1]},
    )
    def test_scenario_5_static_threshold_not_in_grayscale(self, mock_strategy_group, mock_strategy):
        """
        场景 5：静态阈值策略 + 灰度列表不包含 → 走原有流程
        """
        strategy_group_key = "test_merge_5"
        acc_data = AccessDataProcess(strategy_group_key)

        # 启用开关但灰度列表不包含当前策略
        with mock.patch.object(settings, "ACCESS_DETECT_MERGE_ENABLED", True):
            with mock.patch.object(settings, "ACCESS_DETECT_MERGE_STRATEGY_IDS", [999, 1000]):  # 不包含策略 ID 1
                # 验证 _is_all_static_threshold 仍返回 True
                for item in acc_data.items:
                    assert acc_data._is_all_static_threshold(item) is True

                # 验证 _can_merge_access_detect 返回 False（因为不在灰度列表中）
                assert acc_data._can_merge_access_detect() is False

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
        return_value=STATIC_THRESHOLD_STRATEGY,
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail",
        return_value={"1": [1]},
    )
    def test_scenario_5b_static_threshold_in_grayscale(self, mock_strategy_group, mock_strategy):
        """
        场景 5b：静态阈值策略 + 灰度列表包含 → 触发合并处理
        """
        strategy_group_key = "test_merge_5b"
        acc_data = AccessDataProcess(strategy_group_key)

        # 启用开关且灰度列表包含当前策略
        with mock.patch.object(settings, "ACCESS_DETECT_MERGE_ENABLED", True):
            with mock.patch.object(settings, "ACCESS_DETECT_MERGE_STRATEGY_IDS", [1, 2, 3]):  # 包含策略 ID 1
                # 验证 _can_merge_access_detect 返回 True
                assert acc_data._can_merge_access_detect() is True

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
        return_value=STATIC_THRESHOLD_STRATEGY,
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail",
        return_value={"1": [1]},
    )
    @mock.patch("alarm_backends.core.control.item.Item.query_record", return_value=query_record)
    @mock.patch("alarm_backends.service.detect.process.DetectProcess.push_data")
    @mock.patch("alarm_backends.service.detect.process.DetectProcess.double_check")
    @mock.patch("alarm_backends.service.detect.process.DetectProcess.handle_data")
    @mock.patch("alarm_backends.service.detect.process.DetectProcess.pull_data")
    @mock.patch("alarm_backends.core.control.strategy.Strategy.gen_strategy_snapshot")
    def test_detect_and_push_abnormal_uses_detect_process(
        self,
        mock_gen_snapshot,
        mock_pull_data,
        mock_handle_data,
        mock_double_check,
        mock_push_data,
        mock_query_record,
        mock_strategy_group,
        mock_strategy,
    ):
        """
        测试 _detect_and_push_abnormal 正确复用 DetectProcess
        """
        strategy_group_key = "test_detect_process"
        acc_data = AccessDataProcess(strategy_group_key)

        # 模拟 record_list
        mock_records = [MockRecord(RAW_DATA), MockRecord(RAW_DATA_ZERO)]
        acc_data.record_list = mock_records

        with mock.patch.object(settings, "ACCESS_DETECT_MERGE_ENABLED", True):
            with mock.patch.object(settings, "ACCESS_DETECT_MERGE_STRATEGY_IDS", []):
                # 调用合并处理方法
                acc_data._detect_and_push_abnormal()

                # 验证 DetectProcess 的方法被正确调用
                assert mock_gen_snapshot.called, "gen_strategy_snapshot 应该被调用"
                assert mock_pull_data.called, "pull_data 应该被调用"
                assert mock_handle_data.called, "handle_data 应该被调用"
                assert mock_double_check.called, "double_check 应该被调用"
                assert mock_push_data.called, "push_data 应该被调用"

                # 验证 pull_data 被调用时传入了 inputs 参数
                call_args = mock_pull_data.call_args
                assert call_args is not None
                # pull_data(item, inputs=data_points)
                assert "inputs" in call_args.kwargs or len(call_args.args) > 1
