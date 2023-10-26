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
from unittest import TestCase

import mock
import pytest
from six.moves import map

from alarm_backends.constants import LATEST_POINT_WITH_ALL_KEY
from alarm_backends.core.detect_result import ANOMALY_LABEL, CheckResult
from alarm_backends.service.detect.process import DetectProcess
from bkmonitor.models import CacheNode, CacheRouter

pytestmark = pytest.mark.django_db


strategy_config = {
    "bk_biz_id": 2,
    "items": [
        {
            "query_configs": [
                {
                    "metric_field": "idle",
                    "agg_dimension": ["ip", "bk_cloud_id"],
                    "id": 2,
                    "agg_method": "AVG",
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
                    "type": "Threshold",
                    "id": 2,
                },
                {
                    "config": [[{"threshold": 100, "method": "lte"}]],
                    "level": 3,
                    "type": "Threshold",
                    "id": 3,
                },
            ],
            "no_data_config": {"is_enabled": False, "continuous": 5},
            "id": 2,
            "name": "\u7a7a\u95f2\u7387",
            "target": [
                [{"field": "ip", "method": "eq", "value": [{"ip": "127.0.0.1", "bk_cloud_id": 0, "bk_supplier_id": 0}]}]
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
    "id": 1,
    "name": "test",
}


class TestProcessorViews(TestCase):
    def setUp(self) -> None:
        CacheRouter.get_node_by_strategy_id(0)
        CacheNode.refresh_from_settings()

    def test_processor_handle_with_empty_queue(self):
        with mock.patch(
            "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=strategy_config
        ):
            processor = DetectProcess(1)
            processor.process()

    def test_processor_handle(self):
        with mock.patch(
            "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=strategy_config
        ):
            records = [
                {
                    "record_id": "342a08e0f85f169a7e099c18db3708ed.1569246480",
                    "value": 99,
                    "values": {"timestamp": 1569246480, "load5": 99},
                    "dimensions": {"ip": "127.0.0.1"},
                    "time": 1569246480,
                },
                {
                    "record_id": "2a1850513fa6018c435f9b6359b3fa7d.1569246480",
                    "value": 50.1,
                    "values": {"timestamp": 1569246480, "load5": 50.1},
                    "dimensions": {"ip": "10.0.0.1"},
                    "time": 1569246480,
                },
            ]
            dumped_records = list(map(json.dumps, records))

            # 环境定义，和mock的strategy_config保持一致
            # strategy id : 1
            strategy_id = 1
            # items:
            #   item id : 2
            item_id = 2
            # level : 3
            level = 3

            from alarm_backends.core.cache import key

            redis_client = key.DATA_LIST_KEY.client
            redis_client.lpush(key.DATA_LIST_KEY.get_key(strategy_id=strategy_id, item_id=item_id), *dumped_records)

            processor = DetectProcess(1)
            processor.process()

            # 校验策略配置准确性
            assert processor.strategy.id == strategy_id
            assert [item.id for item in processor.strategy.items] == [item_id]
            assert [_a["level"] for _a in processor.strategy.items[0].algorithms] == [level, level]

            # 校验整理处理流程输入/输出
            assert list(processor.inputs.keys()) == [item_id]
            assert len(processor.inputs[item_id]) == 2
            item_outputs = processor.outputs[item_id]
            assert len(item_outputs) == 1
            anomaly_info = item_outputs[0]

            # check ANOMALY_SIGNAL_KEY
            signal_client = key.ANOMALY_SIGNAL_KEY.client
            signal_len = signal_client.llen(key.ANOMALY_SIGNAL_KEY.get_key())
            assert signal_len == 1
            signal_body = signal_client.lrange(key.ANOMALY_SIGNAL_KEY.get_key(), 0, 0)[0]
            assert signal_body == "{strategy_id}.{item_id}".format(strategy_id=strategy_id, item_id=item_id)
            assert 0 < signal_client.ttl(key.ANOMALY_SIGNAL_KEY.get_key()) <= key.ANOMALY_SIGNAL_KEY.ttl

            # check ANOMALY_LIST_KEY
            client = key.ANOMALY_LIST_KEY.client
            list_key = key.ANOMALY_LIST_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
            anomaly_queue_len = client.llen(list_key)
            assert anomaly_queue_len == 1
            anomaly_list = client.lrange(list_key, 0, anomaly_queue_len - 1)
            assert json.loads(anomaly_list[0]) == anomaly_info
            assert 0 < client.ttl(list_key) <= key.ANOMALY_LIST_KEY.ttl

            # check LAST_CHECKPOINTS_CACHE_KEY
            client = key.LAST_CHECKPOINTS_CACHE_KEY.client
            last_checkpoints_key = key.LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=strategy_id, item_id=item_id)

            # field_list 第一个异常点，第二个正常点
            dimensions_md5_list = [record["record_id"].split(".")[0] for record in records]
            dimensions_md5_list.append(LATEST_POINT_WITH_ALL_KEY)
            field_list = [
                key.LAST_CHECKPOINTS_CACHE_KEY.get_field(dimensions_md5=d, level=level) for d in dimensions_md5_list
            ]

            for field in field_list:
                assert client.hexists(last_checkpoints_key, field)

            assert "1569246480" == client.hget(last_checkpoints_key, field_list[0])
            assert 0 < client.ttl(last_checkpoints_key) <= key.LAST_CHECKPOINTS_CACHE_KEY.ttl
            # 去掉__ALL__
            dimensions_md5_list.pop()

            # check CHECK_RESULT_CACHE_KEY
            client = key.CHECK_RESULT_CACHE_KEY.client
            anomaly_timestamps = []
            for dimensions_md5 in dimensions_md5_list:
                check_results = client.zrangebyscore(
                    name=key.CHECK_RESULT_CACHE_KEY.get_key(
                        strategy_id=strategy_id, item_id=item_id, dimensions_md5=dimensions_md5, level=level
                    ),
                    min=1569246480,
                    max=1569246480,
                    withscores=True,
                )
                for label, score in check_results:
                    if label.endswith(ANOMALY_LABEL):
                        anomaly_timestamps.append(int(score))
            assert len(anomaly_timestamps) == 1

    def test_checkresult_pipeline(self):
        redis_pipeline = CheckResult(strategy_id=1, item_id=2, dimensions_md5="md5_str", level="1").pipeline()
        assert redis_pipeline is CheckResult(strategy_id=1, item_id=2, dimensions_md5="md5_str", level="1").CHECK_RESULT
