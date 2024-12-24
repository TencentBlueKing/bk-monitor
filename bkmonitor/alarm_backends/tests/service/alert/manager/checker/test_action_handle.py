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
import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from alarm_backends.core.alert import Alert, Event
from alarm_backends.core.alert.adapter import MonitorEventAdapter
from alarm_backends.core.cache.key import ALERT_DEDUPE_CONTENT_KEY
from alarm_backends.core.cache.strategy import StrategyCacheManager
from alarm_backends.service.alert.manager.checker.action import ActionHandleChecker
from alarm_backends.tests.service.alert.manager.checker import (
    ANOMALY_EVENT,
    NOTICE,
    STRATEGY,
)
from bkmonitor.documents import ActionInstanceDocument
from bkmonitor.models import ActionInstance, ActionPlugin
from constants.action import ActionPluginType, ActionSignal

pytestmark = pytest.mark.django_db


@pytest.fixture()
def create_interval_actions_mock(mocker):
    return mocker.patch("alarm_backends.service.fta_action.tasks.create_interval_actions.delay", return_value=1)


@pytest.fixture()
def action_config(mocker):
    notice_action_config = {
        "execute_config": {
            "template_detail": {
                "interval_notify_mode": "standard",  # 间隔模式
                "notify_interval": 7200,  # 通知间隔
                "template": {},
            }
        },
        "id": 55555,
        "plugin_id": 1,
        "plugin_type": "notice",
        "is_enabled": True,
        "bk_biz_id": 2,
        "name": "test_notice",
    }
    return (
        mocker.patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            return_value=notice_action_config,
        ),
    )


@pytest.fixture()
def init_configs():
    ALERT_DEDUPE_CONTENT_KEY.client.flushall()
    StrategyCacheManager.cache.set(
        StrategyCacheManager.CACHE_KEY_TEMPLATE.format(strategy_id=STRATEGY["id"]), json.dumps(STRATEGY)
    )
    ActionPlugin.objects.all().delete()
    ActionPlugin.objects.create(
        **{
            "id": 1,
            "name": "通知告警",
            "is_enabled": True,
            "is_builtin": True,
            "is_deleted": False,
            "is_peripheral": False,
            "plugin_type": "notice",
            "plugin_key": "notice",
            "plugin_source": "builtin",
            "description": "告警通知是平台内置的套餐类型，由平台自身实现。可以对告警信息基于人进行收敛，可以对接不同的告警通知渠道。 "
            "\n\n* 基于人进行收敛\n* 有告警风暴控制能力\n* 可以定制不同的告警模版\n* 内置基于不同的通知渠道显示的变量\n* "
            "可以自定义各种通知渠道[查看文档]()\n\n更多[查看文档]()",
            "config_schema": {
                "content_template": "发送{{notice_way_display}}告警通知给{{notice_receiver}}{{status_display}}",
                "content_template_with_url": "达到通知告警的执行条件【{{action_signal}}】，已触发告警通知",
                "content_template_without_assignee": "达到通知告警的执行条件【{{action_signal}}】，当前通知人员为空",
                "content_template_shielded": "达到通知告警的执行条件【{{action_signal}}】，因告警已被屏蔽或不在通知时间段，忽略通知发送",
                "content_template_shielded_with_url": "达到通知告警的执行条件【{{action_signal}}】，因告警已被屏蔽忽略通知发送，点击$查看屏蔽策略$",
            },
            "backend_config": [{"function": "execute_notify", "name": "发送通知"}],
        }
    )


class TestAlertHandleChecker:
    @classmethod
    def get_alert(cls, strategy=None, event=None):
        event = MonitorEventAdapter(event or ANOMALY_EVENT, strategy or STRATEGY).adapt()
        event["extra_info"]["strategy"] = strategy or STRATEGY
        alert = Alert.from_event(Event(event))
        ALERT_DEDUPE_CONTENT_KEY.client.set(
            ALERT_DEDUPE_CONTENT_KEY.get_key(strategy_id=alert.strategy_id, dedupe_md5=alert.dedupe_md5),
            json.dumps(alert.to_dict()),
        )
        return alert

    def test_interval_notice(self, create_interval_actions_mock, action_config, init_configs):
        strategy = copy.deepcopy(STRATEGY)
        # 通知设置
        strategy["notice"] = {
            "id": 1,
            # 套餐ID，如果不选套餐请置为0
            "config_id": 55555,
            # 告警组ID
            "user_groups": [],
            "signal": ["abnormal", "recovered", "ack"],
            "options": {
                "converge_config": {
                    "is_enabled": True,
                    "converge_func": "collect",
                    "timedelta": 60,
                    "count": 1,
                    "condition": [
                        {"dimension": "strategy_id", "value": ["self"]},
                        {"dimension": "dimensions", "value": ["self"]},
                        {"dimension": "alert_level", "value": ["self"]},
                        {"dimension": "signal", "value": ["self"]},
                        {"dimension": "bk_biz_id", "value": ["self"]},
                        {"dimension": "notice_receiver", "value": ["self"]},
                        {"dimension": "notice_way", "value": ["self"]},
                        {"dimension": "notice_info", "value": ["self"]},
                    ],
                    "need_biz_converge": True,
                    "sub_converge_config": {
                        "timedelta": 60,
                        "count": 2,
                        "condition": [
                            {"dimension": "bk_biz_id", "value": ["self"]},
                            {"dimension": "notice_receiver", "value": ["self"]},
                            {"dimension": "notice_way", "value": ["self"]},
                            {"dimension": "alert_level", "value": ["self"]},
                            {"dimension": "signal", "value": ["self"]},
                        ],
                        "converge_func": "collect_alarm",
                    },
                },
                "start_time": "00:00:00",
                "end_time": "23:59:59",
            },
            "execute_config": {
                "template_detail": {
                    # 间隔模式
                    "interval_notify_mode": "standard",
                    # 通知间隔
                    "notify_interval": 7200,
                    # 通知模板配置
                    "template": [{"signal": "abnormal"}],
                }
            },
        }
        alert = self.get_alert(strategy)
        alert.update_extra_info(
            "cycle_handle_record",
            {"1": {"last_time": int(time.time()) - 7200, "latest_anomaly_time": 123, "execute_times": 1}},
        )
        alert.data["is_handled"] = True

        ActionHandleChecker([alert]).check_all()

        # 满足周期任务的条件，触发周期通知
        assert create_interval_actions_mock.call_count == 1
        assert alert.cycle_handle_record["1"]["execute_times"] == 2

        ActionHandleChecker([alert]).check_all()
        # 在检查一次， 此时应该不满足满足周期任务的条件，不会触发周期通知
        assert create_interval_actions_mock.call_count == 1

    def test_mute_interval_notice__latest_time(self, create_interval_actions_mock, action_config, init_configs):
        strategy = copy.deepcopy(STRATEGY)
        strategy["notice"] = NOTICE
        alert = self.get_alert(strategy)
        alert.update_extra_info(
            "cycle_handle_record",
            {"1": {"last_time": int(time.time()) - 7200, "latest_anomaly_time": int(time.time()), "execute_times": 1}},
        )
        alert.data["is_handled"] = True

        ActionHandleChecker([alert]).check_all()

        # 最近发送异常点时间大于当前最近异常点事件，不满足条件
        assert create_interval_actions_mock.call_count == 0
        assert alert.cycle_handle_record["1"]["execute_times"] == 1

    def test_interval_notice__latest_action(self, create_interval_actions_mock, action_config, init_configs):
        strategy = copy.deepcopy(STRATEGY)
        strategy["notice"] = NOTICE
        alert = self.get_alert(strategy)
        alert.data["is_handled"] = True
        action = ActionInstance.objects.create(
            id=1,
            signal=ActionSignal.ABNORMAL,
            strategy_id=0,
            alerts=[alert.id],
            alert_level=alert.severity,
            bk_biz_id=2,
            inputs={"alert_latest_time": 12345},
            action_config={},
            execute_times=1,
            action_config_id=55555,
            strategy_relation_id=1,
            need_poll=True,
            is_polled=False,
            action_plugin={
                "plugin_type": ActionPluginType.NOTICE,
                "name": "测试",
                "plugin_key": ActionPluginType.NOTICE,
            },
            end_time=datetime.now(tz=timezone.utc) - timedelta(hours=2),
        )
        ActionInstanceDocument.bulk_create(
            [
                ActionInstanceDocument(
                    id=1,
                    raw_id=1,
                    alert_id=[alert.id],
                    create_time=int(time.time()),
                    action_config_id=action.action_config_id,
                    parent_action_id=0,
                ),
                ActionInstanceDocument(
                    raw_id=2,
                    id=2,
                    alert_id=[alert.id],
                    create_time=int(time.time()) - 1800,
                    action_config_id=action.action_config_id,
                    parent_action_id=0,
                ),
            ],
            action="upsert",
        )
        ActionHandleChecker([alert]).check_all()

        # 最近发送异常点时间大于当前最近异常点事件，不满足条件
        assert create_interval_actions_mock.call_count == 1
        assert alert.cycle_handle_record["1"]["execute_times"] == 2
