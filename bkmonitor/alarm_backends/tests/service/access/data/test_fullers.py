"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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


class MockTopoNode:
    def __init__(self, id_value):
        self.id = id_value


class MockHost:
    def __init__(self, topo_link_value=None, bk_host_id=0, ip="127.0.0.1", bk_cloud_id=0, bk_agent_id=""):
        self.topo_link = topo_link_value
        self.bk_host_id = bk_host_id
        self.ip = ip
        self.bk_cloud_id = bk_cloud_id
        self.bk_agent_id = bk_agent_id


class MockServiceInstance:
    def __init__(self, topo_link_value=None):
        self.ip = "127.0.0.1"
        self.bk_cloud_id = 0
        self.topo_link = topo_link_value


class TestTopoNodeFuller:
    def test_full(self, mocker):
        get_strategy = mocker.patch.object(
            StrategyCacheManager, "get_strategy_by_id", return_value=copy.deepcopy(STRATEGY_CONFIG)
        )
        get_host = mocker.patch.object(
            HostManager,
            "get",
            return_value=MockHost(
                {"module|1": [MockTopoNode("biz|2"), MockTopoNode("module|1"), MockTopoNode("set|1")]}
            ),
        )
        get_host_by_id = mocker.patch.object(HostManager, "get_by_id")
        get_host_by_agent_id = mocker.patch.object(HostManager, "get_by_agent_id")
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

        # 3. Host ID 优先，命中后不再按 Agent ID 补全
        strategy_config = copy.deepcopy(STRATEGY_CONFIG)
        strategy_config["items"][0]["query_configs"][0]["agg_dimension"] = ["bk_host_id", "bk_agent_id"]
        get_strategy.return_value = strategy_config
        strategy = Strategy(strategy_id)
        strategy.config["scenario"] = "os"
        get_host_by_id.return_value = MockHost(
            {"module|3": [MockTopoNode("biz|2"), MockTopoNode("module|3"), MockTopoNode("set|1")]},
            bk_host_id=2,
            ip="127.0.0.3",
            bk_cloud_id=0,
        )
        get_host_by_agent_id.reset_mock()

        f = TopoNodeFuller()
        raw_data_1 = copy.deepcopy(RAW_DATA)
        raw_data_1["bk_host_id"] = 2
        raw_data_1["bk_agent_id"] = "01000000000000000000000000000002"
        record = DataRecord(strategy.items[0], raw_data_1)
        f.full(record)

        assert get_host_by_id.call_args[1]["bk_host_id"] == 2
        assert not get_host_by_agent_id.called
        assert record.dimensions["bk_target_ip"] == "127.0.0.3"
        assert record.dimensions["bk_target_cloud_id"] == "0"
        assert record.dimensions["bk_host_id"] == 2
        host_id_topo_node = record.dimensions["bk_topo_node"]
        host_id_topo_node.sort()
        assert host_id_topo_node == ["biz|2", "module|3", "set|1"]

        # 4. Agent ID
        strategy_config = copy.deepcopy(STRATEGY_CONFIG)
        strategy_config["items"][0]["query_configs"][0]["agg_dimension"] = ["bk_agent_id"]
        get_strategy.return_value = strategy_config
        strategy = Strategy(strategy_id)
        strategy.config["scenario"] = "os"
        agent_id = "01000000000000000000000000000000"
        get_host_by_agent_id.return_value = MockHost(
            {"module|2": [MockTopoNode("biz|2"), MockTopoNode("module|2"), MockTopoNode("set|1")]},
            bk_host_id=1,
            ip="127.0.0.2",
            bk_cloud_id=0,
            bk_agent_id=agent_id,
        )
        get_host.return_value = None

        f = TopoNodeFuller()
        raw_data_1 = copy.deepcopy(RAW_DATA)
        raw_data_1.pop("bk_target_ip")
        raw_data_1.pop("bk_target_cloud_id")
        raw_data_1["bk_agent_id"] = agent_id
        record = DataRecord(strategy.items[0], raw_data_1)
        f.full(record)

        assert get_host_by_agent_id.call_args[1]["bk_agent_id"] == agent_id
        assert record.dimensions["bk_target_ip"] == "127.0.0.2"
        assert record.dimensions["bk_target_cloud_id"] == "0"
        assert record.dimensions["bk_host_id"] == "1"
        agent_topo_node = record.dimensions["bk_topo_node"]
        agent_topo_node.sort()
        assert agent_topo_node == ["biz|2", "module|2", "set|1"]

    def test_full_with_collector_cloud_dimension(self, mocker):
        mocker.patch.object(StrategyCacheManager, "get_strategy_by_id", return_value=copy.deepcopy(STRATEGY_CONFIG))
        get_host = mocker.patch.object(
            HostManager,
            "get",
            return_value=MockHost(
                {"module|1": [MockTopoNode("biz|2"), MockTopoNode("module|1"), MockTopoNode("set|1")]},
                bk_cloud_id=2,
            ),
        )
        mocker.patch.object(HostManager, "get_by_id")
        mocker.patch.object(HostManager, "get_by_agent_id")
        mocker.patch.object(ServiceInstanceManager, "get")

        strategy = Strategy(1)
        strategy.config["scenario"] = "os"
        strategy.items[0].query_configs[0]["agg_dimension"] = ["bk_target_ip", "bk_cloud_id"]

        raw_data = copy.deepcopy(RAW_DATA)
        raw_data.pop("bk_target_cloud_id")
        raw_data["bk_cloud_id"] = "2"
        record = DataRecord(strategy.items[0], raw_data)

        TopoNodeFuller().full(record)

        assert get_host.call_args[1]["bk_cloud_id"] == "2"
        assert record.dimensions["bk_target_cloud_id"] == "2"
        assert "bk_topo_node" in record.dimensions
