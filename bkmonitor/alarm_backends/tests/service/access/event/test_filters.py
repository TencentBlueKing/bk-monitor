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

from alarm_backends.core.cache.cmdb import HostManager
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.core.control.strategy import Strategy
from alarm_backends.service.access.data.filters import RangeFilter
from alarm_backends.service.access.event.filters import ConditionFilter
from alarm_backends.service.access.event.records import (
    CorefileEvent,
    DiskFullEvent,
    DiskReadonlyEvent,
    OOMEvent,
    PingEvent,
)
from alarm_backends.tests.service.access.data.config import (
    CORE_FILE_RAW_DATA,
    EVENT_RAW_DATA,
    EVENT_STRATEGY_CONFIG,
)
from api.cmdb.define import Host


class TestRangeFilter(object):
    def test_ip_filter(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(EVENT_STRATEGY_CONFIG)

        get_host = mocker.patch.object(HostManager, "get")
        get_host.return_value = HostManager.get.return_value = Host(
            bk_host_innerip="10.0.0.1",
            bk_cloud_id=0,
            bk_cloud_name="default area",
            bk_host_id=1,
            bk_biz_id=2,
            operator=["admin"],
            bk_bak_operator=["admin1"],
            bk_module_ids=[1],
            bk_set_ids=[1],
            topo_link={},
        )

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
        strategies = {2: {1: strategy}}

        f = RangeFilter()
        raw_data_1 = copy.deepcopy(EVENT_RAW_DATA)
        record = PingEvent(raw_data_1, strategies).full()[0]
        assert f.filter(record) is False

        record = PingEvent(raw_data_1, strategies).full()[0]
        record.raw_data["dimensions"]["bk_target_ip"] = "127.0.0.2"
        assert f.filter(record) is False

        record = PingEvent(raw_data_1, strategies).full()[0]
        record.raw_data["dimensions"]["bk_target_ip"] = "127.0.0.3"
        assert f.filter(record) is False

        raw_data_1["dimensions"]["bk_target_cloud_id"] = "2"
        record = PingEvent(raw_data_1, strategies).full()[0]
        record.raw_data["dimensions"]["bk_target_cloud_id"] = "2"
        assert f.filter(record) is False

    def test_topo_node_filter(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(EVENT_STRATEGY_CONFIG)

        get_host = mocker.patch.object(HostManager, "get")
        get_host.return_value = HostManager.get.return_value = Host(
            bk_host_innerip="10.0.0.1",
            bk_cloud_id=0,
            bk_cloud_name="default area",
            bk_host_id=1,
            bk_biz_id=2,
            operator=["admin"],
            bk_bak_operator=["admin1"],
            bk_module_ids=[1],
            bk_set_ids=[1],
            topo_link={},
        )

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

        strategies = {2: {1: strategy}}

        f = RangeFilter()
        raw_data_1 = copy.deepcopy(EVENT_RAW_DATA)
        record = PingEvent(raw_data_1, strategies).full()[0]
        record.dimensions["bk_topo_node"] = ["biz|2", "set|1", "module|1"]
        assert f.filter(record) is False

        record = PingEvent(raw_data_1, strategies).full()[0]
        record.dimensions["bk_topo_node"] = [
            "biz|3",
            "set|1",
            "module|1",
        ]
        assert f.filter(record) is False

        record = PingEvent(raw_data_1, strategies).full()[0]
        record.dimensions = {"bk_obj_id": "biz", "bk_inst_id": 2}
        assert f.filter(record) is False


class TestConditionFilter(object):
    def test_filter(self, mocker):
        get_strategy_by_id = mocker.patch.object(StrategyCacheManager, "get_strategy_by_id")
        get_strategy_by_id.return_value = copy.deepcopy(EVENT_STRATEGY_CONFIG)

        get_host = mocker.patch.object(HostManager, "get")
        get_host.return_value = HostManager.get.return_value = Host(
            bk_host_innerip="10.0.0.1",
            bk_cloud_id=0,
            bk_cloud_name="default area",
            bk_host_id=1,
            bk_biz_id=2,
            operator=["admin"],
            bk_bak_operator=["admin1"],
            bk_module_ids=[1],
            bk_set_ids=[1],
            topo_link={},
        )

        strategy_id = 1
        strategy = Strategy(strategy_id)
        strategy.items[0].query_configs[0]["agg_condition"] = [
            {"key": "corefile", "method": "include", "value": ["/data/bkee"]}
        ]
        strategy.config["items"][0]["query_configs"][0]["metric_id"] = "bk_monitor.corefile-gse"
        strategy.items[0].metric_ids = ["bk_monitor.corefile-gse"]
        strategies = {2: {1: strategy}}

        f = ConditionFilter()
        raw_data_1 = copy.deepcopy(CORE_FILE_RAW_DATA)
        record = CorefileEvent(raw_data_1, strategies).full()[0]
        assert f.filter(record) is True

        raw_data_1["_extra_"]["corefile"] = "/data/bkee/core_101041_2018-03-10"
        record = CorefileEvent(raw_data_1, strategies).full()[0]
        assert f.filter(record) is False

    def test_filter_dimension(self, mocker):
        assert (
            set(
                CorefileEvent(
                    {
                        "_extra_": {
                            "bizid": 0,
                            "cloudid": 0,
                            "corefile": "/data/corefile/core_101041_2018-03-10",
                            "filesize": "0",
                            "host": "127.0.0.1",
                            "type": 7,
                        }
                    },
                    [],
                ).filter_dimensions.keys()
            )
            == {"executable_path", "corefile", "signal", "executable"}
        )
        assert (
            set(
                OOMEvent(
                    {
                        "_extra_": {
                            "bizid": 0,
                            "cloudid": 0,
                            "host": "127.0.0.1",
                            "type": 9,
                            "total": 3,
                            "process": "oom/java/consul",
                            "message": "total-vm:44687536kB, anon-rss:32520504kB, file-rss:0kB, shmem-rss:0kB",
                        }
                    },
                    [],
                ).filter_dimensions.keys()
            )
            == {"process", "message"}
        )
        assert (
            set(
                OOMEvent(
                    {
                        "_extra_": {
                            "bizid": 0,
                            "cloudid": 0,
                            "host": "127.0.0.1",
                            "type": 9,
                            "total": 3,
                            "process": "oom/java/consul",
                            "message": "total-vm:44687536kB, anon-rss:32520504kB, file-rss:0kB, shmem-rss:0kB",
                            "oom_memcg": "oom_cgroup_path",
                            "task_memcg": "oom_cgroup_task",
                            "task": "process_name",
                            "constraint": "CONSTRAINT_MEMCG",
                        }
                    },
                    [],
                ).filter_dimensions.keys()
            )
            == {"process", "message", "oom_memcg", "task_memcg", "task", "constraint"}
        )
        assert (
            set(
                DiskFullEvent(
                    {
                        "_extra_": {
                            "used_percent": 93,
                            "used": 45330684,
                            "cloudid": 0,
                            "free": 7,
                            "fstype": "ext4",
                            "host": "127.0.0.1",
                            "disk": "/",
                            "file_system": "/dev/vda1",
                            "size": 51473888,
                            "bizid": 0,
                            "avail": 3505456,
                            "type": 6,
                        }
                    },
                    [],
                ).filter_dimensions.keys()
            )
            == {"disk", "file_system", "fstype"}
        )
        assert (
            set(
                DiskReadonlyEvent(
                    {
                        "_extra_": {
                            "cloudid": 0,
                            "host": "127.0.0.1",
                            "ro": [
                                {"position": r"\/sys\/fs\/cgroup", "fs": "tmpfs", "type": "tmpfs"},
                                {"position": r"\/readonly_disk", "fs": r"dev\/vdb", "type": "ext4"},
                            ],
                            "type": 3,
                            "bizid": 0,
                        }
                    },
                    [],
                ).filter_dimensions.keys()
            )
            == {"position", "type", "fs"}
        )
