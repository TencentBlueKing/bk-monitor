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

import pytest
from mock import MagicMock

from bkmonitor.strategy.convert import CMDBTopoNodeAggConvert, FakeEventConvert
from bkmonitor.strategy.new_strategy import Item, Strategy
from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import SYSTEM_EVENT_RT_TABLE_ID

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="function")
def mock_metric_split_api(mocker):
    return mocker.patch(
        "bkmonitor.strategy.convert.api.metadata.create_result_table_metric_split",
        return_value={"table_id": "test.test_cmdb_level"},
    )


class TestCmdbLevelAgg:
    Config = {
        "name": "name",
        "expression": "a + b",
        "origin_sql": "test",
        "no_data_config": {},
        "target": [
            [
                {
                    "field": "host_topo_node",
                    "method": "eq",
                    "value": [
                        {"bk_obj_id": "set", "bk_inst_id": 1},
                        {"bk_obj_id": "set", "bk_inst_id": 2},
                        {"bk_obj_id": "module", "bk_inst_id": 1},
                        {"bk_obj_id": "module", "bk_inst_id": 2},
                    ],
                }
            ]
        ],
        "algorithms": [{"type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "xxx"}],
        "query_configs": [
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "alias": "a",
                "result_table_id": "system.disk",
                "metric_field": "usage",
                "unit": "percent",
                "agg_method": "avg",
                "agg_condition": [],
                "agg_dimension": [],
                "agg_interval": 60,
            }
        ],
    }

    def test_cmdb_topo_aggregation(self, mock_metric_split_api: MagicMock):
        strategy = Strategy(bk_biz_id=1, scenario="os", name="test", items=[copy.deepcopy(self.Config)])
        item = strategy.items[0]
        item.query_configs[0].result_table_id = "2_system.disk"

        CMDBTopoNodeAggConvert.convert(strategy)

        assert item.query_configs[0].result_table_id == "test.test_cmdb_level"
        assert set(item.query_configs[0].agg_dimension) == {"bk_obj_id", "bk_inst_id"}
        assert item.query_configs[0].origin_config == {
            "result_table_id": "2_system.disk",
            "agg_dimension": [],
        }
        assert mock_metric_split_api.call_count == 2

    def test_refuse_host_metric(self, mock_metric_split_api):
        strategy = Strategy(bk_biz_id=1, scenario="os", name="test", items=[copy.deepcopy(self.Config)])
        try:
            CMDBTopoNodeAggConvert.convert(strategy)
        except Exception as e:
            assert "主机性能指标按CMDB动态节点聚合暂不可用(原因：维度未使用云区域ID + IP，目标又选择了CMDB节点)" == str(e)
        else:
            assert False

    def test_no_topo_node_target(self, mock_metric_split_api):
        strategy = Strategy(bk_biz_id=1, scenario="os", name="test", items=[copy.deepcopy(self.Config)])
        item = strategy.items[0]
        item.query_configs[0].result_table_id = "2_system.disk"
        item.target = [[]]

        CMDBTopoNodeAggConvert.convert(strategy)
        assert mock_metric_split_api.call_count == 0

        item.target = [
            [
                {
                    "field": "bk_target_ip",
                    "method": "eq",
                    "value": [
                        {"ip": "set", "bk_cloud_id": 2},
                        {"ip": "module", "bk_cloud_id": 1},
                        {"ip": "module", "bk_cloud_id": 2},
                    ],
                }
            ]
        ]
        CMDBTopoNodeAggConvert.convert(strategy)
        assert mock_metric_split_api.call_count == 0

    def test_service_and_module_node_target(self, mock_metric_split_api):
        strategy = Strategy(bk_biz_id=1, scenario="os", name="test", items=[copy.deepcopy(self.Config)])
        item = strategy.items[0]
        item.query_configs[0].result_table_id = "2_system.disk"
        item.target = [
            [
                {
                    "field": "host_set_template",
                    "method": "eq",
                    "value": [
                        {"bk_obj_id": "SET_TEMPLATE", "bk_inst_id": 1},
                        {"bk_obj_id": "SET_TEMPLATE", "bk_inst_id": 2},
                        {"bk_obj_id": "SERVICE_TEMPLATE", "bk_inst_id": 1},
                        {"bk_obj_id": "SERVICE_TEMPLATE", "bk_inst_id": 2},
                    ],
                }
            ]
        ]
        CMDBTopoNodeAggConvert.convert(strategy)
        assert mock_metric_split_api.call_count == 2
        assert item.query_configs[0].result_table_id == "test.test_cmdb_level"

    def test_instance_dimension(self, mock_metric_split_api):
        strategy = Strategy(bk_biz_id=1, scenario="os", name="test", items=[copy.deepcopy(self.Config)])
        item = strategy.items[0]
        item.query_configs[0].result_table_id = "2_system.disk"
        item.query_configs[0].agg_dimension = ["bk_target_ip", "bk_target_cloud_id"]

        CMDBTopoNodeAggConvert.convert(strategy)
        assert mock_metric_split_api.call_count == 0

        item.query_configs[0].agg_dimension = ["bk_target_service_instance_id"]
        CMDBTopoNodeAggConvert.convert(strategy)
        assert mock_metric_split_api.call_count == 0

    def test_reset(self):
        strategy = Strategy(bk_biz_id=1, scenario="os", name="test", items=[copy.deepcopy(self.Config)])
        item = strategy.items[0]
        item.query_configs[0].result_table_id = "2_system.disk"
        item.query_configs[0].agg_dimension = ["bk_obj_id", "bk_inst_id"]
        item.query_configs[0].origin_config = {"result_table_id": "system.disk", "agg_dimension": []}

        CMDBTopoNodeAggConvert.restore(strategy)
        assert item.query_configs[0].agg_dimension == []
        assert item.query_configs[0].result_table_id == "system.disk"


class TestEventMetric:
    Config = {
        "name": "name",
        "expression": "a + b",
        "origin_sql": "test",
        "no_data_config": {},
        "target": [
            [
                {
                    "field": "host_topo_node",
                    "method": "eq",
                    "value": [
                        {"bk_obj_id": "set", "bk_inst_id": 1},
                        {"bk_obj_id": "set", "bk_inst_id": 2},
                        {"bk_obj_id": "module", "bk_inst_id": 1},
                        {"bk_obj_id": "module", "bk_inst_id": 2},
                    ],
                }
            ]
        ],
        "algorithms": [{"type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "xxx"}],
        "query_configs": [
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "event",
                "alias": "a",
                "result_table_id": "system.event",
                "metric_field": "ping-gse",
                "agg_condition": [],
            }
        ],
    }

    def test_ping(self):
        strategy = Strategy(bk_biz_id=1, scenario="os", name="test", items=[copy.deepcopy(self.Config)])
        item = strategy.items[0]
        FakeEventConvert.convert(strategy)

        assert item.query_configs[0].data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        assert item.query_configs[0].data_type_label == DataTypeLabel.TIME_SERIES
        assert item.query_configs[0].result_table_id == "pingserver.base"
        assert item.query_configs[0].metric_field == "loss_percent"
        assert item.query_configs[0].agg_method == "MAX"
        assert item.query_configs[0].agg_interval == 60
        assert item.query_configs[0].agg_dimension == ["bk_target_ip", "bk_target_cloud_id", "ip", "bk_cloud_id"]

        FakeEventConvert.restore(strategy)
        assert item.query_configs[0].data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        assert item.query_configs[0].data_type_label == DataTypeLabel.EVENT
        assert item.query_configs[0].metric_field == "ping-gse"
        assert item.query_configs[0].result_table_id == SYSTEM_EVENT_RT_TABLE_ID

    def test_os_restart(self):
        strategy = Strategy(bk_biz_id=1, scenario="os", name="test", items=[copy.deepcopy(self.Config)])
        item = strategy.items[0]
        item.query_configs[0].metric_field = "os_restart"
        FakeEventConvert.convert(strategy)

        assert item.query_configs[0].data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        assert item.query_configs[0].data_type_label == DataTypeLabel.TIME_SERIES
        assert item.query_configs[0].result_table_id == "system.env"
        assert item.query_configs[0].metric_field == "uptime"
        assert item.query_configs[0].agg_method == "MAX"
        assert item.query_configs[0].agg_interval == 60
        assert item.query_configs[0].agg_dimension == ["bk_target_ip", "bk_target_cloud_id"]

        FakeEventConvert.restore(strategy)
        assert item.query_configs[0].data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        assert item.query_configs[0].data_type_label == DataTypeLabel.EVENT
        assert item.query_configs[0].metric_field == "os_restart"
        assert item.query_configs[0].result_table_id == SYSTEM_EVENT_RT_TABLE_ID

    def test_proc_port(self):
        strategy = Strategy(bk_biz_id=1, scenario="os", name="test", items=[copy.deepcopy(self.Config)])
        item = strategy.items[0]
        item.query_configs[0].metric_field = "proc_port"
        FakeEventConvert.convert(strategy)

        assert item.query_configs[0].data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        assert item.query_configs[0].data_type_label == DataTypeLabel.TIME_SERIES
        assert item.query_configs[0].result_table_id == "system.proc_port"
        assert item.query_configs[0].metric_field == "proc_exists"
        assert item.query_configs[0].agg_method == "MAX"
        assert item.query_configs[0].agg_interval == 60
        assert item.query_configs[0].agg_dimension == [
            "bk_target_ip",
            "bk_target_cloud_id",
            "display_name",
            "protocol",
            "listen",
            "nonlisten",
            "not_accurate_listen",
            "bind_ip",
        ]

        FakeEventConvert.restore(strategy)
        assert item.query_configs[0].data_source_label == DataSourceLabel.BK_MONITOR_COLLECTOR
        assert item.query_configs[0].data_type_label == DataTypeLabel.EVENT
        assert item.query_configs[0].metric_field == "proc_port"
        assert item.query_configs[0].result_table_id == SYSTEM_EVENT_RT_TABLE_ID


class TestDimensionProcess:
    Config = {
        "name": "name",
        "expression": "a + b",
        "origin_sql": "test",
        "no_data_config": {},
        "target": [[{"field": "bk_target_ip", "method": "eq", "value": [{"ip": "127.0.0.1", "bk_cloud_id": 0}]}]],
        "algorithms": [{"type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "xxx"}],
        "query_configs": [
            {
                "data_source_label": "bk_monitor",
                "data_type_label": "time_series",
                "alias": "a",
                "result_table_id": "system.disk",
                "metric_field": "usage",
                "unit": "percent",
                "extend_fields": {},
                "agg_method": "avg",
                "agg_condition": [],
                "agg_dimension": [],
                "agg_interval": 60,
            }
        ],
    }

    def test_instance_target_dimension(self):
        item = Item(strategy_id=1, **copy.deepcopy(self.Config))
        item.supplement_inst_target_dimension()
        assert set(item.query_configs[0].agg_dimension) == {"bk_target_ip", "bk_target_cloud_id"}

    def test_advance_condition_dimension(self):
        item = Item(strategy_id=1, **copy.deepcopy(self.Config))
        item.query_configs[0].agg_condition = [{"key": "test", "method": "reg", "value": [1, 2]}]
        item.query_configs[0].supplement_adv_condition_dimension()
        assert item.query_configs[0].agg_dimension == ["test"]
