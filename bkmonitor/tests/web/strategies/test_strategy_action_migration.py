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


import pytest
from fta_web.handlers import migrate_actions
from bkmonitor.strategy.new_strategy import Strategy, Action, UserGroup
from bkmonitor.models import ActionConfig, GlobalConfig, StrategyActionConfigRelation
from bkmonitor.action.serializers import ActionConfigDetailSlz
from monitor_web.notice_group.resources import BackendSaveNoticeGroupResource

pytestmark = pytest.mark.django_db


class TestStrategyActionMigrate:
    Config = {
        "id": 0,
        "bk_biz_id": 2,
        "name": "测试策略",
        "source": "bk_monitor",
        "scenario": "os",
        "type": "monitor",
        "is_enabled": True,
        "create_time": "2021-06-13T09:22:27.113718+00:00",
        "create_user": "system",
        "update_time": "2021-06-13T09:22:27.113718+00:00",
        "update_user": "system",
        "items": [
            {
                "id": 1,
                "name": "name",
                "expression": "a + b",
                "origin_sql": "test",
                "no_data_config": {"is_enabled": True},
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
        "actions": [],
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

    notice_group_config = {
        "name": "测试用户组",
        "message": "用户组的说明",
        "bk_biz_id": 2,
        "notice_way": {1: ["weixin"], 2: ["weixin"], 3: ["weixin"]},
        "webhook_url": "http://www.baidu.com",
        "notice_receiver": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
        "wxwork_group": {3: "dsfksdkfjlskdjflksdjlfkasldf"},
    }

    user_group_config = {
        "name": "测试用户组",
        "desc": "用户组的说明",
        "bk_biz_id": 2,
        "duty_arranges": [
            {
                "duty_type": "always",
                "work_time": "always",
                "users": [{"id": "admin", "display_name": "管理员", "logo": "", "type": "user"}],
            }
        ],
    }

    old_action_config = {
        "id": 0,
        "type": "notice",
        "config": {
            "alarm_end_time": "23:59:59",
            "send_recovery_alarm": True,
            "alarm_start_time": "00:00:00",
            "alarm_interval": 1440,
        },
        "notice_group_ids": [1],
        "notice_template": {"anomaly_template": "aaa", "recovery_template": "aaa"},
    }

    def test_migrate_actions(self, clean_model):
        GlobalConfig.objects.filter(key="MIGRATE_ACTIONS_OPERATE").delete()
        notice_group_data = BackendSaveNoticeGroupResource().request(self.notice_group_config)

        strategy = Strategy(**self.Config)
        strategy.save()

        self.old_action_config["notice_group_ids"] = [notice_group_data["id"]]

        old_action = Action(strategy_id=strategy.id, **self.old_action_config)
        old_action.save()

        migrate_actions(sender=None)

        strategies_after_migrate = strategy.from_models([strategy])
        assert len(strategies_after_migrate[0].actions) == 4
        assert UserGroup.objects.filter(name="测试用户组").count() == 1
        assert ActionConfig.objects.filter(plugin_id=2).count() == 1
        assert ActionConfig.objects.filter(plugin_id=1).count() == 3
        assert StrategyActionConfigRelation.objects.filter(strategy_id=strategy.id, signal="abnormal").count() == 2
        assert StrategyActionConfigRelation.objects.filter(strategy_id=strategy.id, signal="no_data").count() == 1

        ac_data = ActionConfigDetailSlz(instance=ActionConfig.objects.filter(plugin_id=1).first()).data

        notify_type = [
            {"level": 1, "type": "weixin"},
            {"level": 2, "type": "weixin"},
            {"level": 3, "type": "weixin,wxwork-bot", "chatid": "dsfksdkfjlskdjflksdjlfkasldf"},
        ]
        assert ac_data["execute_config"]["template_detail"]["notify_config"]["notify_type"] == notify_type
