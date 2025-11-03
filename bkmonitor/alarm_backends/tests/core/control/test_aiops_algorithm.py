"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import pytest
from unittest.mock import MagicMock
from unittest import mock
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy

HOST_ANOMALY_DETECTION_CONFIG = {
    "id": 8,
    "type": "HostAnomalyDetection",
    "level": 1,
    "config": {
        "levels": [1],
    },
    "unit_prefix": "",
}
THRESHOLD_ALGORITHM = {
    "id": 1,
    "type": "Threshold",
    "level": 1,
    "config": [[{"method": "gte", "threshold": 10.0}]],
    "unit_prefix": "",
}


@pytest.fixture
def strategy_cache():
    strategy_cache_obj = MagicMock()
    strategy_cache_obj.get_strategies_map = StrategyCacheManager.get_strategies_map
    return strategy_cache_obj


@pytest.fixture
def strategy():
    strategy_obj = MagicMock()
    strategy_obj.get_trigger_configs = Strategy.get_trigger_configs
    return strategy_obj


def create_strategy_config(algorithms1, algorithms2):
    return {
        "id": 64963,
        "version": "v2",
        "bk_biz_id": 2,
        "name": "omg002",
        "source": "source1",
        "scenario": "os",
        "type": "monitor",
        "items": [
            {
                "id": 7,
                "name": "主机场景",
                "no_data_config": {"level": 2, "continuous": 10, "is_enabled": False, "agg_dimension": []},
                "target": [[]],
                "expression": "a",
                "functions": [],
                "origin_sql": "",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "metric_id": "metric_id",
                        "id": 8,
                        "functions": [],
                        "result_table_id": "system.cpu_detail",
                        "agg_method": "AVG",
                        "agg_interval": 60,
                        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id", "device_name"],
                        "agg_condition": [],
                        "metric_field": "usage",
                        "unit": "",
                    }
                ],
                "algorithms": algorithms1,
                "metric_type": "time_series",
                "time_delay": 0,
            },
            {
                "id": 7,
                "name": "主机场景",
                "no_data_config": {"level": 2, "continuous": 10, "is_enabled": False, "agg_dimension": []},
                "target": [[]],
                "expression": "a",
                "functions": [],
                "origin_sql": "",
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "a",
                        "metric_id": "metric_id",
                        "id": 8,
                        "functions": [],
                        "result_table_id": "system.cpu_detail",
                        "agg_method": "AVG",
                        "agg_interval": 60,
                        "agg_dimension": ["bk_target_ip", "bk_target_cloud_id", "device_name"],
                        "agg_condition": [],
                        "metric_field": "usage",
                        "unit": "",
                    }
                ],
                "algorithms": algorithms2,
                "metric_type": "time_series",
                "time_delay": 0,
            },
        ],
        "detects": [
            {
                "id": 8,
                "level": 1,
                "expression": "",
                "trigger_config": {
                    "count": 10,
                    "uptime": {"calendars": [], "time_ranges": [{"end": "23:59", "start": "00:00"}]},
                    "check_window": 15,
                },
                "recovery_config": {"check_window": 5, "status_setter": "recovery"},
                "connector": "and",
            }
        ],
    }


def test_only_aiops(strategy):
    """
    测试只有AIOPS算法的情况
    """
    algorithms = [HOST_ANOMALY_DETECTION_CONFIG]
    strategy_config = create_strategy_config(algorithms, algorithms)
    trigger_config = strategy.get_trigger_configs(strategy_config)
    expected_check_window_size = 5
    expected_trigger_count = 1
    for detect in strategy_config.get("detects", []):
        level = str(detect["level"])
        actual_check_window_size = trigger_config[level].get("check_window_size")
        actual_trigger_count = trigger_config[level].get("trigger_count")
        assert expected_check_window_size == actual_check_window_size
        assert expected_trigger_count == actual_trigger_count


def test_not_only_aiops(strategy):
    """
    测试有AIOPS算法和非AIOPS算法的情况
    """
    algorithms1 = [
        THRESHOLD_ALGORITHM,
        HOST_ANOMALY_DETECTION_CONFIG,
    ]
    algorithms2 = [
        THRESHOLD_ALGORITHM,
    ]
    strategy_config = create_strategy_config(algorithms1, algorithms2)
    trigger_config = strategy.get_trigger_configs(strategy_config)
    expected_check_window_size = 5
    expected_trigger_count = 1
    for detect in strategy_config.get("detects", []):
        level = str(detect["level"])
        actual_check_window_size = trigger_config[level].get("check_window_size")
        actual_trigger_count = trigger_config[level].get("trigger_count")
        assert expected_check_window_size != actual_check_window_size
        assert expected_trigger_count != actual_trigger_count


def test_only_not_aiops(strategy):
    """
    测试只有非AIOPS算法的情况
    """
    algorithms = [
        THRESHOLD_ALGORITHM,
    ]
    strategy_config = create_strategy_config(algorithms, algorithms)
    trigger_config = strategy.get_trigger_configs(strategy_config)
    expected_check_window_size = 5
    expected_trigger_count = 1
    for detect in strategy_config.get("detects", []):
        level = str(detect["level"])
        actual_check_window_size = trigger_config[level].get("check_window_size")
        actual_trigger_count = trigger_config[level].get("trigger_count")
        assert expected_check_window_size != actual_check_window_size
        assert expected_trigger_count != actual_trigger_count


def test_empty_algorithms(strategy):
    """
    测试空算法的情况
    """
    algorithms = []
    strategy_config = create_strategy_config(algorithms, algorithms)
    trigger_config = strategy.get_trigger_configs(strategy_config)
    expected_check_window_size = 5
    expected_trigger_count = 1
    for detect in strategy_config.get("detects", []):
        level = str(detect["level"])
        actual_check_window_size = trigger_config[level].get("check_window_size")
        actual_trigger_count = trigger_config[level].get("trigger_count")
        assert expected_check_window_size != actual_check_window_size
        assert expected_trigger_count != actual_trigger_count


def test_empty_and_no_aiops_algorithms(strategy):
    """
    测试空算法和非AIOPS算法的情况
    """
    algorithms1 = []
    algorithms2 = [THRESHOLD_ALGORITHM]
    strategy_config = create_strategy_config(algorithms1, algorithms2)
    trigger_config = strategy.get_trigger_configs(strategy_config)
    expected_check_window_size = 5
    expected_trigger_count = 1
    for detect in strategy_config.get("detects", []):
        level = str(detect["level"])
        actual_check_window_size = trigger_config[level].get("check_window_size")
        actual_trigger_count = trigger_config[level].get("trigger_count")
        assert expected_check_window_size != actual_check_window_size
        assert expected_trigger_count != actual_trigger_count


def test_empty_and_aiops_algorithms(strategy):
    """
    测试空算法和AIOPS算法的情况
    """
    algorithms1 = []
    algorithms2 = [HOST_ANOMALY_DETECTION_CONFIG]
    strategy_config = create_strategy_config(algorithms1, algorithms2)
    trigger_config = strategy.get_trigger_configs(strategy_config)
    expected_check_window_size = 5
    expected_trigger_count = 1
    for detect in strategy_config.get("detects", []):
        level = str(detect["level"])
        actual_check_window_size = trigger_config[level].get("check_window_size")
        actual_trigger_count = trigger_config[level].get("trigger_count")
        assert expected_check_window_size == actual_check_window_size
        assert expected_trigger_count == actual_trigger_count


def execute_strategy_test(strategy_config, strategy_cache):
    """执行策略测试的通用方法"""
    with mock.patch("alarm_backends.core.cache.strategy.Strategy.from_models") as mock_from_models:
        mock_strategy = MagicMock()
        mock_strategy.to_dict.return_value = strategy_config
        mock_from_models.return_value = [mock_strategy]

        with mock.patch("alarm_backends.core.cache.strategy.BusinessManager.keys") as mock_biz_keys:
            mock_biz_keys.return_value = [2]

            with mock.patch(
                "alarm_backends.core.cache.strategy.StrategyCacheManager.handle_strategy"
            ) as mock_handle_strategy:
                mock_handle_strategy.return_value = True

                with mock.patch("alarm_backends.core.cache.strategy.StrategyCacheManager.check_related_strategy"):
                    result_map = strategy_cache.get_strategies_map()
                    return result_map


def test_only_aiops_cache(strategy_cache):
    """
    测试只有AIOPS算法的情况
    """
    algorithms = [HOST_ANOMALY_DETECTION_CONFIG]
    strategy_config = create_strategy_config(algorithms, algorithms)

    result_map = execute_strategy_test(strategy_config, strategy_cache)
    expected_check_window = 5
    expected_count = 1

    for strategy_id, strategy_config in result_map.items():
        # 检查 detects 列表中的每个 detect
        for detect in strategy_config.get("detects", []):
            actual_check_window = detect.get("trigger_config", {}).get("check_window")
            actual_count = detect.get("trigger_config", {}).get("count")
            actual_uptime = detect.get("trigger_config", {}).get("uptime")
            assert expected_check_window == actual_check_window
            assert expected_count == actual_count
            assert actual_uptime is not None


def test_not_only_aiops_cache(strategy_cache):
    """
    测试有AIOPS算法和非AIOPS算法的情况
    """
    algorithms1 = [
        THRESHOLD_ALGORITHM,
        HOST_ANOMALY_DETECTION_CONFIG,
    ]
    algorithms2 = [
        THRESHOLD_ALGORITHM,
    ]
    strategy_config = create_strategy_config(algorithms1, algorithms2)

    result_map = execute_strategy_test(strategy_config, strategy_cache)

    expected_check_window = 5
    expected_count = 1

    for strategy_id, strategy_config in result_map.items():
        # 检查 detects 列表中的每个 detect
        for detect in strategy_config.get("detects", []):
            actual_check_window = detect.get("trigger_config", {}).get("check_window")
            actual_count = detect.get("trigger_config", {}).get("count")
            actual_uptime = detect.get("trigger_config", {}).get("uptime")
            assert expected_check_window != actual_check_window
            assert expected_count != actual_count
            assert actual_uptime is not None


def test_empty_aiops_cache(strategy_cache):
    """
    测试空算法的情况
    """
    algorithms = []
    strategy_config = create_strategy_config(algorithms, algorithms)

    result_map = execute_strategy_test(strategy_config, strategy_cache)

    expected_check_window = 5
    expected_count = 1

    for strategy_id, strategy_config in result_map.items():
        # 检查 detects 列表中的每个 detect
        for detect in strategy_config.get("detects", []):
            actual_check_window = detect.get("trigger_config", {}).get("check_window")
            actual_count = detect.get("trigger_config", {}).get("count")
            actual_uptime = detect.get("trigger_config", {}).get("uptime")
            assert expected_check_window != actual_check_window
            assert expected_count != actual_count
            assert actual_uptime is not None


def test_empty_and_no_aiops_cache(strategy_cache):
    """
    测试空算法和非AIOPS算法的情况
    """
    algorithms1 = []
    algorithms2 = [THRESHOLD_ALGORITHM]
    strategy_config = create_strategy_config(algorithms1, algorithms2)

    result_map = execute_strategy_test(strategy_config, strategy_cache)

    expected_check_window = 5
    expected_count = 1

    for strategy_id, strategy_config in result_map.items():
        # 检查 detects 列表中的每个 detect
        for detect in strategy_config.get("detects", []):
            actual_check_window = detect.get("trigger_config", {}).get("check_window")
            actual_count = detect.get("trigger_config", {}).get("count")
            actual_uptime = detect.get("trigger_config", {}).get("uptime")
            assert expected_check_window != actual_check_window
            assert expected_count != actual_count
            assert actual_uptime is not None


def test_empty_and_aiops_algorithms_cache(strategy_cache):
    """
    测试空算法和AIOPS算法的情况
    """
    algorithms1 = []
    algorithms2 = [HOST_ANOMALY_DETECTION_CONFIG]
    strategy_config = create_strategy_config(algorithms1, algorithms2)

    result_map = execute_strategy_test(strategy_config, strategy_cache)

    expected_check_window = 5
    expected_count = 1

    for strategy_id, strategy_config in result_map.items():
        # 检查 detects 列表中的每个 detect
        for detect in strategy_config.get("detects", []):
            actual_check_window = detect.get("trigger_config", {}).get("check_window")
            actual_count = detect.get("trigger_config", {}).get("count")
            actual_uptime = detect.get("trigger_config", {}).get("uptime")
            assert expected_check_window == actual_check_window
            assert expected_count == actual_count
            assert actual_uptime is not None
