# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.test import TestCase
from mock import MagicMock, patch

from alarm_backends.constants import NO_DATA_LEVEL, NO_DATA_TAG_DIMENSION
from alarm_backends.core.cache import key
from alarm_backends.core.control.mixins.nodata import CheckMixin
from alarm_backends.service.detect import DataPoint
from bkmonitor.utils.common_utils import count_md5

RECORDS = [
    {
        "record_id": "06c3c0cf76fddfa01db5f300ddc5ddac.1583896800",
        "values": {"idle": 0.8, "time": 1583896800},
        "dimensions": {"bk_target_cloud_id": "0", "bk_target_ip": "127.0.0.1"},
        "value": 0.8,
        "time": 1583896800,
    },
    {
        "record_id": "06c3c0cf76fddfa01db5f300ddc5ddac.1583896800",
        "values": {"idle": 0.8, "time": 1583896800},
        "dimensions": {"bk_target_ip": "127.0.0.2", "bk_target_cloud_id": "0"},
        "value": 0.8,
        "time": 1583896800,
    },
]
TARGET_INSTANCE_DIMENSIONS = [
    {
        "bk_target_ip": "127.0.0.1",
        "bk_target_cloud_id": "0",
        "__NO_DATA_DIMENSION__": True,
    },
    {
        "bk_target_ip": "127.0.0.2",
        "bk_target_cloud_id": "0",
        "__NO_DATA_DIMENSION__": True,
    },
    {
        "bk_target_ip": "127.0.0.3",
        "bk_target_cloud_id": "0",
        "__NO_DATA_DIMENSION__": True,
    },
]
ANOMALY_INFO = [
    {
        "data": {
            "dimensions": {"__NO_DATA_DIMENSION__": True, "bk_target_cloud_id": "0", "bk_target_ip": "127.0.0.3"},
            "record_id": "30911fd7286a738d51d8ba5840bfd201.10000",
            "time": 10000,
            "value": None,
            "values": {"loads": None, "timestamp": 10000},
        },
        "strategy_snapshot_key": "snapshot_key",
    },
    {
        "data": {
            "dimensions": {"__NO_DATA_DIMENSION__": True, "bk_target_cloud_id": "0", "bk_target_ip": "127.0.0.7"},
            "record_id": "ff9447af90e21c21a571fed86eed61c7.10000",
            "time": 10000,
            "value": None,
            "values": {"loads": None, "timestamp": 10000},
        },
        "strategy_snapshot_key": "snapshot_key",
    },
    {
        "data": {
            "dimensions": {"__NO_DATA_DIMENSION__": True},
            "record_id": "3e06a0b6d0560271cafee9f08a6da2d7.10000",
            "time": 10000,
            "value": None,
            "values": {"loads": None, "timestamp": 10000},
        },
        "strategy_snapshot_key": "snapshot_key",
    },
]


def mock_anomaly_info(self, check_timestamp, target_dimension, target_dms_md5):
    return {
        "data": {
            "record_id": "{dimensions_md5}.{timestamp}".format(
                dimensions_md5=target_dms_md5, timestamp=check_timestamp
            ),
            "value": None,
            "values": {"timestamp": check_timestamp, "loads": None},
            "dimensions": target_dimension,
            "time": check_timestamp,
        },
        "strategy_snapshot_key": "snapshot_key",
    }


def mock_last_check_key(self, check_timestamp, dms_md5_list=None):
    if dms_md5_list is None:
        dms_md5_list = ["e5a9d7c74835f2637cff046a47737f81", "4b2af89bdb5f9c09e55743b07c306a77"]
    for dms_md5 in dms_md5_list:
        key.LAST_CHECKPOINTS_CACHE_KEY.client.hset(
            key.LAST_CHECKPOINTS_CACHE_KEY.get_key(strategy_id=self.item.strategy.id, item_id=self.item.id),
            key.LAST_CHECKPOINTS_CACHE_KEY.get_field(
                dimensions_md5=dms_md5,
                level=NO_DATA_LEVEL,
            ),
            check_timestamp,
        )


class TestChecker(TestCase):
    databases = {"monitor_api", "default"}

    def setUp(self):
        class Strategy(object):
            id = 100
            scenario = "host_process"

        class Item(CheckMixin):
            id = 1000
            name = "check_test"
            strategy = Strategy()
            query_configs = [
                {
                    "agg_condition": [],
                    "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
                    "agg_interval": 60,
                    "agg_method": "AVG",
                    "id": 200,
                    "metric_field": "disk_usage",
                    "result_table_id": "related_id.base",
                    "unit": "%",
                    "metric_id": "bk_monitor.base.disk_usage",
                    "data_source_label": "",
                    "data_type_label": "",
                }
            ]
            no_data_config = {
                "is_enabled": False,
                "continuous": 5,
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id"],
            }

        self.item_cls = Item
        self.item = self.item_cls()

        key.LAST_CHECKPOINTS_CACHE_KEY.client.flushall()

    def tearDown(self):
        key.LAST_CHECKPOINTS_CACHE_KEY.client.flushall()

    def test_process_dimensions__invalid_data(self):
        records = [
            {
                "record_id": "06c3c0cf76fddfa01db5f300ddc5ddac.1583896800",
                "values": {"idle": 0.8, "time": 1583896800},
                "dimensions": {
                    "bk_target_cloud_id": "0",
                    "bk_target_ip": "127.0.0.1",
                    "bk_topo_node": ["set|3", "module|21"],
                },
                "value": 0.8,
                "time": 1583896800,
            },
            {
                "record_id": "06c3c0cf76fddfa01db5f300ddc5ddac.1583896800",
                "values": {"idle": 0.8, "time": 1583896800},
                "dimensions": {
                    "bk_target_ip": "127.0.0.2",
                },
                "value": 0.8,
                "time": 1583896800,
            },
        ]
        no_data_dimensions = ["bk_target_ip", "bk_target_cloud_id"]
        data_points = [DataPoint(record, self.item) for record in records]
        data_dimensions = self.item._process_dimensions(no_data_dimensions, data_points)["data_dimensions"]
        assert_dimensions = {"bk_target_cloud_id": "0", "bk_target_ip": "127.0.0.1", NO_DATA_TAG_DIMENSION: True}
        self.assertEqual(data_dimensions, [assert_dimensions])

    def test_process_dimensions__dimensions_md5_timestamp(self):
        records = [
            {
                "record_id": "06c3c0cf76fddfa01db5f300ddc5ddac.1583896740",
                "values": {"idle": 0.8, "time": 1583896740},
                "dimensions": {
                    "bk_target_cloud_id": "0",
                    "bk_target_ip": "127.0.0.1",
                    "bk_topo_node": ["set|3", "module|21"],
                },
                "value": 0.8,
                "time": 1583896740,
            },
            {
                "record_id": "06c3c0cf76fddfa01db5f300ddc5ddac.1583896800",
                "values": {"idle": 0.8, "time": 1583896800},
                "dimensions": {
                    "bk_target_cloud_id": "0",
                    "bk_target_ip": "127.0.0.1",
                    "bk_topo_node": ["set|3", "module|21"],
                },
                "value": 0.8,
                "time": 1583896800,
            },
            {
                "record_id": "06c3c0cf76fddfa01db5f300ddc5ddac.1583896800",
                "values": {"idle": 0.8, "time": 1583896800},
                "dimensions": {
                    "bk_target_cloud_id": "0",
                    "bk_target_ip": "127.0.0.2",
                    "bk_topo_node": ["set|3", "module|21"],
                },
                "value": 0.8,
                "time": 1583896800,
            },
            {
                "record_id": "06c3c0cf76fddfa01db5f300ddc5ddac.1583896860",
                "values": {"idle": 0.8, "time": 1583896860},
                "dimensions": {
                    "bk_target_cloud_id": "0",
                    "bk_target_ip": "127.0.0.2",
                    "bk_topo_node": ["set|3", "module|21"],
                },
                "value": 0.8,
                "time": 1583896860,
            },
        ]
        no_data_dimensions = ["bk_target_ip", "bk_target_cloud_id"]
        data_points = [DataPoint(record, self.item) for record in records]
        result = self.item._process_dimensions(no_data_dimensions, data_points)
        data_dimensions = result["data_dimensions"]
        dimensions_md5_timestamp = result["dimensions_md5_timestamp"]
        data_dimensions_mds = result["data_dimensions_mds"]
        assert_dimensions1 = {"bk_target_cloud_id": "0", "bk_target_ip": "127.0.0.1", NO_DATA_TAG_DIMENSION: True}
        dimension1_md5 = count_md5(assert_dimensions1)
        assert_dimensions2 = {"bk_target_cloud_id": "0", "bk_target_ip": "127.0.0.2", NO_DATA_TAG_DIMENSION: True}
        dimension2_md5 = count_md5(assert_dimensions2)
        self.assertEqual([assert_dimensions1, assert_dimensions2], data_dimensions)
        self.assertEqual(dimensions_md5_timestamp, {dimension1_md5: 1583896800, dimension2_md5: 1583896860})
        self.assertEqual([dimension1_md5, dimension2_md5], data_dimensions_mds)

    def test_produce_anomaly_id(self):
        self.assertEqual(
            self.item._produce_anomaly_id(check_timestamp=10000, dimensions_md5="dimensions_md5"),
            "dimensions_md5.10000.100.1000.2",
        )

    def test_count_anomaly_period(self):
        check_timestamp = 10000
        dimensions_md5 = "test_dimensions_md5"
        self.item.query_configs = [{"agg_interval": 100}]
        # 测试取不到无数据异常监测点的情况
        self.assertEqual(self.item._count_anomaly_period(check_timestamp, dimensions_md5), 1)

        check_timestamp = 20000
        # 测试上一次取不到无数据异常监测点时成功设置了检测时间点，这次能取到无数据异常监测点
        self.assertEqual(self.item._count_anomaly_period(check_timestamp, dimensions_md5), 101)

    def test_count_no_data_period(self):
        check_timestamp = 10000
        dimensions_md5 = "test_dimensions_md5"
        self.item.query_configs = [{"agg_interval": 100}]
        self.assertEqual(self.item._count_no_data_period(check_timestamp, dimensions_md5), 0)

        mock_last_check_key(self, 9000, [dimensions_md5])
        self.assertEqual(self.item._count_no_data_period(check_timestamp, dimensions_md5), 10)

    @patch(
        "alarm_backends.service.nodata.scenarios.base.BaseScenario.get_target_instances_dimensions",
        MagicMock(return_value=(TARGET_INSTANCE_DIMENSIONS, [])),
    )
    @patch("alarm_backends.core.control.mixins.nodata.CheckMixin._produce_anomaly_info", mock_anomaly_info)
    @patch("alarm_backends.core.control.mixins.nodata.CheckMixin._is_host_dimension_in_business", lambda x, y: True)
    def test_check__no_his_dms(self):
        check_timestamp = 10000
        mock_last_check_key(self, 9940)
        data_points = [DataPoint(record, self.item) for record in RECORDS]
        self.assertEqual(self.item.check(data_points, check_timestamp), [ANOMALY_INFO[0]])

    @patch(
        "alarm_backends.service.nodata.scenarios.base.BaseScenario.get_target_instances_dimensions",
        MagicMock(return_value=([], [])),
    )
    @patch("alarm_backends.core.control.mixins.nodata.CheckMixin._produce_anomaly_info", mock_anomaly_info)
    def test_check__total_no_data_dms(self):
        check_timestamp = 10000
        data_points = []
        self.assertEqual(self.item.check(data_points, check_timestamp), [ANOMALY_INFO[2]])

    @patch(
        "alarm_backends.service.nodata.scenarios.base.BaseScenario.get_target_instances_dimensions",
        MagicMock(return_value=(TARGET_INSTANCE_DIMENSIONS, [])),
    )
    @patch("alarm_backends.core.control.mixins.nodata.CheckMixin._produce_anomaly_info", mock_anomaly_info)
    def test_check__total_no_data_recover(self):
        check_timestamp = 10000
        mock_last_check_key(self, 9940)
        data_points = [DataPoint(record, self.item) for record in RECORDS]
        key.NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.client.hset(
            key.NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.get_key(),
            key.NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.get_field(
                strategy_id=self.item.strategy.id,
                item_id=self.item.id,
                dimensions_md5="3e06a0b6d0560271cafee9f08a6da2d7",
            ),
            9000,
        )
        self.item.check(data_points, check_timestamp)
        last_anomaly_point = key.NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.client.hget(
            key.NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.get_key(),
            key.NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY.get_field(
                strategy_id=self.item.strategy.id,
                item_id=self.item.id,
                dimensions_md5="3e06a0b6d0560271cafee9f08a6da2d7",
            ),
        )
        self.assertEqual(last_anomaly_point, None)

    @patch(
        "alarm_backends.service.nodata.scenarios.base.BaseScenario.get_target_instances_dimensions",
        MagicMock(
            return_value=(
                [],
                [{"bk_target_ip": "127.0.0.7", "bk_target_cloud_id": "0", "__NO_DATA_DIMENSION__": True}],
            )
        ),
    )
    @patch("alarm_backends.core.control.mixins.nodata.CheckMixin._produce_anomaly_info", mock_anomaly_info)
    def test_check__missing_target_dms_only(self):
        check_timestamp = 10000
        mock_last_check_key(self, 9940)
        data_points = [DataPoint(record, self.item) for record in RECORDS]
        self.assertEqual(self.item.check(data_points, check_timestamp), [ANOMALY_INFO[1]])

    @patch(
        "alarm_backends.service.nodata.scenarios.base.BaseScenario.get_target_instances_dimensions",
        MagicMock(
            return_value=(
                TARGET_INSTANCE_DIMENSIONS,
                [{"bk_target_ip": "127.0.0.7", "bk_target_cloud_id": "0", "__NO_DATA_DIMENSION__": True}],
            )
        ),
    )
    @patch("alarm_backends.core.control.mixins.nodata.CheckMixin._produce_anomaly_info", mock_anomaly_info)
    @patch("alarm_backends.service.alert.manager.checker.close.HostManager", None)
    def test_check__no_his_and_missing_target(self):
        check_timestamp = 10000
        mock_last_check_key(self, 9940)
        data_points = [DataPoint(record, self.item) for record in RECORDS]
        # 127.0.0.3 不在HostManager缓存中
        self.assertEqual(self.item.check(data_points, check_timestamp), ANOMALY_INFO[1:2])
