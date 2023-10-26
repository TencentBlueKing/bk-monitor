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

from bkmonitor.models import (
    Action as ActionModel,
    ActionNoticeMapping,
    AlgorithmModel,
    DetectModel,
    ItemModel,
    QueryConfigModel,
    StrategyModel,
    NoticeTemplate,
)
from bkmonitor.models import StrategyActionConfigRelation as RelationModel
from bkmonitor.strategy.new_strategy import Action, ActionConfigRelation, Algorithm, Detect, Item, QueryConfig, Strategy
from constants.action import ActionSignal

pytestmark = pytest.mark.django_db


class TestAction:
    def test_to_dict(self):
        config = {
            "id": 0,
            "type": "operate",
            "config": {
                "alarm_end_time": "23:59:59",
                "send_recovery_alarm": False,
                "alarm_start_time": "00:00:00",
                "alarm_interval": 1440,
            },
            "notice_group_ids": [1],
            "notice_template": {"anomaly_template": "aaa", "recovery_template": "aaa"},
        }
        action = Action(
            strategy_id=1,
            type="operate",
            config=config["config"],
            notice_group_ids=[1],
            notice_template={"anomaly_template": "aaa", "recovery_template": "aaa"},
        )

        assert action.to_dict() == config

        action = Action(
            strategy_id=1,
            type="operate",
            config=config["config"],
            notice_group_ids=[1],
            id=1,
            notice_template={"anomaly_template": "aaa", "recovery_template": "aaa"},
        )
        assert action.to_dict()["id"] == 1

    def test_save(self, clean_model):
        action = Action(
            strategy_id=1, type="ANOMALY_NOTICE", config={"test_save": True}, id=10000, notice_group_ids=[1, 2]
        )
        action.save()
        action_obj = ActionModel.objects.get(id=action.id)

        assert action_obj.strategy_id == 1
        assert action_obj.action_type == "ANOMALY_NOTICE"
        assert action_obj.config == {"test_save": True}
        assert action.id == action_obj.id
        assert ActionNoticeMapping.objects.filter(action_id=action.id).count() == 2
        assert NoticeTemplate.objects.filter(action_id=action.id).count() == 1

        action = Action(strategy_id=1, type="ANOMALY_NOTICE", config={"test_save": True}, notice_group_ids=[1])
        action.save()
        action_obj = ActionModel.objects.get(id=action.id)

        assert action_obj.strategy_id == 1
        assert action_obj.action_type == "ANOMALY_NOTICE"
        assert action_obj.config == {"test_save": True}
        assert action.id == action_obj.id
        assert ActionNoticeMapping.objects.filter(action_id=action.id).count() == 1

        action.type = "RECOVERY_NOTICE"
        action.notice_group_ids = [1, 3, 4]
        action.save()
        action_obj = ActionModel.objects.get(id=action.id)

        assert action_obj.action_type == "RECOVERY_NOTICE"
        assert not ActionNoticeMapping.objects.filter(action_id=action.id, notice_group_id=2).exists()
        assert (
            ActionNoticeMapping.objects.filter(action_id=action.id, notice_group_id__in=action.notice_group_ids).count()
            == 3
        )

    def test_delete_useless(self, clean_model):
        action_obj1 = ActionModel.objects.create(action_type="ANOMALY_NOTICE", strategy_id=1, config={})
        action_obj2 = ActionModel.objects.create(action_type="ANOMALY_NOTICE", strategy_id=1, config={})
        action_obj3 = ActionModel.objects.create(action_type="RECOVERY_NOTICE", strategy_id=2, config={})

        ActionNoticeMapping.objects.create(action_id=action_obj1.id, notice_group_id=1)
        ActionNoticeMapping.objects.create(action_id=action_obj2.id, notice_group_id=1)
        ActionNoticeMapping.objects.create(action_id=action_obj3.id, notice_group_id=1)

        Action.delete_useless(useless_action_ids=[action_obj2.id])
        assert ActionNoticeMapping.objects.filter(action_id__in=[action_obj1.id, action_obj3.id]).count() == 2


class TestActionRelation:
    def test_to_dict(self):
        config = {
            "signal": ActionSignal.ABNORMAL,
            "config_id": 1,
            "user_groups": [114, 203],
        }
        relation = ActionConfigRelation(strategy_id=1, **config)

        assert relation.to_dict()["id"] is None
        assert relation.to_dict()["is_combined"] is False
        config["id"] = 1
        config["is_combined"] = True

        relation = ActionConfigRelation(strategy_id=1, **config)
        assert relation.to_dict() == config

    def test_save(self, clean_model):
        config = {"signal": "abnormal", "config_id": 1, "user_groups": [114, 203], "is_combined": True}
        relation = ActionConfigRelation(strategy_id=1, **config)
        relation.save()

        relation_obj = RelationModel.objects.get(id=relation.id)

        assert relation_obj.strategy_id == 1
        assert relation_obj.signal == ActionSignal.ABNORMAL
        assert relation_obj.config_id == 1
        assert relation_obj.id == relation.id

    def test_delete_useless(self, clean_model):
        config = {"signal": "abnormal", "config_id": 1, "user_groups": [114, 203]}
        relation = ActionConfigRelation(strategy_id=2, **config)
        relation.save()
        config["id"] = relation.id

        relation.id = None
        # save again
        relation.save()

        relation.delete_useless(relation_ids=[relation.id])

        assert RelationModel.objects.filter(strategy_id=2).count() == 1


class TestAlgorithm:
    def test_to_dict(self):
        config = {"id": 1, "type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "%"}

        algorithm = Algorithm(strategy_id=1, item_id=1, **config)
        assert algorithm.to_dict() == config

        del config["id"]
        algorithm = Algorithm(strategy_id=1, item_id=1, **config)
        assert algorithm.to_dict()["id"] == 0

    def test_save(self, clean_model):
        algorithm = Algorithm(id=10000, strategy_id=1, item_id=1, level=2, type="type", config={"a": 1})
        algorithm.save()

        assert not AlgorithmModel.objects.filter(id=10000).exists()
        assert AlgorithmModel.objects.filter(id=algorithm.id).exists()

        algorithm = Algorithm(strategy_id=1, item_id=1, level=2, type="type", config={"a": 1})
        algorithm.save()
        assert AlgorithmModel.objects.filter(id=algorithm.id).exists()

        algorithm.type = "type1"
        algorithm.config = {"a": 2}
        algorithm.unit_prefix = "%"
        algorithm.level = 3
        algorithm.save()

        obj = AlgorithmModel.objects.get(id=algorithm.id)
        assert obj.type == "type1"
        assert obj.config == {"a": 2}
        assert obj.unit_prefix == "%"
        assert obj.level == 3


class TestDetect:
    def test_to_dict(self):
        config = {
            "id": 1,
            "level": 1,
            "expression": "",
            "trigger_config": {},
            "recovery_config": {},
            "connector": "and",
        }
        detect = Detect(strategy_id=1, **config)
        assert detect.to_dict() == config

        del config["id"]
        detect = Detect(strategy_id=1, **config)
        assert detect.to_dict()["id"] == 0

    def test_save(self, clean_model):
        detect = Detect(
            id=10000, level=2, expression="", trigger_config={}, recovery_config={}, strategy_id=1, connector="and"
        )
        detect.save()

        assert DetectModel.objects.filter(id=detect.id).exists()
        assert detect.id != 1000

        detect = Detect(level=2, expression="", trigger_config={}, recovery_config={}, strategy_id=1, connector="and")
        detect.save()
        assert DetectModel.objects.filter(id=detect.id).exists()

        detect_id = detect.id
        detect.level = 3
        detect.expression = "A + B"
        detect.trigger_config = {"a": 1}
        detect.recovery_config = {"b": 1}
        detect.connector = "or"
        detect.save()

        assert detect.id == detect_id

        obj = DetectModel.objects.get(id=detect.id)
        assert obj.level == detect.level
        assert obj.expression == detect.expression
        assert obj.trigger_config == detect.trigger_config
        assert obj.recovery_config == detect.recovery_config
        assert obj.connector == detect.connector


class TestItem:
    def test_to_dict(self):
        config = {
            "id": 1,
            "name": "name",
            "expression": "a + b",
            "origin_sql": "test",
            "no_data_config": {},
            "target": [[]],
            "query_configs": [
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "alias": "A",
                    "id": 1,
                    "result_table_id": "xxxx",
                    "metric_field": "aaa",
                    "metric_id": "bk_monitor.xxxx.aaa",
                    "unit": "xxx",
                    "agg_method": "avg",
                    "agg_condition": [],
                    "agg_dimension": [],
                    "agg_interval": 60,
                    "functions": [],
                }
            ],
            "algorithms": [
                {"id": 1, "type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "%"}
            ],
        }

        item = Item(strategy_id=1, **config)
        assert item.to_dict() == config

    def test_save(self, clean_model):
        config = {
            "id": 2,
            "name": "name",
            "expression": "a + b",
            "origin_sql": "test",
            "no_data_config": {},
            "target": [[]],
            "algorithms": [
                {"id": 1, "type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "%"}
            ],
            "query_configs": [
                {
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "alias": "A",
                    "id": 1,
                    "result_table_id": "xxxx",
                    "metric_field": "aaa",
                    "unit": "xxx",
                    "agg_method": "avg",
                    "agg_condition": [],
                    "agg_dimension": [],
                    "agg_interval": 60,
                }
            ],
        }

        item = Item(strategy_id=1, **config)
        item.save()

        assert item.id != 2
        assert ItemModel.objects.filter(id=item.id).exists()
        assert item.algorithms[0].id != 1
        assert AlgorithmModel.objects.filter(id=item.algorithms[0].id).exists()
        assert QueryConfigModel.objects.filter(id=item.query_configs[0].id).exists()

        old_item_id = item.id
        item.name = "name1"
        item.expression = "b + c"
        item.origin_sql = "test1"
        item.no_data_config = {"a": 1}
        item.query_configs = [
            QueryConfig(
                1,
                item.id,
                **{
                    "data_source_label": "bk_monitor",
                    "data_type_label": "time_series",
                    "alias": "a",
                    "id": 1,
                    "result_table_id": "xxxx",
                    "metric_field": "aaa",
                    "unit": "xxx",
                    "agg_method": "avg",
                    "agg_condition": [],
                    "agg_dimension": [],
                    "agg_interval": 60,
                }
            )
        ]
        item.algorithms[0].level = 2
        item.save()

        item_obj = ItemModel.objects.get(strategy_id=1, id=item.id)
        assert item.id == old_item_id
        assert item_obj.name == item.name
        assert item_obj.expression == item.expression
        assert item_obj.origin_sql == item.origin_sql
        assert item_obj.no_data_config == item.no_data_config

        algorithm_obj = AlgorithmModel.objects.get(strategy_id=1, item_id=item.id, id=item.algorithms[0].id)
        assert algorithm_obj.level == 2

        query_config_obj = QueryConfigModel.objects.get(strategy_id=1, id=item.query_configs[0].id)
        assert query_config_obj.config["unit"] == "xxx"


class TestStrategy:
    Config = {
        "id": 0,
        "bk_biz_id": 2,
        "name": "测试策略",
        "type": "monitor",
        "source": "bk_monitor",
        "scenario": "os",
        "type": "monitor",
        "is_enabled": True,
        "create_time": "2021-05-07T09:22:27.113718+00:00",
        "create_user": "system",
        "update_time": "2021-05-07T09:22:27.113718+00:00",
        "update_user": "system",
        "items": [
            {
                "id": 1,
                "name": "name",
                "expression": "a + b",
                "origin_sql": "test",
                "no_data_config": {},
                "target": [[]],
                "algorithms": [
                    {"id": 1, "type": "operate", "level": 1, "config": {"floor": 1, "ceil": 1}, "unit_prefix": "xxx"}
                ],
                "query_configs": [
                    {
                        "data_source_label": "bk_monitor",
                        "data_type_label": "time_series",
                        "alias": "A",
                        "id": 1,
                        "metric_id": "bk_monitor.xxxx.aaa",
                        "result_table_id": "xxxx",
                        "metric_field": "aaa",
                        "unit": "xxx",
                        "agg_method": "avg",
                        "agg_condition": [],
                        "agg_dimension": [],
                        "agg_interval": 60,
                        "functions": [],
                    }
                ],
            }
        ],
        "actions": [{"signal": "abnormal", "config_id": 1, "user_groups": [114, 203], "is_combined": True, "id": None}],
        "detects": [
            {
                "id": 1,
                "level": 1,
                "expression": "",
                "trigger_config": {"count": 1, "check_window": 2},
                "recovery_config": {"check_window": 2},
                "connector": "and",
            }
        ],
        "labels": [],
        "version": "v2",
    }

    def test_to_dict(self, clean_model):
        strategy = Strategy(**self.Config.copy())

        assert len(strategy.detects) == 1 and isinstance(strategy.detects[0], Detect)
        assert len(strategy.items) == 1 and isinstance(strategy.items[0], Item)
        assert len(strategy.actions) == 1 and isinstance(strategy.actions[0], ActionConfigRelation)
        assert len(strategy.items[0].query_configs) == 1 and isinstance(strategy.items[0].query_configs[0], QueryConfig)
        assert len(strategy.items[0].algorithms) == 1 and isinstance(strategy.items[0].algorithms[0], Algorithm)
        assert strategy.to_dict() == self.Config

    def test_save(self, clean_model):
        strategy = Strategy(**self.Config.copy())
        strategy.save()

        assert StrategyModel.objects.filter(id=strategy.id).exists()
        assert ItemModel.objects.filter(id=strategy.items[0].id).exists()
        assert RelationModel.objects.filter(id=strategy.actions[0].id).exists()
        assert DetectModel.objects.filter(id=strategy.detects[0].id).exists()
        assert AlgorithmModel.objects.filter(id=strategy.items[0].algorithms[0].id).exists()
        assert QueryConfigModel.objects.filter(id=strategy.items[0].query_configs[0].id).exists()

        old_strategy = copy.deepcopy(strategy)

        strategy.scenario = "host_process"
        strategy.items[0].expression = "b + a"
        strategy.actions[0].signal = ActionSignal.ABNORMAL
        strategy.detects[0].level = 2
        strategy.items[0].query_configs[0].result_table_id = "aaaa"
        strategy.items[0].algorithms[0].level = 2

        strategy.items[0].id = 0
        strategy.actions[0].id = 0
        strategy.detects[0].id = 0
        strategy.items[0].query_configs[0].id = 0
        strategy.items[0].algorithms[0].id = 0
        strategy.save()

        assert old_strategy.items[0].id == strategy.items[0].id
        assert old_strategy.actions[0].id == strategy.actions[0].id
        assert old_strategy.detects[0].id == strategy.detects[0].id
        assert old_strategy.items[0].query_configs[0].id == strategy.items[0].query_configs[0].id
        assert old_strategy.items[0].algorithms[0].id == strategy.items[0].algorithms[0].id

        assert StrategyModel.objects.get(id=strategy.id).scenario == strategy.scenario
        assert ItemModel.objects.get(id=strategy.items[0].id).expression == strategy.items[0].expression
        assert RelationModel.objects.get(id=strategy.actions[0].id).config_id == strategy.actions[0].config_id
        assert DetectModel.objects.get(id=strategy.detects[0].id).level == strategy.detects[0].level
        assert (
            AlgorithmModel.objects.get(id=strategy.items[0].algorithms[0].id).level
            == strategy.items[0].algorithms[0].level
        )
        assert (
            QueryConfigModel.objects.get(id=strategy.items[0].query_configs[0].id).config["result_table_id"]
            == strategy.items[0].query_configs[0].result_table_id
        )

    def test_from_model(self, clean_model):
        s1 = strategy = Strategy(**self.Config)
        strategy.save()

        self.Config["name"] = "测试策略2"
        s2 = strategy = Strategy(**self.Config)
        strategy.save()

        self.Config["type"] = "fta"
        self.Config["name"] = "测试策略3"
        s3 = strategy = Strategy(**self.Config)
        strategy.save()

        strategies = Strategy.from_models(StrategyModel.objects.all())
        assert len(strategies) == 3
        s1.create_time = strategies[0].create_time
        s2.create_time = strategies[1].create_time
        s3.create_time = strategies[2].create_time
        s1.update_time = strategies[0].update_time
        s2.update_time = strategies[1].update_time
        s3.update_time = strategies[2].update_time
        assert s1.to_dict() == strategies[0].to_dict()
        assert s2.to_dict() == strategies[1].to_dict()
        assert s3.to_dict() == strategies[2].to_dict()
