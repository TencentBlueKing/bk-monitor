"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from alarm_backends.core.context import ActionContext
from alarm_backends.service.fta_action import tasks, utils
from fta_web.action.resources import backend_resources


@pytest.mark.parametrize("config_count", [1, 2])
@pytest.mark.parametrize(
    ("groups", "expected_groups", "expected_alert_ids"),
    [
        ([["first"], ["second", "first"], ["foreign"]], [["first"], ["second", "first"]], ["first", "second"]),
        ([["foreign"]], [], []),
        ([], [], []),
    ],
)
def test_batch_create_keeps_all_authorized_alerts(
    monkeypatch, groups, expected_groups, expected_alert_ids, config_count
):
    """末组被过滤时仍推送此前合法任务，所有合法告警仅更新一次。"""
    alerts = {
        alert_id: SimpleNamespace(
            id=alert_id,
            event=SimpleNamespace(bk_biz_id=biz_id),
            strategy_id=1,
            severity=1,
            assignee=["previous"],
        )
        for alert_id, biz_id in [("first", 1), ("second", 1), ("foreign", 2)]
    }
    created_actions = []

    def create_action(**kwargs):
        action = SimpleNamespace(
            id=len(created_actions) + 1,
            create_time=datetime.now(),
            is_parent_action=False,
            strategy={},
            inputs={},
            **kwargs,
        )
        created_actions.append(action)
        return action

    action_manager = SimpleNamespace(
        create=Mock(side_effect=create_action),
        filter=lambda **kwargs: [
            action for action in created_actions if all(getattr(action, key) == value for key, value in kwargs.items())
        ],
    )
    document = Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs))
    document.mget.side_effect = lambda ids: [alerts[alert_id] for alert_id in ids]
    alert_log = Mock()
    alert_log.OpType.ACTION = "action"
    dispatch = Mock()
    monkeypatch.setattr(backend_resources, "ActionInstance", SimpleNamespace(objects=action_manager))
    monkeypatch.setattr(utils, "ActionInstance", SimpleNamespace(objects=action_manager))
    monkeypatch.setattr(backend_resources, "ActionPlugin", SimpleNamespace(objects=SimpleNamespace(all=lambda: [])))
    monkeypatch.setattr(
        backend_resources,
        "ActionPluginSlz",
        lambda **kwargs: SimpleNamespace(data=[{"id": 1, "plugin_type": "message_queue"}]),
    )
    monkeypatch.setattr(backend_resources, "AlertDocument", document)
    monkeypatch.setattr(backend_resources, "AlertLog", alert_log)
    monkeypatch.setattr(tasks, "dispatch_action_task", dispatch)
    monkeypatch.setattr(backend_resources, "get_user_display_name", lambda name: name)
    data = {
        "bk_biz_id": "1",
        "creator": "operator",
        "operate_data_list": [
            {
                "alert_ids": alert_ids,
                "action_configs": [{"config_id": index + 1, "plugin_id": 1} for index in range(config_count)],
            }
            for alert_ids in groups
        ],
    }

    result = backend_resources.BatchCreateActionResource().perform_request(data)

    assert [action.alerts for action in created_actions] == [
        group for group in expected_groups for _ in range(config_count)
    ]
    assert result == {"actions": [action.id for action in created_actions], "alert_ids": expected_alert_ids}
    if not expected_alert_ids:
        dispatch.assert_not_called()
        document.bulk_create.assert_not_called()
        alert_log.bulk_create.assert_not_called()
        return

    assert dispatch.call_count == len(created_actions)
    for action, call in zip(created_actions, dispatch.call_args_list):
        assert call.args[1]["id"] == action.id
        # 消息队列插件强制使用该快照；普通插件缓存缺失时也回退到它。
        context = ActionContext.__new__(ActionContext)
        context.use_alert_snap = True
        context.related_alerts = call.args[1]["alerts"]
        assert [alert.id for alert in context.alerts] == action.alerts
    document.bulk_create.assert_called_once()
    updated_alerts = document.bulk_create.call_args.args[0]
    assert [alert.id for alert in updated_alerts] == expected_alert_ids
    assert all(alert.is_handled and set(alert.assignee) == {"previous", "operator"} for alert in updated_alerts)
    alert_log.bulk_create.assert_called_once()
    assert len(alert_log.bulk_create.call_args.args[0]) == len(expected_groups) * config_count
