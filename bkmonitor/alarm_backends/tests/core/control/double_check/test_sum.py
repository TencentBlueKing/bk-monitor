# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json

import mock
import pytest
from django.conf import settings

from alarm_backends.core.cache import key as redis_keys_collections
from alarm_backends.core.cache.key import DATA_LIST_KEY
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.detect.double_check_strategies.sum import (
    DoubleCheckSumStrategy,
    make_sure_strategy_ids_type,
)
from alarm_backends.service.detect.process import DetectProcess
from alarm_backends.tests.core.control.double_check import make_item_config
from bkmonitor.models import CacheNode

pytestmark = pytest.mark.django_db


@pytest.fixture
def fake_strategy_config():
    CacheNode.refresh_from_settings()
    return {
        "bk_biz_id": 2,
        "items": [
            {
                "query_configs": [
                    {
                        "metric_field": "idle",
                        "agg_dimension": ["ip", "bk_cloud_id"],
                        "id": 2,
                        "agg_method": "SUM",
                        "agg_condition": [],
                        "agg_interval": 60,
                        "result_table_id": "system.cpu_detail",
                        "unit": "%",
                        "data_type_label": "time_series",
                        "metric_id": "bk_monitor.system.cpu_detail.idle",
                        "data_source_label": "bk_monitor",
                    }
                ],
                "algorithms": [
                    {
                        "config": [[{"threshold": 51.0, "method": "lte"}]],
                        "level": 3,
                        "type": "Threshold",
                        "id": 2,
                    },
                ],
                "no_data_config": {"is_enabled": False, "continuous": 5},
                "id": 2,
                "name": "\u7a7a\u95f2\u7387",
                "target": [
                    [
                        {
                            "field": "ip",
                            "method": "eq",
                            "value": [{"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_supplier_id": 0}],
                        }
                    ]
                ],
            }
        ],
        "scenario": "os",
        "actions": [
            {
                "notice_template": {"action_id": 2, "anomaly_template": "aa", "recovery_template": ""},
                "id": 2,
                "notice_group_list": [
                    {
                        "notice_receiver": ["user#test"],
                        "name": "test",
                        "notice_way": {"1": ["weixin"], "3": ["weixin"], "2": ["weixin"]},
                        "notice_group_id": 1,
                        "message": "",
                        "notice_group_name": "test",
                        "id": 1,
                    }
                ],
                "type": "notice",
                "config": {
                    "alarm_end_time": "23:59:59",
                    "send_recovery_alarm": False,
                    "alarm_start_time": "00:00:00",
                    "alarm_interval": 120,
                },
            }
        ],
        "detects": [
            {
                "level": 3,
                "expression": "",
                "connector": "and",
                "trigger_config": {"count": 1, "check_window": 5},
                "recovery_config": {"check_window": 5},
            }
        ],
        "source_type": "BKMONITOR",
        "id": 10,
        "name": "test",
    }


FAKE_TIMESTAMP = 1569246480


def make_fake_query_records(now_count, former_count):
    return [
        {
            "value": former_count,
            "_result_": former_count,
            "time": FAKE_TIMESTAMP - 60,
            "record_id": "c10ad28a0015bac25b56649440db13ee" + f".{FAKE_TIMESTAMP - 60}",
        },
        {
            "value": now_count,
            "_result_": now_count,
            "time": FAKE_TIMESTAMP,
            "record_id": "c10ad28a0015bac25b56649440db13ee" + f".{FAKE_TIMESTAMP}",
        },
    ]


class TestSumDoubleCheck:
    """测试 SUM 聚合时的二次确认"""

    @pytest.fixture(autouse=True)
    def auto_set_strategy_ids(self):
        """保证其他测试不会卡在策略限定上"""
        DoubleCheckSumStrategy.match_strategy_ids = []

    @pytest.mark.parametrize(
        "strategy_ids,hit",
        [
            ([], True),
            ([2, 3, 4], True),
            ([1], True),
            (["1"], True),
            ("1", True),
        ],
    )
    def test_double_check_strategy_ids(self, fake_strategy_config, strategy_ids, hit):
        """测试策略白名单"""
        strategy = Strategy(1, fake_strategy_config)
        # 当前 Strategy 和 Item 事实意义上是一对一
        dc_strategy = DoubleCheckSumStrategy(item=strategy.items[0])
        dc_strategy.match_strategy_ids = make_sure_strategy_ids_type(strategy_ids)
        assert dc_strategy.check_hit() == hit

    @pytest.mark.parametrize("case", [[1, 2, 3], "1,2,3", "1,2,3,", ["1", "2", "3"]])
    def test_make_sure_strategy_ids_type(self, case):
        assert make_sure_strategy_ids_type(case) == [1, 2, 3]

    @pytest.mark.parametrize(
        "data_labels_params,hit",
        [
            (
                {
                    "query_configs": [
                        {
                            "metric_field": "idle",
                            "agg_dimension": ["ip", "bk_cloud_id"],
                            "id": 2,
                            "agg_method": "SUM",
                            "agg_condition": [],
                            "agg_interval": 60,
                            "result_table_id": "system.cpu_detail",
                            "unit": "%",
                            "data_type_label": "event",
                            "metric_id": "bk_monitor.system.cpu_detail.idle",
                            "data_source_label": "bk_monitor",
                        }
                    ],
                },
                False,
            ),
            (
                {
                    "query_configs": [
                        {
                            "metric_field": "idle",
                            "agg_dimension": ["ip", "bk_cloud_id"],
                            "id": 2,
                            "agg_method": "COUNT",
                            "agg_condition": [],
                            "agg_interval": 60,
                            "result_table_id": "system.cpu_detail",
                            "unit": "%",
                            "data_type_label": "time_series",
                            "metric_id": "bk_monitor.system.cpu_detail.idle",
                            "data_source_label": "bk_monitor",
                        }
                    ],
                },
                False,
            ),
            (
                {
                    "query_configs": [
                        {
                            "metric_field": "idle",
                            "agg_dimension": ["ip", "bk_cloud_id"],
                            "id": 2,
                            "agg_method": "SUM",
                            "agg_condition": [],
                            "agg_interval": 60,
                            "result_table_id": "system.cpu_detail",
                            "unit": "%",
                            "data_type_label": "time_series",
                            "metric_id": "bk_monitor.system.cpu_detail.idle",
                            "data_source_label": "bk_monitor",
                        }
                    ],
                },
                True,
            ),
        ],
    )
    def test_double_check_scopes(self, fake_strategy_config, data_labels_params, hit):
        """测试二次确认限定范围"""
        _strategy_config = dict(fake_strategy_config)
        _strategy_config["items"] = [make_item_config(data_labels_params)]
        strategy = Strategy(1, _strategy_config)

        # 当前 Strategy 和 Item 事实意义上是一对一
        dc_strategy = DoubleCheckSumStrategy(item=strategy.items[0])
        assert dc_strategy.check_hit() == hit

    @pytest.mark.parametrize(
        "agg_method_params,hit",
        [
            (
                {
                    "query_configs": [
                        {
                            "metric_field": "idle",
                            "agg_dimension": ["ip", "bk_cloud_id"],
                            "id": 2,
                            "agg_method": "SUM",
                            "agg_condition": [],
                            "agg_interval": 60,
                            "result_table_id": "system.cpu_detail",
                            "unit": "%",
                            "data_type_label": "time_series",
                            "metric_id": "bk_monitor.system.cpu_detail.idle",
                            "data_source_label": "bk_monitor",
                        }
                    ],
                },
                True,
            ),
            (
                {},
                False,
            ),
        ],
    )
    def test_double_check_agg_method(self, fake_strategy_config, agg_method_params, hit):
        """测试二次确认聚合方法"""

        _strategy_config = dict(fake_strategy_config)
        _strategy_config["items"] = [make_item_config(agg_method_params)]
        strategy = Strategy(1, _strategy_config)

        # 当前 Strategy 和 Item 事实意义上是一对一
        dc_strategy = DoubleCheckSumStrategy(item=strategy.items[0])
        assert dc_strategy.check_hit() == hit

    @pytest.mark.parametrize(
        "algorithm_type_params,hit",
        [
            (
                {
                    "query_configs": [
                        {
                            "metric_field": "idle",
                            "agg_dimension": ["ip", "bk_cloud_id"],
                            "id": 2,
                            "agg_method": "SUM",
                            "agg_condition": [],
                            "agg_interval": 60,
                            "result_table_id": "system.cpu_detail",
                            "unit": "%",
                            "data_type_label": "time_series",
                            "metric_id": "bk_monitor.system.cpu_detail.idle",
                            "data_source_label": "bk_monitor",
                        }
                    ],
                    "algorithms": [
                        {
                            "config": [[{"threshold": 51.0, "method": "gte"}]],
                            "level": 3,
                            "type": "SimpleYearRound",
                            "id": 2,
                        },
                    ],
                },
                False,
            ),
            (
                {
                    "query_configs": [
                        {
                            "metric_field": "idle",
                            "agg_dimension": ["ip", "bk_cloud_id"],
                            "id": 2,
                            "agg_method": "SUM",
                            "agg_condition": [],
                            "agg_interval": 60,
                            "result_table_id": "system.cpu_detail",
                            "unit": "%",
                            "data_type_label": "time_series",
                            "metric_id": "bk_monitor.system.cpu_detail.idle",
                            "data_source_label": "bk_monitor",
                        }
                    ],
                },
                True,
            ),
            (
                {
                    "query_configs": [
                        {
                            "metric_field": "idle",
                            "agg_dimension": ["ip", "bk_cloud_id"],
                            "id": 2,
                            "agg_method": "SUM",
                            "agg_condition": [],
                            "agg_interval": 60,
                            "result_table_id": "system.cpu_detail",
                            "unit": "%",
                            "data_type_label": "time_series",
                            "metric_id": "bk_monitor.system.cpu_detail.idle",
                            "data_source_label": "bk_monitor",
                        }
                    ],
                    "algorithms": [
                        {
                            "config": [[{"threshold": 51.0, "method": "gte"}]],
                            "level": 3,
                            "type": "SimpleRingRatio",
                            "id": 2,
                        },
                        {
                            "config": [[{"threshold": 51.0, "method": "gte"}]],
                            "level": 3,
                            "type": "OsRestart",
                            "id": 2,
                        },
                    ],
                },
                True,
            ),
        ],
    )
    def test_double_check_algorithm_type(self, fake_strategy_config, algorithm_type_params, hit):
        """测试二次确认检测算法"""

        _strategy_config = dict(fake_strategy_config)
        _strategy_config["items"] = [make_item_config(algorithm_type_params)]
        strategy = Strategy(1, _strategy_config)

        # 当前 Strategy 和 Item 事实意义上是一对一
        dc_strategy = DoubleCheckSumStrategy(item=strategy.items[0])
        assert dc_strategy.check_hit() == hit

    @pytest.mark.parametrize(
        "algorithm_type_params,best",
        [
            (
                {
                    "algorithms": [
                        {
                            "config": [[{"threshold": 51.0, "method": "gte"}]],
                            "level": 3,
                            "type": "SimpleRingRatio",
                            "id": 2,
                        },
                        {
                            "config": [[{"threshold": 51.0, "method": "gte"}]],
                            "level": 3,
                            "type": "OsRestart",
                            "id": 2,
                        },
                    ],
                },
                "SimpleRingRatio",
            ),
            (
                {
                    "algorithms": [
                        {
                            "config": [[{"threshold": 51.0, "method": "gte"}]],
                            "level": 3,
                            "type": "SimpleRingRatio",
                            "id": 2,
                        },
                        {
                            "config": [[{"threshold": 51.0, "method": "gte"}]],
                            "level": 3,
                            "type": "AdvancedRingRatio",
                            "id": 2,
                        },
                        {
                            "config": [[{"threshold": 51.0, "method": "gte"}]],
                            "level": 3,
                            "type": "Threshold",
                            "id": 2,
                        },
                    ],
                },
                "AdvancedRingRatio",
            ),
        ],
    )
    def test_double_best_algorithm_type(self, fake_strategy_config, algorithm_type_params, best):
        """测试二次确认检测算法"""

        _strategy_config = dict(fake_strategy_config)
        _strategy_config.update(
            {
                "query_configs": [
                    {
                        "metric_field": "idle",
                        "agg_dimension": ["ip", "bk_cloud_id"],
                        "id": 2,
                        "agg_method": "SUM",
                        "agg_condition": [],
                        "agg_interval": 60,
                        "result_table_id": "system.cpu_detail",
                        "unit": "%",
                        "data_type_label": "time_series",
                        "metric_id": "bk_monitor.system.cpu_detail.idle",
                        "data_source_label": "bk_monitor",
                    }
                ],
            }
        )
        _strategy_config["items"] = [make_item_config(algorithm_type_params)]
        strategy = Strategy(1, _strategy_config)

        # 当前 Strategy 和 Item 事实意义上是一对一
        dc_strategy = DoubleCheckSumStrategy(item=strategy.items[0])
        assert dc_strategy.get_best_match_algorithm() == best

    @pytest.mark.parametrize(
        "now_count,former_count,expected",
        [(10, 10, False), (10, 20, True), (18, 20, True), (19, 20, False), (20, 10, False)],
    )
    def test_sum_double_check(self, fake_strategy_config, now_count, former_count, expected):
        """测试二次确认逻辑"""
        settings.DOUBLE_CHECK_SUM_STRATEGY_IDS = [1]
        with mock.patch(
            "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
            return_value=fake_strategy_config,
        ), mock.patch(
            "alarm_backends.core.control.item.Item.query_record",
            return_value=make_fake_query_records(now_count, former_count),
        ):
            strategy_id = fake_strategy_config["id"]
            item_id = fake_strategy_config["items"][0]["id"]
            data_list_key = redis_keys_collections.DATA_LIST_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
            DATA_LIST_KEY.client.lpush(
                data_list_key,
                json.dumps(
                    {
                        "value": now_count,
                        "_result_": now_count,
                        "time": FAKE_TIMESTAMP,
                        "record_id": "c10ad28a0015bac25b56649440db13ee" + f".{FAKE_TIMESTAMP}",
                    }
                ),
            )

            processor = DetectProcess(strategy_id)
            processor.process()
            # 默认策略id 10 不再灰度名单
            assert DoubleCheckSumStrategy.DOUBLE_CHECK_CONTEXT_KEY not in processor.outputs[item_id][0].get(
                "context", {}
            )

            strategy = Strategy(1, fake_strategy_config)
            dc_strategy = DoubleCheckSumStrategy(item=strategy.items[0])
            dc_strategy.double_check(processor.outputs[item_id])

            assert (
                DoubleCheckSumStrategy.DOUBLE_CHECK_CONTEXT_KEY in processor.outputs[item_id][0].get("context", {})
            ) == expected
