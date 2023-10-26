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


from django.test import TestCase

from alarm_backends.constants import NO_DATA_TAG_DIMENSION
from alarm_backends.service.nodata.scenarios.base import (
    SCENARIO_CLS,
    HostScenario,
    ServiceScenario,
    UptimeCheckScenario,
)
from alarm_backends.tests.service.nodata.mock import *  # noqa
from alarm_backends.tests.service.nodata.mock_settings import *  # noqa

HOSTS_INFO = [
    {
        "bk_cloud_id": 0,
        "bk_host_innerip": "127.0.0.1",
        "topo": [
            [
                {
                    "id": "module|111",
                    "bk_obj_id": "module",
                    "bk_inst_id": 111,
                },
                {
                    "id": "set|11",
                    "bk_obj_id": "set",
                    "bk_inst_id": 11,
                },
                {
                    "id": "biz|2",
                    "bk_obj_id": "biz",
                    "bk_inst_id": 2,
                },
            ],
            [
                {
                    "id": "module|121",
                    "bk_obj_id": "module",
                    "bk_inst_id": 121,
                },
                {
                    "id": "set|12",
                    "bk_obj_id": "set",
                    "bk_inst_id": 12,
                },
                {
                    "id": "biz|2",
                    "bk_obj_id": "biz",
                    "bk_inst_id": 2,
                },
            ],
        ],
    },
    {
        "bk_cloud_id": 0,
        "bk_host_innerip": "127.0.0.2",
        "topo": [
            [
                {
                    "id": "module|111",
                    "bk_obj_id": "module",
                    "bk_inst_id": 111,
                },
                {
                    "id": "set|11",
                    "bk_obj_id": "set",
                    "bk_inst_id": 11,
                },
                {
                    "id": "biz|2",
                    "bk_obj_id": "biz",
                    "bk_inst_id": 2,
                },
            ]
        ],
    },
    {
        "bk_cloud_id": 0,
        "bk_host_innerip": "127.0.0.3",
        "topo": [
            [
                {
                    "id": "module|211",
                    "bk_obj_id": "module",
                    "bk_inst_id": 211,
                },
                {
                    "id": "set|21",
                    "bk_obj_id": "set",
                    "bk_inst_id": 21,
                },
                {
                    "id": "biz|2",
                    "bk_obj_id": "biz",
                    "bk_inst_id": 2,
                },
            ]
        ],
    },
    {
        "bk_cloud_id": 0,
        "bk_host_innerip": "127.0.0.7",
        "topo": [
            [
                {
                    "id": "module|311",
                    "bk_obj_id": "module",
                    "bk_inst_id": 311,
                },
                {
                    "id": "set|21",
                    "bk_obj_id": "set",
                    "bk_inst_id": 31,
                },
                {
                    "id": "biz|2",
                    "bk_obj_id": "biz",
                    "bk_inst_id": 3,
                },
            ]
        ],
    },
]

SERVICES_INFO = [
    {
        "service_instance_id": 1,
        "name": "127.0.0.1_service1",
        "ip": "127.0.0.1",
        "topo": [
            [
                {
                    "id": "module|111",
                    "bk_obj_id": "module",
                    "bk_inst_id": 111,
                },
                {
                    "id": "set|11",
                    "bk_obj_id": "set",
                    "bk_inst_id": 11,
                },
                {
                    "id": "biz|2",
                    "bk_obj_id": "biz",
                    "bk_inst_id": 2,
                },
            ],
            [
                {
                    "id": "module|121",
                    "bk_obj_id": "module",
                    "bk_inst_id": 121,
                },
                {
                    "id": "set|12",
                    "bk_obj_id": "set",
                    "bk_inst_id": 12,
                },
                {
                    "id": "biz|2",
                    "bk_obj_id": "biz",
                    "bk_inst_id": 2,
                },
            ],
        ],
    },
    {
        "service_instance_id": 2,
        "name": "127.0.0.2_service2",
        "ip": "127.0.0.2",
        "topo": [
            [
                {
                    "id": "module|111",
                    "bk_obj_id": "module",
                    "bk_inst_id": 111,
                },
                {
                    "id": "set|11",
                    "bk_obj_id": "set",
                    "bk_inst_id": 11,
                },
                {
                    "id": "biz|2",
                    "bk_obj_id": "biz",
                    "bk_inst_id": 2,
                },
            ]
        ],
    },
    {
        "service_instance_id": 3,
        "name": "127.0.0.3_service3",
        "ip": "127.0.0.2",
        "topo": [
            [
                {
                    "id": "module|311",
                    "bk_obj_id": "module",
                    "bk_inst_id": 311,
                },
                {
                    "id": "set|31",
                    "bk_obj_id": "set",
                    "bk_inst_id": 31,
                },
                {
                    "id": "biz|2",
                    "bk_obj_id": "biz",
                    "bk_inst_id": 2,
                },
            ]
        ],
    },
]

HISTORY_DIMENSIONS = {
    "md5_1": {
        "bk_target_ip": "127.0.0.1",
        "bk_target_cloud_id": "0",
        "mountpoint": "/data/a",
        "__NO_DATA_DIMENSION__": True,
    },
    "md5_2": {
        "bk_target_ip": "127.0.0.2",
        "bk_target_cloud_id": "0",
        "mountpoint": "/data/b",
        "__NO_DATA_DIMENSION__": True,
    },
    "md5_3": {
        "bk_target_ip": "127.0.0.3",
        "bk_target_cloud_id": "0",
        "mountpoint": "/data/a",
        "__NO_DATA_DIMENSION__": True,
    },
    "md5_4": {"bk_target_ip": "127.0.0.3", "bk_target_cloud_id": "0", "__NO_DATA_DIMENSION__": True},
    "md5_5": {
        "bk_target_ip": "127.0.0.4",
        "bk_target_cloud_id": "0",
        "mountpoint": "/data/a",
        "dimension2": "dimension2",
        "__NO_DATA_DIMENSION__": True,
    },
    "md5_6": {
        "bk_target_ip": "127.0.0.5",
        "bk_target_cloud_id": "0",
        "dimension3": "dimension3",
        "__NO_DATA_DIMENSION__": True,
    },
}


class TestHostScenario(TestCase):
    def setUp(self):
        item_config = {
            "id": 11,
            "name": "item1",
            "algorithms": [
                {
                    "config": [{"method": "gte", "threshold": 10.0}],
                    "type": "Threshold",
                    "id": 111,
                    "level": 1,
                }
            ],
            "no_data_config": {
                "continuous": 5,
                "is_enabled": False,
                "agg_dimension": ["bk_target_ip", "bk_target_cloud_id", "mountpoint"],
            },
            "query_configs": [
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
            ],
            "target": [
                [{"field": "host_topo_node", "method": "eq", "value": [{"bk_inst_id": 11, "bk_obj_id": "set"}]}]
            ],
        }
        strategy_config = {
            "id": 1,
            "name": "strategy1",
            "bk_biz_id": 2,
            "scenario": "os",
            "items": [item_config],
            "detects": [
                {
                    "level": 1,
                    "connector": "and",
                    "expression": "",
                    "recovery_config": {"check_window": 2},
                    "trigger_config": {"check_window": 1, "count": 1},
                }
            ],
        }
        strategy = MockStrategy(strategy_config)
        self.item = MockItem(item_config, strategy)
        self.host_scenario = HostScenario(self.item)

    def test_get_no_data_dimensions(self):
        self.assertEqual(
            self.host_scenario.get_no_data_dimensions(), ["bk_target_ip", "bk_target_cloud_id", "mountpoint"]
        )

    def test_add_no_data_tag(self):
        dimensions = [{"dimension1": "1", "dimension2": "2"}, {"dimension1": "3", "dimension2": "4"}]
        self.host_scenario.add_no_data_tag(dimensions)
        self.assertEqual(
            dimensions,
            [
                {"dimension1": "1", "dimension2": "2", NO_DATA_TAG_DIMENSION: True},
                {"dimension1": "3", "dimension2": "4", NO_DATA_TAG_DIMENSION: True},
            ],
        )

    @patch(
        ALARM_BACKENDS_CORE_CACHE_CMDB_HOSTMANAGER_REFRESH_BY_BIZ,
        MagicMock(return_value=generate_mock_hosts(HOSTS_INFO)),
    )
    def test_get_target_instances__dynamic_topo(self):
        self.assertEqual(
            self.host_scenario.get_target_instances(),
            [
                {"bk_target_cloud_id": "0", "bk_target_ip": "127.0.0.1"},
                {"bk_target_cloud_id": "0", "bk_target_ip": "127.0.0.2"},
            ],
        )

    @patch(
        ALARM_BACKENDS_CORE_CACHE_CMDB_HOSTMANAGER_REFRESH_BY_BIZ,
        MagicMock(return_value=generate_mock_hosts(HOSTS_INFO)),
    )
    def test_get_target_instances__static_host(self):
        temp = self.host_scenario.item.target
        self.host_scenario.item.target = [
            [
                {
                    "field": "bk_target_ip",
                    "method": "eq",
                    "value": [
                        {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": 0},
                        {"bk_target_ip": "127.0.0.2", "bk_target_cloud_id": 1},
                        {"bk_target_ip": "127.0.0.100", "bk_target_cloud_id": 0},
                    ],
                }
            ]
        ]
        self.assertEqual(
            self.host_scenario.get_target_instances(), [{"bk_target_cloud_id": "0", "bk_target_ip": "127.0.0.1"}]
        )
        self.host_scenario.item.target = temp

    @patch(ALARM_BACKENDS_CORE_DETECT_RESULT_CHECKRESULT, MockCheckResult(HISTORY_DIMENSIONS))
    def test_get_history_dimensions(self):
        self.assertEqual(
            sorted(self.host_scenario.get_history_dimensions(), key=lambda x: x["bk_target_ip"]),
            [
                HISTORY_DIMENSIONS["md5_1"],
                HISTORY_DIMENSIONS["md5_2"],
                HISTORY_DIMENSIONS["md5_3"],
            ],
        )

    @patch(ALARM_BACKENDS_CORE_DETECT_RESULT_CHECKRESULT, MockCheckResult(HISTORY_DIMENSIONS))
    @patch(ALARM_BACKENDS_CORE_DETECT_RESULT_DIMENSIONRANGEFILTER_FILTER, MagicMock(return_value=False))
    @patch(
        ALARM_BACKENDS_CORE_CACHE_CMDB_HOSTMANAGER_REFRESH_BY_BIZ,
        MagicMock(return_value=generate_mock_hosts(HOSTS_INFO)),
    )
    def test_get_target_instances_dimensions(self):
        history_dimensions, missing_target_instances = self.host_scenario.get_target_instances_dimensions()
        self.assertEqual(
            sorted(history_dimensions, key=lambda x: x["bk_target_ip"]),
            [HISTORY_DIMENSIONS["md5_1"], HISTORY_DIMENSIONS["md5_2"]],
        )
        temp = self.host_scenario.item.target
        self.host_scenario.item.target = [
            [
                {
                    "field": "bk_target_ip",
                    "method": "eq",
                    "value": [
                        {"bk_target_ip": "127.0.0.1", "bk_target_cloud_id": "0"},
                        {"bk_target_ip": "127.0.0.2", "bk_target_cloud_id": "0"},
                        {"bk_target_ip": "127.0.0.3", "bk_target_cloud_id": "0"},
                        {"bk_target_ip": "127.0.0.7", "bk_target_cloud_id": "0"},
                    ],
                }
            ]
        ]
        history_dimensions, missing_target_instances = self.host_scenario.get_target_instances_dimensions()
        self.assertEqual(
            sorted(history_dimensions, key=lambda x: x["bk_target_ip"]),
            [HISTORY_DIMENSIONS["md5_1"], HISTORY_DIMENSIONS["md5_2"], HISTORY_DIMENSIONS["md5_3"]],
        )
        self.assertEqual(
            missing_target_instances,
            [{"bk_target_ip": "127.0.0.7", "bk_target_cloud_id": "0", "__NO_DATA_DIMENSION__": True}],
        )
        self.host_scenario.item.no_data_config["agg_dimension"] = ["bk_target_ip", "bk_target_cloud_id", "mountpoint"]
        self.host_scenario.item.target = temp


class TestServiceScenario(TestCase):
    def setUp(self):
        item_config = {
            "id": 11,
            "name": "item1",
            "algorithms": [
                {
                    "config": [{"method": "gte", "threshold": 10.0}],
                    "type": "Threshold",
                    "id": 111,
                    "level": 1,
                }
            ],
            "no_data_config": {
                "continuous": 5,
                "is_enabled": False,
                "agg_dimension": ["bk_target_service_instance_id", "service_type"],
            },
            "query_configs": [
                {
                    "metric_id": "bk_monitor.base.redis_blocked_clients",
                    "data_source_label": "",
                    "data_type_label": "",
                    "agg_condition": [],
                    "agg_dimension": ["bk_target_service_instance_id"],
                    "agg_interval": 60,
                    "agg_method": "AVG",
                    "id": 200,
                    "metric_field": "disk_usage",
                    "result_table_id": "related_id.base",
                    "unit": "%",
                }
            ],
            "target": [
                [{"field": "host_topo_node", "method": "eq", "value": [{"bk_inst_id": 11, "bk_obj_id": "set"}]}]
            ],
        }
        strategy_config = {
            "id": 1,
            "name": "strategy1",
            "bk_biz_id": 2,
            "scenario": "service_module",
            "items": [item_config],
            "detects": [
                {
                    "level": 1,
                    "connector": "and",
                    "expression": "",
                    "recovery_config": {"check_window": 2},
                    "trigger_config": {"check_window": 1, "count": 1},
                }
            ],
        }
        strategy = MockStrategy(strategy_config)
        self.item = MockItem(item_config, strategy)
        self.service_scenario = ServiceScenario(self.item)

    @patch(
        ALARM_BACKENDS_CORE_CACHE_CMDB_SERVICE_INSTANCE_MANAGER_REFRESH_BY_BIZ,
        MagicMock(return_value=generate_mock_services(SERVICES_INFO)),
    )
    def test_get_target_instances__topo_set(self):
        self.assertEqual(
            self.service_scenario.get_target_instances(),
            [{"bk_target_service_instance_id": "1"}, {"bk_target_service_instance_id": "2"}],
        )

    @patch(
        ALARM_BACKENDS_CORE_CACHE_CMDB_SERVICE_INSTANCE_MANAGER_REFRESH_BY_BIZ,
        MagicMock(return_value=generate_mock_services(SERVICES_INFO)),
    )
    def test_get_target_instances__topo_module(self):
        temp = self.service_scenario.item.target
        self.service_scenario.item.target = [
            [{"field": "host_topo_node", "method": "eq", "value": [{"bk_inst_id": 311, "bk_obj_id": "module"}]}]
        ]
        self.assertEqual(self.service_scenario.get_target_instances(), [{"bk_target_service_instance_id": "3"}])
        self.service_scenario.strategy.item = temp


class TestUptimeCheckScenario(TestCase):
    def setUp(self):
        item_config = {
            "id": 1,
            "no_data_config": {"continuous": 5, "is_enabled": False, "agg_dimension": ["task_id"]},
            "query_configs": [
                {
                    "agg_condition": [],
                    "agg_dimension": ["bk_target_service_instance_id"],
                    "agg_interval": 60,
                    "agg_method": "AVG",
                    "id": 200,
                    "metric_field": "disk_usage",
                    "result_table_id": "related_id.base",
                    "unit": "%",
                }
            ],
            "target": [
                [{"field": "host_topo_node", "method": "eq", "value": [{"bk_inst_id": 11, "bk_obj_id": "set"}]}]
            ],
        }
        strategy_config = {
            "id": 1,
            "name": "strategy1",
            "bk_biz_id": 2,
            "scenario": "service_module",
            "items": [item_config],
            "detects": [
                {
                    "level": 1,
                    "connector": "and",
                    "expression": "",
                    "recovery_config": {"check_window": 2},
                    "trigger_config": {"check_window": 1, "count": 1},
                }
            ],
        }
        strategy = MockStrategy(strategy_config)
        self.item = MockItem(item_config, strategy)
        self.uptime_check_scenario = UptimeCheckScenario(self.item)

    def test_get_target_instance(self):
        self.assertIsNone(self.uptime_check_scenario.get_target_instances())


class TestScenarioCls(TestCase):
    def test_scenario(self):
        self.assertEqual(SCENARIO_CLS["host_process"], HostScenario)
        self.assertEqual(SCENARIO_CLS["os"], HostScenario)

        self.assertEqual(SCENARIO_CLS["service_module"], ServiceScenario)
        self.assertEqual(SCENARIO_CLS["component"], ServiceScenario)
        self.assertEqual(SCENARIO_CLS["service_process"], ServiceScenario)

        self.assertEqual(SCENARIO_CLS["uptimecheck"], UptimeCheckScenario)
