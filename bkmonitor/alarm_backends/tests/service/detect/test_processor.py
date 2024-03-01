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
import copy
import json
from unittest import TestCase

import mock
import pytest
from six.moves import map

from alarm_backends.constants import LATEST_POINT_WITH_ALL_KEY
from alarm_backends.core.detect_result import ANOMALY_LABEL, CheckResult
from alarm_backends.core.storage.redis_cluster import get_node_by_strategy_id
from alarm_backends.service.detect.process import DetectProcess
from bkmonitor.models import CacheNode

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
    "update_time": 1569246480,
    "source_type": "BKMONITOR",
    "id": 1,
    "name": "test",
}


class TestProcessorViews(TestCase):
    def setUp(self) -> None:
        get_node_by_strategy_id(0)
        CacheNode.refresh_from_settings()

    def test_processor_handle_with_empty_queue(self):
        with mock.patch(
            "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
            return_value=copy.deepcopy(strategy_config),
        ):
            processor = DetectProcess("1")
            processor.process()

    def test_processor_handle(self):
        with mock.patch(
            "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id",
            return_value=copy.deepcopy(strategy_config),
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
                    "record_id": "2a1850513fa6018c435f9b6359b3fa7d.1569246481",
                    "value": 50.1,
                    "values": {"timestamp": 1569246481, "load5": 50.1},
                    "dimensions": {"ip": "10.0.0.1"},
                    # 数据点时间戳错开，避免检测记录断言不准确
                    "time": 1569246481,
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
            data_channel = key.DATA_LIST_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
            redis_client.lpush(data_channel, *dumped_records)

            processor = DetectProcess(str(strategy_id))
            processor.process()

            # 待检测队列已将读取数据删除
            assert redis_client.llen(data_channel) == 0

            # 校验策略配置准确性
            assert processor.strategy.id == str(strategy_id)
            assert [item.id for item in processor.strategy.items] == [item_id]
            assert [_a["level"] for _a in processor.strategy.items[0].algorithms] == [level, level]

            # 校验整理处理流程输入/输出
            assert list(processor.inputs.keys()) == [item_id]
            assert len(processor.inputs[item_id]) == 2
            item_outputs = processor.outputs[item_id]
            assert len(item_outputs) == 1

            # check ANOMALY_SIGNAL_KEY
            signal_client = key.ANOMALY_SIGNAL_KEY.client
            assert signal_client.llen(key.ANOMALY_SIGNAL_KEY.get_key()) == 1
            signal_body = signal_client.lrange(key.ANOMALY_SIGNAL_KEY.get_key(), 0, -1)[0]
            assert signal_body == "{strategy_id}.{item_id}".format(strategy_id=strategy_id, item_id=item_id)
            assert 0 < signal_client.ttl(key.ANOMALY_SIGNAL_KEY.get_key()) <= key.ANOMALY_SIGNAL_KEY.ttl

            # check STRATEGY_SNAPSHOT_KEY
            anomaly_info = copy.deepcopy(item_outputs[0])
            snapshot_key = anomaly_info.pop("strategy_snapshot_key")
            # 检测异常信息中的策略快照唯一键有效性：能从快照缓存中取出数据说明有效
            assert snapshot_key == key.STRATEGY_SNAPSHOT_KEY.get_key(
                strategy_id=strategy_id, update_time=strategy_config["update_time"]
            )
            assert json.loads(key.STRATEGY_SNAPSHOT_KEY.client.get(snapshot_key)) == strategy_config

            # check anomaly_info structure
            anomaly_info["anomaly"][str(level)].pop("anomaly_time")
            assert anomaly_info == {
                "data": records[0],
                "anomaly": {
                    str(level): {
                        "anomaly_message": "空闲率 >= 51.0% 同时  <= 100.0%, 当前值99%",
                        "anomaly_id": f"{records[0]['record_id']}.{strategy_id}.{item_id}.{level}",
                    }
                },
            }

            # check ANOMALY_LIST_KEY
            client = key.ANOMALY_LIST_KEY.client
            list_key = key.ANOMALY_LIST_KEY.get_key(strategy_id=strategy_id, item_id=item_id)

            anomaly_list = client.lrange(list_key, 0, -1)
            assert len(anomaly_list) == 1
            assert json.loads(anomaly_list[0]) == item_outputs[0]
            assert 0 < client.ttl(list_key) <= key.ANOMALY_LIST_KEY.ttl

            # check LAST_CHECKPOINTS_CACHE_KEY
            client = key.LAST_CHECKPOINTS_CACHE_KEY.client
            last_checkpoints_key = key.LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=strategy_id, item_id=item_id)

            # record_id 生成规则：{dimensions_md5}.{timestamp}
            last_checkpoints_mapping = {
                key.LAST_CHECKPOINTS_CACHE_KEY.get_field(
                    dimensions_md5=record["record_id"].split(".")[0], level=level
                ): str(record["time"])
                for record in records
            }
            # 本次 detect 数据点的最大时间戳
            last_checkpoints_mapping[
                key.LAST_CHECKPOINTS_CACHE_KEY.get_field(dimensions_md5=LATEST_POINT_WITH_ALL_KEY, level=level)
            ] = "1569246481"
            assert client.hgetall(last_checkpoints_key) == last_checkpoints_mapping
            assert 0 < client.ttl(last_checkpoints_key) <= key.LAST_CHECKPOINTS_CACHE_KEY.ttl

            # check CHECK_RESULT_CACHE_KEY
            client = key.CHECK_RESULT_CACHE_KEY.client
            dimensions_md5_list = [record["record_id"].split(".")[0] for record in records]
            for dimensions_md5 in dimensions_md5_list:
                check_results = client.zrangebyscore(
                    name=key.CHECK_RESULT_CACHE_KEY.get_key(
                        strategy_id=strategy_id, item_id=item_id, dimensions_md5=dimensions_md5, level=level
                    ),
                    min=records[0]["time"],
                    max=records[1]["time"],
                    withscores=True,
                )
                # 无论是否异常都会有对应数据点的检测记录
                # records 代表两条不同的 time series，每条 time series 都有一个数据点
                assert len(check_results) == 1
                for label, score in check_results:
                    if label.endswith(ANOMALY_LABEL):
                        assert score == records[0]["time"]
                        assert label == f"{records[0]['time']}|{ANOMALY_LABEL}"
                    else:
                        assert score == records[1]["time"]
                        assert label == f"{records[1]['time']}|{records[1]['value']}"

    def test_check_result_pipeline(self):
        redis_pipeline = CheckResult(strategy_id=1, item_id=2, dimensions_md5="md5_str", level="1").pipeline()
        assert redis_pipeline is CheckResult(strategy_id=1, item_id=2, dimensions_md5="md5_str", level="1").CHECK_RESULT
