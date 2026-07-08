"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from alarm_backends.core.cache.strategy import StrategyCacheManager
from core.drf_resource import api

from constants.data_source import DataSourceLabel, DataTypeLabel
from constants.strategy import TargetFieldType


def test_system_event_target_shield_respects_agg_condition(monkeypatch):
    monkeypatch.setattr(
        api.cmdb,
        "get_mainline_object_topo",
        lambda: [{"bk_obj_id": "biz"}, {"bk_obj_id": "set"}, {"bk_obj_id": "module"}],
    )

    biz_target = {
        "field": TargetFieldType.host_topo,
        "method": "eq",
        "value": [{"bk_obj_id": "biz", "bk_inst_id": 2}],
    }
    set_target = {
        "field": TargetFieldType.host_topo,
        "method": "eq",
        "value": [{"bk_obj_id": "set", "bk_inst_id": 100}],
    }

    strategy_configs = [
        make_system_event_strategy(
            strategy_id=1,
            target=biz_target,
            agg_condition=[{"key": "process_name", "method": "eq", "value": ["process_a"]}],
        ),
        make_system_event_strategy(
            strategy_id=2,
            target=set_target,
            agg_condition=[{"key": "process_name", "method": "neq", "value": ["process_a"]}],
        ),
    ]

    StrategyCacheManager.add_target_shield_condition(strategy_configs)

    assert strategy_configs[0]["items"][0]["target"] == [[biz_target]]


def test_system_event_target_shield_keeps_same_query_shield(monkeypatch):
    monkeypatch.setattr(
        api.cmdb,
        "get_mainline_object_topo",
        lambda: [{"bk_obj_id": "biz"}, {"bk_obj_id": "set"}, {"bk_obj_id": "module"}],
    )

    biz_target = {
        "field": TargetFieldType.host_topo,
        "method": "eq",
        "value": [{"bk_obj_id": "biz", "bk_inst_id": 2}],
    }
    set_target = {
        "field": TargetFieldType.host_topo,
        "method": "eq",
        "value": [{"bk_obj_id": "set", "bk_inst_id": 100}],
    }
    agg_condition = [{"key": "event_name", "method": "eq", "value": ["process_restart_success"]}]

    strategy_configs = [
        make_system_event_strategy(strategy_id=1, target=biz_target, agg_condition=agg_condition),
        make_system_event_strategy(strategy_id=2, target=set_target, agg_condition=agg_condition),
    ]

    StrategyCacheManager.add_target_shield_condition(strategy_configs)

    assert strategy_configs[0]["items"][0]["target"] == [
        [
            biz_target,
            {
                "field": TargetFieldType.host_topo,
                "method": "neq",
                "value": [{"bk_obj_id": "set", "bk_inst_id": 100}],
            },
        ]
    ]


def test_query_md5_target_shield_keeps_existing_group(monkeypatch):
    monkeypatch.setattr(
        api.cmdb,
        "get_mainline_object_topo",
        lambda: [{"bk_obj_id": "biz"}, {"bk_obj_id": "set"}, {"bk_obj_id": "module"}],
    )

    biz_target = {
        "field": TargetFieldType.host_topo,
        "method": "eq",
        "value": [{"bk_obj_id": "biz", "bk_inst_id": 2}],
    }
    set_target = {
        "field": TargetFieldType.host_topo,
        "method": "eq",
        "value": [{"bk_obj_id": "set", "bk_inst_id": 100}],
    }
    query_md5 = "query-md5"

    strategy_configs = [
        make_system_event_strategy(strategy_id=1, target=biz_target, agg_condition=[]),
        make_system_event_strategy(strategy_id=2, target=set_target, agg_condition=[]),
    ]
    for strategy_config in strategy_configs:
        strategy_config["items"][0]["query_md5"] = query_md5

    StrategyCacheManager.add_target_shield_condition(strategy_configs)

    assert strategy_configs[0]["items"][0]["target"] == [
        [
            biz_target,
            {
                "field": TargetFieldType.host_topo,
                "method": "neq",
                "value": [{"bk_obj_id": "set", "bk_inst_id": 100}],
            },
        ]
    ]


def make_system_event_strategy(strategy_id, target, agg_condition):
    return {
        "id": strategy_id,
        "bk_biz_id": 2,
        "priority": None,
        "items": [
            {
                "id": strategy_id * 10,
                "name": "system_event",
                "expression": "a",
                "functions": [],
                "query_md5": "",
                "target": [[target]],
                "query_configs": [
                    {
                        "data_source_label": DataSourceLabel.BK_MONITOR_COLLECTOR,
                        "data_type_label": DataTypeLabel.EVENT,
                        "metric_id": "bk_monitor.gse_process_event",
                        "agg_method": "COUNT",
                        "agg_interval": 60,
                        "agg_dimension": [],
                        "agg_condition": agg_condition,
                        "result_table_id": "system.event",
                        "metric_field": "event",
                    }
                ],
            }
        ],
    }
