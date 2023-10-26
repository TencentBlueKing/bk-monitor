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

from alarm_backends.core.cache.cmdb import HostManager, ServiceInstanceManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.access.data.fullers import TopoNodeFuller
from alarm_backends.service.access.data.records import DataRecord

from .config import RAW_DATA, STRATEGY_CONFIG


class MockTopoNode(object):
    def __init__(self, id_value):
        self.id = id_value


class MockHost(object):
    def __init__(self, topo_link_value=None):
        self.topo_link = topo_link_value
        self.bk_host_id = 0


class MockServiceInstance(object):
    def __init__(self, topo_link_value=None):
        self.ip = "127.0.0.1"
        self.bk_cloud_id = 0
        self.topo_link = topo_link_value


class TestTopoNodeFuller(object):
    def test_full(self, mocker):
        mocker.patch.object(StrategyCacheManager, "get_strategy_by_id", return_value=copy.deepcopy(STRATEGY_CONFIG))
        mocker.patch.object(
            HostManager,
            "get",
            return_value=MockHost(
                {"module|1": [MockTopoNode("biz|2"), MockTopoNode("module|1"), MockTopoNode("set|1")]}
            ),
        )
        mocker.patch.object(
            ServiceInstanceManager,
            "get",
            return_value=MockServiceInstance(
                {"module|1": [MockTopoNode("biz|2"), MockTopoNode("module|1"), MockTopoNode("set|1")]}
            ),
        )

        strategy_id = 1
        strategy = Strategy(strategy_id)
        strategy.config["scenario"] = "os"

        # 1. Host
        f = TopoNodeFuller()
        raw_data_1 = copy.deepcopy(RAW_DATA)
        record = DataRecord(strategy.items[0], raw_data_1)
        f.full(record)
        assert "bk_topo_node" in record.dimensions
        host_topo_node = record.dimensions["bk_topo_node"]
        host_topo_node.sort()
        assert host_topo_node == ["biz|2", "module|1", "set|1"]

        # 2. Service
        strategy = Strategy(strategy_id)
        strategy.config["scenario"] = "service_module"
        f = TopoNodeFuller()
        raw_data_1 = copy.deepcopy(RAW_DATA)
        raw_data_1["bk_target_service_instance_id"] = 1
        strategy.items[0].query_configs[0]["agg_dimension"].append("bk_target_service_instance_id")
        record = DataRecord(strategy.items[0], raw_data_1)
        f.full(record)
        assert "bk_topo_node" in record.dimensions
        service_topo_node = record.dimensions["bk_topo_node"]
        service_topo_node.sort()
        assert service_topo_node == ["biz|2", "module|1", "set|1"]

        assert record.dimensions["bk_host_id"] == 0
