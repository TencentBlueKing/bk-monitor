"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import copy
import gzip
import json
import time
from collections import defaultdict

from unittest import mock
import pytest
from django.conf import settings

from alarm_backends.core.cache import key
from alarm_backends.service.access.data import AccessBatchDataProcess, AccessDataProcess
from bkmonitor.models import CacheNode
from bkmonitor.utils.common_utils import count_md5

from .config import (
    RAW_DATA,
    RAW_DATA_NONE,
    RAW_DATA_ZERO,
    STANDARD_DATA,
    STRATEGY_CONFIG_V3,
)

query_record = [RAW_DATA, RAW_DATA_ZERO, RAW_DATA_NONE]

pytestmark = pytest.mark.django_db


class MockRecord:
    def __init__(self, attrs):
        self.data = copy.deepcopy(attrs)
        self.__dict__.update(attrs)

        self.is_duplicate = False
        self.inhibitions = defaultdict(lambda: False)


class TestAccessDataProcess:
    def setup_method(self):
        CacheNode.refresh_from_settings()
        c = key.ACCESS_BATCH_DATA_KEY.client
        c.flushall()

    def teardown_method(self):
        pass

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG_V3
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    @mock.patch("alarm_backends.core.control.item.Item.query_record", return_value=query_record)
    def test_pull(self, mock_strategy, mock_strategy_group, mock_records):
        strategy_group_key = "123456789"
        acc_data = AccessDataProcess(strategy_group_key)
        acc_data.pull()
        assert len(acc_data.record_list) == 2
        assert acc_data.record_list
        assert acc_data.record_list[0].raw_data == {
            "bk_target_ip": "127.0.0.2",
            "load5": 0,
            "bk_target_cloud_id": "0",
            "_time_": 1569246420,
            "_result_": 0,
        }
        assert acc_data.record_list[1].raw_data == {
            "bk_target_ip": "127.0.0.1",
            "load5": 1.381234,
            "bk_target_cloud_id": "0",
            "_time_": 1569246480,
            "_result_": 1.381234,
        }
        assert mock_strategy.call_count == 1
        assert mock_records.call_count == 1
        assert mock_strategy_group.call_count == 1

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG_V3
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    @mock.patch("alarm_backends.core.control.item.Item.query_record", return_value=query_record)
    @mock.patch("alarm_backends.service.access.tasks.run_access_batch_data")
    def test_pull_batch(self, mock_batch, mock_records, mock_strategy_group, mock_strategy):
        strategy_group_key = "123456789"
        acc_data = AccessDataProcess(strategy_group_key)
        settings.ACCESS_DATA_BATCH_PROCESS_THRESHOLD = 2
        settings.ACCESS_DATA_BATCH_PROCESS_SIZE = 1
        acc_data.pull()

        c = key.ACCESS_BATCH_DATA_KEY.client
        data_key = key.ACCESS_BATCH_DATA_KEY.get_key(
            strategy_group_key=strategy_group_key, sub_task_id=f"{acc_data.batch_timestamp}.2"
        )
        data = c.get(data_key)
        result = json.loads(gzip.decompress(base64.b64decode(data)).decode("utf-8"))
        assert len(result) == 2
        assert (
            json.dumps(result[0], sort_keys=True) == '{"_result_": 0, "_time_": 1569246420, "bk_target_cloud_id":'
            ' "0", "bk_target_ip": "127.0.0.2", "load5": 0}'
        )
        assert len(acc_data.record_list) == 1
        assert mock_batch.delay.call_count == 1

        p = AccessBatchDataProcess(strategy_group_key=strategy_group_key, sub_task_id=f"{acc_data.batch_timestamp}.2")
        p.filters = []
        p.process()
        assert len(p.record_list) == 1

        result = c.lrange(
            key.ACCESS_BATCH_DATA_RESULT_KEY.get_key(
                strategy_group_key=strategy_group_key, timestamp=acc_data.batch_timestamp
            ),
            0,
            -1,
        )
        assert len(result) == 1

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG_V3
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    def test_push(self, mock_strategy, mock_strategy_group):
        strategy_id = 1
        item_id = 1
        strategy_group_key = "123456789"
        acc_data = AccessDataProcess(strategy_group_key)
        record = MockRecord(STANDARD_DATA)
        record.inhibitions = {item_id: False}
        record.items = [acc_data.items[0]]
        record.is_retains = {item_id: True}
        acc_data.record_list = [
            record,
        ]
        acc_data.push()
        assert mock_strategy.call_count == 1

        client = key.DATA_SIGNAL_KEY.client
        assert str(strategy_id) == client.rpop(key.DATA_SIGNAL_KEY.get_key())

        client = key.DATA_LIST_KEY.client
        output_key = key.DATA_LIST_KEY.get_key(strategy_id=strategy_id, item_id=item_id)
        expected_data = copy.deepcopy(STANDARD_DATA)
        assert client.rpop(output_key) == json.dumps(expected_data)

        client = key.NOISE_REDUCE_TOTAL_KEY.client
        noise_dimension_hash = count_md5(["bk_target_ip", "bk_target_cloud_id"])
        noise_dimension_data_hash = count_md5(STANDARD_DATA["dimensions"])
        record_key = key.NOISE_REDUCE_TOTAL_KEY.get_key(
            strategy_id=strategy_id, noise_dimension_hash=noise_dimension_hash
        )
        assert set(client.zrangebyscore(record_key, STANDARD_DATA["time"], int(time.time() + 1))) == {
            noise_dimension_data_hash
        }

    strategy_dict = copy.deepcopy(STRATEGY_CONFIG_V3)
    strategy_dict["notice"]["options"].pop("noise_reduce_config", None)

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=strategy_dict
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    def test_push_without_noise(self, mock_strategy, mock_strategy_group):
        strategy_id = 1
        item_id = 1
        start_timestamp = int(time.time()) - 1
        strategy_group_key = "123456789"
        acc_data = AccessDataProcess(strategy_group_key)
        record = MockRecord(STANDARD_DATA)
        record.items = [acc_data.items[0]]
        record.is_retains = {item_id: True}
        acc_data.record_list = [
            record,
        ]
        acc_data.push()
        assert mock_strategy.call_count == 1
        client = key.NOISE_REDUCE_TOTAL_KEY.client
        noise_dimension_hash = count_md5(["bk_target_ip", "bk_target_cloud_id"])
        record_key = key.NOISE_REDUCE_TOTAL_KEY.get_key(
            strategy_id=strategy_id, noise_dimension_hash=noise_dimension_hash
        )
        assert client.zrangebyscore(record_key, start_timestamp, int(time.time() + 1)) == []


class TestLimitRecordsByTimePoints:
    """测试 _limit_records_by_time_points 方法（方案 B：限制处理时间点数量）"""

    def setup_method(self):
        CacheNode.refresh_from_settings()

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG_V3
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    def test_limit_records_empty_list(self, mock_strategy_group, mock_strategy):
        """测试空记录列表"""
        strategy_group_key = "test_empty"
        acc_data = AccessDataProcess(strategy_group_key)

        records, last_time_point = acc_data._limit_records_by_time_points([])

        assert records == []
        assert last_time_point is None

    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG_V3
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    def test_limit_records_under_limit(self, mock_strategy_group, mock_strategy):
        """测试时间点数量未超限 - 全部处理，无限制"""
        strategy_group_key = "test_under_limit"
        acc_data = AccessDataProcess(strategy_group_key)

        # 创建 5 个不同时间点的记录（默认限制是 10）
        records = [
            MockRecord({"time": 100, "value": 1}),
            MockRecord({"time": 200, "value": 2}),
            MockRecord({"time": 300, "value": 3}),
            MockRecord({"time": 400, "value": 4}),
            MockRecord({"time": 500, "value": 5}),
        ]

        result_records, last_time_point = acc_data._limit_records_by_time_points(records)

        assert len(result_records) == 5
        assert last_time_point is None  # 未触发限制

    @mock.patch("django.conf.settings.ACCESS_DATA_MAX_TIME_POINTS", 3)
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG_V3
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    def test_limit_records_over_limit(self, mock_strategy_group, mock_strategy):
        """测试时间点数量超限 - 处理前 N 个，丢弃其余"""
        strategy_group_key = "test_over_limit"
        acc_data = AccessDataProcess(strategy_group_key)

        # 创建 5 个不同时间点的记录，限制为 3
        records = [
            MockRecord({"time": 100, "value": 1}),
            MockRecord({"time": 200, "value": 2}),
            MockRecord({"time": 300, "value": 3}),
            MockRecord({"time": 400, "value": 4}),
            MockRecord({"time": 500, "value": 5}),
        ]

        result_records, last_time_point = acc_data._limit_records_by_time_points(records)

        assert len(result_records) == 3
        assert last_time_point == 300  # 最后处理的时间点
        # 验证保留的是前 3 个时间点
        assert all(r.time <= 300 for r in result_records)

    @mock.patch("django.conf.settings.ACCESS_DATA_MAX_TIME_POINTS", 2)
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG_V3
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    def test_limit_records_multi_series_same_time(self, mock_strategy_group, mock_strategy):
        """测试同一时间点多序列数据 - 完整处理或完整丢弃"""
        strategy_group_key = "test_multi_series"
        acc_data = AccessDataProcess(strategy_group_key)

        # 创建记录：时间点 100 有 3 条，时间点 200 有 2 条，时间点 300 有 1 条
        # 限制为 2 个时间点
        records = [
            MockRecord({"time": 100, "value": 1, "ip": "1.1.1.1"}),
            MockRecord({"time": 100, "value": 2, "ip": "1.1.1.2"}),
            MockRecord({"time": 100, "value": 3, "ip": "1.1.1.3"}),
            MockRecord({"time": 200, "value": 4, "ip": "1.1.1.1"}),
            MockRecord({"time": 200, "value": 5, "ip": "1.1.1.2"}),
            MockRecord({"time": 300, "value": 6, "ip": "1.1.1.1"}),
        ]

        result_records, last_time_point = acc_data._limit_records_by_time_points(records)

        assert len(result_records) == 5  # 时间点 100 (3条) + 时间点 200 (2条)
        assert last_time_point == 200
        # 验证时间点 300 的数据被完全丢弃
        assert all(r.time <= 200 for r in result_records)
        # 验证时间点 100 的所有 3 条数据都被保留
        assert len([r for r in result_records if r.time == 100]) == 3

    @mock.patch("django.conf.settings.ACCESS_DATA_MAX_TIME_POINTS", 2)
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG_V3
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    def test_limit_records_unordered_times(self, mock_strategy_group, mock_strategy):
        """测试时间戳乱序的情况 - 应按排序后的时间点顺序处理"""
        strategy_group_key = "test_unordered"
        acc_data = AccessDataProcess(strategy_group_key)

        # 创建乱序的记录，限制为 2 个时间点
        records = [
            MockRecord({"time": 300, "value": 3}),
            MockRecord({"time": 100, "value": 1}),
            MockRecord({"time": 500, "value": 5}),
            MockRecord({"time": 200, "value": 2}),
        ]

        result_records, last_time_point = acc_data._limit_records_by_time_points(records)

        assert len(result_records) == 2
        assert last_time_point == 200  # 排序后前 2 个时间点是 100 和 200
        # 验证保留的是时间最早的 2 个点
        result_times = {r.time for r in result_records}
        assert result_times == {100, 200}


# LOG 类型策略配置（用于测试非时序数据不触发限制）
STRATEGY_CONFIG_LOG = copy.deepcopy(STRATEGY_CONFIG_V3)
STRATEGY_CONFIG_LOG["items"][0]["query_configs"][0]["data_type_label"] = "log"


class TestLimitRecordsByTimePointsLogType:
    """测试非时序数据类型不触发限制"""

    def setup_method(self):
        CacheNode.refresh_from_settings()

    @mock.patch("django.conf.settings.ACCESS_DATA_MAX_TIME_POINTS", 2)
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_by_id", return_value=STRATEGY_CONFIG_LOG
    )
    @mock.patch(
        "alarm_backends.core.cache.strategy.StrategyCacheManager.get_strategy_group_detail", return_value={"1": [1]}
    )
    def test_limit_records_log_type_not_limited(self, mock_strategy_group, mock_strategy):
        """测试 LOG 类型数据不触发时间点限制"""
        strategy_group_key = "test_log_type"
        acc_data = AccessDataProcess(strategy_group_key)

        # 创建 5 个时间点的记录，即使限制为 2，LOG 类型也不应触发限制
        records = [
            MockRecord({"time": 100, "value": 1}),
            MockRecord({"time": 200, "value": 2}),
            MockRecord({"time": 300, "value": 3}),
            MockRecord({"time": 400, "value": 4}),
            MockRecord({"time": 500, "value": 5}),
        ]

        result_records, last_time_point = acc_data._limit_records_by_time_points(records)

        # LOG 类型不触发限制，全部保留
        assert len(result_records) == 5
        assert last_time_point is None
