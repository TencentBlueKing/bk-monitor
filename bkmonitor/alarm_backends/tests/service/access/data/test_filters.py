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
import datetime
from collections import defaultdict

import arrow
from django.conf import settings

from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.core.cache.cmdb.dynamic_group import DynamicGroupManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.access.data.filters import (
    ExpireFilter,
    HostStatusFilter,
    RangeFilter,
)
from alarm_backends.service.access.data.records import DataRecord
from api.cmdb.define import Host

from .config import RAW_DATA, STRATEGY_CONFIG


class TestExpireFilter(object):
    def test_filter(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = STRATEGY_CONFIG

        strategy_id = 1
        strategy = Strategy(strategy_id)
        _ = strategy.config
        get_strategy_by_id.assert_called_once_with(strategy_id)

        f = ExpireFilter()

        arrow_now = arrow.utcnow()
        raw_data_1 = copy.deepcopy(RAW_DATA)
        raw_data_1["_time_"] = arrow.get(arrow_now.datetime + datetime.timedelta(minutes=-28)).timestamp
        raw_data_2 = copy.deepcopy(RAW_DATA)
        raw_data_2["_time_"] = arrow.get(arrow_now.datetime + datetime.timedelta(minutes=-29)).timestamp
        raw_data_3 = copy.deepcopy(RAW_DATA)
        raw_data_3["_time_"] = arrow.get(arrow_now.datetime + datetime.timedelta(minutes=-30)).timestamp
        raw_data_4 = copy.deepcopy(RAW_DATA)
        raw_data_4["_time_"] = arrow.get(arrow_now.datetime + datetime.timedelta(minutes=-31)).timestamp

        record = DataRecord(strategy.items[0], raw_data_1)
        assert f.filter(record) is False

        record = DataRecord(strategy.items[0], raw_data_2)
        assert f.filter(record) is False

        record = DataRecord(strategy.items[0], raw_data_3)
        assert f.filter(record) is False

        record = DataRecord(strategy.items[0], raw_data_4)
        assert f.filter(record) is True


class TestRangeFilter(object):
    def test_ip_filter(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(STRATEGY_CONFIG)

        strategy_id = 1
        strategy = Strategy(strategy_id)
        strategy.items[0].target = [
            [
                {
                    "field": "bk_target_ip",
                    "method": "eq",
                    "value": [
                        {"bk_target_ip": "127.0.0.1", "bk_supplier_id": 0, "bk_target_cloud_id": 0},
                        {"bk_target_ip": "127.0.0.2", "bk_supplier_id": 0, "bk_target_cloud_id": 0},
                    ],
                }
            ]
        ]

        f = RangeFilter()
        raw_data_1 = copy.deepcopy(RAW_DATA)
        raw_data_1["bk_target_ip"] = "127.0.0.1"
        record = DataRecord(strategy.items[0], raw_data_1)
        assert f.filter(record) is False
        assert record.is_retains[STRATEGY_CONFIG["items"][0]["id"]] is True

        raw_data_1["bk_target_ip"] = "127.0.0.2"
        record = DataRecord(strategy.items[0], raw_data_1)
        assert f.filter(record) is False
        assert record.is_retains[STRATEGY_CONFIG["items"][0]["id"]] is True

        raw_data_1["bk_target_ip"] = "127.0.0.3"
        record = DataRecord(strategy.items[0], raw_data_1)
        assert f.filter(record) is False
        # 数据需要被保留，但对于 item 来说实际上这个数据点已经被过滤了
        assert record.is_retains[STRATEGY_CONFIG["items"][0]["id"]] is False

        raw_data_1["bk_target_cloud_id"] = "2"
        record = DataRecord(strategy.items[0], raw_data_1)
        assert f.filter(record) is False
        assert record.is_retains[STRATEGY_CONFIG["items"][0]["id"]] is False

    def test_dynamic_group_filter(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(STRATEGY_CONFIG)

        get_dynamic_group = mocker.patch.object(DynamicGroupManager, "multi_get")
        get_dynamic_group.return_value = [{"bk_obj_id": "host", "bk_inst_ids": [1, 2, 3], "id": "xxx"}]

        strategy_id = 1
        strategy = Strategy(strategy_id)
        strategy.items[0].target = [
            [
                {
                    "field": "dynamic_group",
                    "method": "eq",
                    "value": [{"dynamic_group_id": "xxx"}],
                }
            ]
        ]

        f = RangeFilter()
        record = DataRecord(strategy.items[0], copy.deepcopy(RAW_DATA))
        record.dimensions["bk_host_id"] = "1"
        assert f.filter(record) is False
        assert record.is_retains[STRATEGY_CONFIG["items"][0]["id"]] is True

    def test_topo_node_filter(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(STRATEGY_CONFIG)

        strategy_id = 1
        strategy = Strategy(strategy_id)
        _ = strategy.config
        strategy.items[0].target = [
            [
                {
                    "field": "host_topo_node",
                    "method": "eq",
                    "value": [
                        {"bk_obj_id": "biz", "bk_inst_id": 2},
                        {"bk_obj_id": "set", "bk_inst_id": 2},
                        {"bk_obj_id": "module", "bk_inst_id": 5},
                    ],
                }
            ]
        ]

        f = RangeFilter()
        raw_data_1 = copy.deepcopy(RAW_DATA)
        record = DataRecord(strategy.items[0], raw_data_1)
        record.dimensions["bk_topo_node"] = ["biz|2", "set|1", "module|1"]
        assert f.filter(record) is False
        assert record.is_retains[STRATEGY_CONFIG["items"][0]["id"]] is True

        record = DataRecord(strategy.items[0], raw_data_1)
        record.dimensions["bk_topo_node"] = [
            "biz|3",
            "set|1",
            "module|1",
        ]
        assert f.filter(record) is False
        assert record.is_retains[STRATEGY_CONFIG["items"][0]["id"]] is False

        record = DataRecord(strategy.items[0], raw_data_1)
        record.dimensions = {"bk_obj_id": "biz", "bk_inst_id": 2}
        assert f.filter(record) is False
        assert record.is_retains[STRATEGY_CONFIG["items"][0]["id"]] is True


class TestHostStatusFilter(object):
    def test_filter(self, mocker):
        get_host = mocker.patch.object(HostManager, "get")
        get_host.return_value = Host(
            bk_host_innerip="127.0.0.1",
            bk_cloud_id=0,
            bk_host_id=1,
            bk_biz_id=2,
            bk_state=settings.HOST_DISABLE_MONITOR_STATES[0],
            bk_set_ids="",
            bk_module_ids=[1],
            bk_bak_operator="test",
            operator="test",
        )

        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(STRATEGY_CONFIG)
        strategy = Strategy(1)

        f = HostStatusFilter()
        record = DataRecord(strategy.items[0], copy.deepcopy(RAW_DATA))
        assert not f.filter(record)
        assert not record.is_retains[strategy.items[0].id]

        record.is_retains = defaultdict(lambda: True)
        get_host.return_value = Host(
            bk_host_innerip="127.0.0.1",
            bk_cloud_id=0,
            bk_host_id=1,
            bk_biz_id=2,
            bk_state="",
            bk_set_ids="",
            bk_module_ids=[1],
            bk_bak_operator="test",
            operator="test",
        )
        assert not f.filter(record)
        assert record.is_retains[1]
