"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at https://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time
from types import SimpleNamespace
from unittest import mock

from alarm_backends.service.fta_action.tasks.alert_assign import (
    AlertAssigneeManager,
    BackendAlertMatchContext,
)
from alarm_backends.service.fta_action.tasks.create_action import CreateActionProcessor
from bkmonitor.action.alert_assign import AlertAssignMatchManager
from constants.action import ActionNoticeType, ActionSignal, AssignMode, UserGroupType


def build_assignee_manager():
    alert = SimpleNamespace(
        id="alert-id",
        severity=2,
        strategy={"id": 123},
        event=SimpleNamespace(bk_biz_id=2),
    )
    manager = AlertAssigneeManager.__new__(AlertAssigneeManager)
    manager.alert = alert
    manager.assign_mode = [AssignMode.ONLY_NOTICE]
    manager.notice_type = ActionNoticeType.NORMAL
    manager.origin_notice_users_object = None
    manager.match_manager = None
    manager._subscription_match_context = None
    manager._subscription_notify_info = None
    return manager


def build_match_alert():
    return SimpleNamespace(
        id="alert-id",
        alert_name="multi metric alert",
        severity=2,
        strategy={"id": 123, "scenario": "os"},
        labels=["label-a"],
        dimensions=[],
        origin_alarm=None,
        extra_info=None,
        event=SimpleNamespace(
            plugin_id="bkmonitor",
            metric=["metric_a", "metric_b"],
            tags=[],
            bk_biz_id=2,
            bk_cloud_id=0,
        ),
    )


def build_create_action_case(subscription_notify_info):
    alert = mock.MagicMock()
    alert.id = "alert-id"
    alert.to_dict.return_value = {}
    alert.is_no_data.return_value = False
    alert.__getitem__.return_value = int(time.time())

    action = {
        "id": 9,
        "config_id": 1,
        "options": {"skip_delay": 0},
        "signal": [ActionSignal.ABNORMAL],
    }
    processor = CreateActionProcessor.__new__(CreateActionProcessor)
    processor.strategy_id = 123
    processor.strategy = {"id": 123}
    processor.signal = ActionSignal.ABNORMAL
    processor.severity = 2
    processor.relation_id = None
    processor.execute_times = 0
    processor.notice_type = ActionNoticeType.NORMAL
    processor.is_alert_shielded = False
    processor.noise_reduce_result = False
    processor._notice_noise_reduce_processed = False
    processor.generate_uuid = "generate-uuid"
    processor.notice = {
        "id": 9,
        "config_id": 1,
        "user_groups": [],
        "options": {"assign_mode": [AssignMode.BY_RULE]},
    }
    processor.alerts = [alert]
    processor.alert_ids = [alert.id]
    processor.alert_objs = {alert.id: alert}

    assignee_manager = mock.MagicMock()
    assignee_manager.is_matched = False
    assignee_manager.match_manager = None
    assignee_manager.get_assignees.return_value = []
    assignee_manager.get_notify_info.side_effect = lambda user_type=UserGroupType.MAIN: {}
    assignee_manager.get_appointee_notify_info.return_value = {}
    assignee_manager.get_subscription_notify_info.return_value = subscription_notify_info

    processor.get_action_relations = mock.Mock(return_value=[action])
    processor.get_alert_shield_result = mock.Mock(return_value=(False, []))
    processor.create_message_queue_action = mock.Mock()
    processor.is_alert_status_valid = mock.Mock(return_value=True)
    processor.alert_assign_handle = mock.Mock(return_value=assignee_manager)
    processor.get_alert_related_users = mock.Mock(return_value=[])
    processor.is_action_config_valid = mock.Mock(return_value=True)
    processor.do_create_action = mock.Mock(return_value=mock.Mock())
    processor.update_alert_documents = mock.Mock()
    processor._process_issue_aggregation = mock.Mock()
    return processor, alert, assignee_manager


def run_create_action_case(processor, plugin_type="notice"):
    with (
        mock.patch(
            "alarm_backends.service.fta_action.tasks.create_action.ActionConfigCacheManager.get_action_config_by_id",
            return_value={"plugin_id": 7, "name": "notice"},
        ),
        mock.patch("alarm_backends.service.fta_action.tasks.create_action.ActionPlugin"),
        mock.patch("alarm_backends.service.fta_action.tasks.create_action.ActionPluginSlz") as plugin_serializer,
        mock.patch("alarm_backends.service.fta_action.tasks.create_action.ActionInstance"),
        mock.patch("alarm_backends.service.fta_action.tasks.create_action.PushActionProcessor"),
        mock.patch("alarm_backends.service.fta_action.tasks.create_action.AssignCacheManager"),
        mock.patch("alarm_backends.service.fta_action.tasks.create_action.SubscribeCacheManager"),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.create_action.NoiseReduceRecordProcessor"
        ) as noise_reduce_processor,
    ):
        plugin_serializer.return_value.data = [{"id": 7, "plugin_type": plugin_type}]
        noise_reduce_processor.return_value.process.return_value = False
        processor.do_create_actions()
    return noise_reduce_processor


def test_subscription_matches_without_by_rule():
    manager = build_assignee_manager()

    subscription_match_manager = SimpleNamespace(
        dimensions={"alert.strategy_id": "123", "alert.metric": ["metric_a", "metric_b"]},
        origin_severity=2,
    )
    rule = {
        "id": 1,
        "conditions": [],
        "notice_ways": ["mail"],
        "user_type": "main",
    }

    with (
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_users_by_biz",
            return_value=["subscriber"],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_rules_by_user",
            return_value=[rule],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.BackendAlertMatchContext",
            return_value=subscription_match_manager,
            create=True,
        ) as subscription_context_class,
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.BackendAssignMatchManager",
            return_value=subscription_match_manager,
        ) as assign_manager_class,
    ):
        notify_info, follow_notify_info = manager.get_subscription_notify_info()

    assert notify_info == {"mail": ["subscriber"]}
    assert follow_notify_info == {}
    subscription_context_class.assert_called_once_with(manager.alert, notice_users=[])
    assign_manager_class.assert_not_called()


def test_neutral_and_assignment_context_build_the_same_multi_metric_dimensions():
    alert = build_match_alert()

    subscription_context = BackendAlertMatchContext(alert, notice_users=["default_user"], cmdb_attrs={})
    assignment_context = AlertAssignMatchManager(alert, notice_users=["default_user"], cmdb_attrs={})

    assert subscription_context.dimensions == assignment_context.dimensions
    assert subscription_context.dimensions["alert.metric"] == ["metric_a", "metric_b"]
    assert subscription_context.dimensions["notice_users"] == ["default_user"]


def test_origin_notice_users_flattens_voice_receivers_for_match_dimensions():
    manager = build_assignee_manager()
    manager.origin_notice_users_object = mock.Mock()
    manager.origin_notice_users_object.get_notice_receivers.return_value = {
        "mail": ["mail_user"],
        "voice": [["voice_user_a", "voice_user_b"]],
        "wxbot_mention_users": ["mention_user"],
    }

    assert set(manager.get_origin_notice_users()) == {"mail_user", "voice_user_a", "voice_user_b"}


def test_multi_metric_subscription_condition_matches_any_metric():
    manager = build_assignee_manager()
    dimensions = BackendAlertMatchContext(build_match_alert(), cmdb_attrs={}).dimensions
    rule = {
        "conditions": [
            {
                "field": "alert.metric",
                "method": "eq",
                "value": ["metric_b"],
            }
        ]
    }

    assert manager._is_subscription_rule_matched(rule, dimensions) is True


def test_subscription_result_is_reused_for_the_same_alert():
    manager = build_assignee_manager()
    subscription_match_manager = SimpleNamespace(
        dimensions={"alert.strategy_id": "123"},
        origin_severity=2,
    )
    rule = {
        "id": 1,
        "conditions": [],
        "notice_ways": ["mail"],
        "user_type": "follower",
    }

    with (
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_users_by_biz",
            return_value=["subscriber"],
        ) as get_users_by_biz,
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_rules_by_user",
            return_value=[rule],
        ) as get_rules_by_user,
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.BackendAlertMatchContext",
            return_value=subscription_match_manager,
            create=True,
        ),
    ):
        first_result = manager.get_subscription_notify_info()
        second_result = manager.get_subscription_notify_info()

    assert first_result is second_result
    get_users_by_biz.assert_called_once_with(2)
    get_rules_by_user.assert_called_once_with(2, "subscriber")


def test_dynamic_group_conversion_does_not_mutate_cached_rule():
    manager = build_assignee_manager()
    subscription_match_manager = SimpleNamespace(
        dimensions={"bk_host_id": "101"},
        origin_severity=2,
        get_host_ids_by_dynamic_groups=mock.Mock(return_value=[101]),
    )
    rule = {
        "id": 1,
        "conditions": [
            {
                "field": "dynamic_group",
                "method": "eq",
                "value": [9],
            }
        ],
        "notice_ways": ["mail"],
        "user_type": "main",
    }

    with (
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_users_by_biz",
            return_value=["subscriber"],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_rules_by_user",
            return_value=[rule],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.BackendAlertMatchContext",
            return_value=subscription_match_manager,
            create=True,
        ),
        mock.patch.object(manager, "_is_subscription_rule_matched", return_value=True),
    ):
        manager.get_subscription_notify_info()

    assert rule["conditions"] == [
        {
            "field": "dynamic_group",
            "method": "eq",
            "value": [9],
        }
    ]


def test_invalid_subscription_rule_isolated_and_valid_voice_rule_still_matches():
    manager = build_assignee_manager()
    subscription_match_manager = SimpleNamespace(
        dimensions={"alert.strategy_id": "123"},
        origin_severity=2,
    )
    invalid_rule = {"id": 1, "conditions": [{"method": "eq", "value": "123"}]}
    valid_rule = {
        "id": 2,
        "conditions": [],
        "notice_ways": ["voice"],
        "user_type": "follower",
    }

    with (
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_users_by_biz",
            return_value=["subscriber"],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_rules_by_user",
            return_value=[invalid_rule, valid_rule],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.BackendAlertMatchContext",
            return_value=subscription_match_manager,
        ),
    ):
        notify_info, follow_notify_info = manager.get_subscription_notify_info()

    assert notify_info == {}
    assert follow_notify_info == {"voice": [["subscriber"]]}


def test_invalid_subscription_rule_does_not_remove_default_receiver():
    manager = build_assignee_manager()
    manager.get_notify_info = mock.Mock(
        side_effect=lambda user_type=UserGroupType.MAIN: (
            {"mail": ["default_user"]} if user_type == UserGroupType.MAIN else {}
        )
    )
    manager.get_appointee_notify_info = mock.Mock(return_value={})
    subscription_match_manager = SimpleNamespace(
        dimensions={"alert.strategy_id": "123"},
        origin_severity=2,
    )
    invalid_rule = {"id": 1, "conditions": [{"method": "eq", "value": "123"}]}
    processor = CreateActionProcessor.__new__(CreateActionProcessor)
    processor.notice_type = ActionNoticeType.NORMAL

    with (
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_users_by_biz",
            return_value=["subscriber"],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_rules_by_user",
            return_value=[invalid_rule],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.BackendAlertMatchContext",
            return_value=subscription_match_manager,
        ),
    ):
        notify_info, follow_notify_info = processor.get_merged_notice_info(manager)

    assert notify_info == {"mail": ["default_user"]}
    assert follow_notify_info == {}


def test_subscription_context_failure_does_not_remove_default_receiver():
    manager = build_assignee_manager()
    manager.get_notify_info = mock.Mock(
        side_effect=lambda user_type=UserGroupType.MAIN: (
            {"mail": ["default_user"]} if user_type == UserGroupType.MAIN else {}
        )
    )
    manager.get_appointee_notify_info = mock.Mock(return_value={})
    processor = CreateActionProcessor.__new__(CreateActionProcessor)
    processor.notice_type = ActionNoticeType.NORMAL

    with (
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_users_by_biz",
            return_value=["subscriber"],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.BackendAlertMatchContext",
            side_effect=RuntimeError("context unavailable"),
        ),
    ):
        notify_info, follow_notify_info = processor.get_merged_notice_info(manager)

    assert notify_info == {"mail": ["default_user"]}
    assert follow_notify_info == {}


def test_any_main_rule_promotes_all_matched_channels_for_the_same_user():
    manager = build_assignee_manager()
    subscription_match_manager = SimpleNamespace(
        dimensions={"alert.strategy_id": "123"},
        origin_severity=2,
    )
    rules = [
        {"id": 1, "conditions": [], "notice_ways": ["mail"], "user_type": "main"},
        {"id": 2, "conditions": [], "notice_ways": ["sms"], "user_type": "follower"},
    ]

    with (
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_users_by_biz",
            return_value=["subscriber"],
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.SubscribeCacheManager.get_rules_by_user",
            return_value=rules,
        ),
        mock.patch(
            "alarm_backends.service.fta_action.tasks.alert_assign.BackendAlertMatchContext",
            return_value=subscription_match_manager,
        ),
    ):
        notify_info, follow_notify_info = manager.get_subscription_notify_info()

    assert notify_info == {"mail": ["subscriber"], "sms": ["subscriber"]}
    assert follow_notify_info == {}


def test_notice_relation_is_kept_for_subscription_only_strategy():
    notice = {
        "id": 9,
        "config_id": 1,
        "user_groups": [],
        "options": {"assign_mode": [AssignMode.ONLY_NOTICE]},
        "signal": [ActionSignal.ABNORMAL],
    }
    processor = CreateActionProcessor.__new__(CreateActionProcessor)
    processor.strategy = {"actions": [], "notice": notice}
    processor.strategy_id = 123
    processor.signal = ActionSignal.ABNORMAL
    processor.alerts = [SimpleNamespace(event=SimpleNamespace(bk_biz_id=2))]
    processor.generate_uuid = "generate-uuid"
    processor.notice_type = ActionNoticeType.NORMAL
    processor.relation_id = None
    processor.noise_reduce_result = False

    with (
        mock.patch(
            "alarm_backends.service.fta_action.tasks.create_action.SubscribeCacheManager.get_users_by_biz",
            return_value=["subscriber"],
        ) as get_users_by_biz,
        mock.patch(
            "alarm_backends.service.fta_action.tasks.create_action.NoiseReduceRecordProcessor"
        ) as noise_reduce_processor,
    ):
        actions = processor.get_action_relations()

    assert actions == [notice]
    get_users_by_biz.assert_not_called()
    noise_reduce_processor.assert_not_called()


def test_notice_relation_without_action_config_is_not_synthesized():
    processor = CreateActionProcessor.__new__(CreateActionProcessor)
    processor.strategy = {
        "actions": [],
        "notice": {
            "user_groups": [],
            "options": {"assign_mode": [AssignMode.ONLY_NOTICE]},
            "signal": [ActionSignal.ABNORMAL],
        },
    }
    processor.signal = ActionSignal.ABNORMAL
    processor.relation_id = None

    assert processor.get_action_relations() == []


def test_subscription_receivers_are_merged_without_default_or_assignment():
    processor = CreateActionProcessor.__new__(CreateActionProcessor)
    processor.notice_type = ActionNoticeType.NORMAL
    assignee_manager = mock.Mock()
    assignee_manager.get_notify_info.side_effect = lambda user_type=UserGroupType.MAIN: {}
    assignee_manager.get_appointee_notify_info.return_value = {}
    assignee_manager.get_subscription_notify_info.return_value = (
        {"mail": ["main_subscriber"]},
        {"mail": ["main_subscriber", "follower_subscriber"]},
    )

    notify_info, follow_notify_info = processor.get_merged_notice_info(assignee_manager)

    assert notify_info == {"mail": ["main_subscriber"]}
    assert follow_notify_info == {"mail": ["follower_subscriber"]}


def test_wxbot_mentions_alone_are_not_actual_notice_receivers():
    assert CreateActionProcessor.has_notice_receivers({"wxbot_mention_users": ["mention_user"]}) is False


def test_subscription_only_receiver_creates_notice_action_and_starts_noise_reduce():
    processor, alert, assignee_manager = build_create_action_case(({"mail": ["subscriber"]}, {}))
    noise_reduce_processor = run_create_action_case(processor)

    processor.do_create_action.assert_called_once()
    assert processor.do_create_action.call_args.kwargs["notice_info"] == ({"mail": ["subscriber"]}, {})
    assignee_manager.get_subscription_notify_info.assert_called_once()
    noise_reduce_processor.assert_called_once_with(
        processor.notice,
        processor.signal,
        processor.strategy_id,
        alert,
        processor.generate_uuid,
    )


def test_empty_final_receivers_skip_notice_action_and_noise_reduce():
    processor, _, _ = build_create_action_case(({}, {}))

    noise_reduce_processor = run_create_action_case(processor)

    processor.do_create_action.assert_not_called()
    noise_reduce_processor.assert_not_called()


def test_subscription_only_alert_without_receivers_keeps_original_early_return():
    processor, _, _ = build_create_action_case(({}, {}))
    processor.notice["options"]["assign_mode"] = [AssignMode.ONLY_NOTICE]

    run_create_action_case(processor)

    processor.do_create_action.assert_not_called()
    processor.update_alert_documents.assert_not_called()
    processor._process_issue_aggregation.assert_not_called()


def test_message_queue_does_not_mark_subscription_only_alert_without_receivers_as_notified():
    processor, _, _ = build_create_action_case(({}, {}))
    processor.notice["options"]["assign_mode"] = [AssignMode.ONLY_NOTICE]
    processor.create_message_queue_action.side_effect = lambda new_actions: new_actions.append(99)

    run_create_action_case(processor)

    processor.do_create_action.assert_not_called()
    processor.update_alert_documents.assert_not_called()
    processor._process_issue_aggregation.assert_not_called()


def test_configured_user_group_keeps_parent_notice_when_current_receivers_are_empty():
    processor, _, _ = build_create_action_case(({}, {}))
    processor.notice["user_groups"] = [1]

    noise_reduce_processor = run_create_action_case(processor)

    processor.do_create_action.assert_called_once()
    assert processor.do_create_action.call_args.kwargs["notice_info"] == ({}, {})
    noise_reduce_processor.assert_called_once()


def test_matched_assignment_keeps_parent_notice_when_current_receivers_are_empty():
    processor, _, assignee_manager = build_create_action_case(({}, {}))
    assignee_manager.is_matched = True

    noise_reduce_processor = run_create_action_case(processor)

    processor.do_create_action.assert_called_once()
    assert processor.do_create_action.call_args.kwargs["notice_info"] == ({}, {})
    noise_reduce_processor.assert_called_once()


def test_subscription_follower_is_recorded_without_assignment_match_manager():
    processor, _, assignee_manager = build_create_action_case(({}, {"mail": ["follower_subscriber"]}))

    run_create_action_case(processor)

    assert assignee_manager.match_manager is None
    assert mock.call(["follower_subscriber"], []) in processor.get_alert_related_users.call_args_list


def test_assignment_follower_robot_receivers_are_not_written_to_alert_followers():
    processor, _, assignee_manager = build_create_action_case(({}, {"mail": ["follower_subscriber"]}))
    assignee_manager.is_matched = True
    assignee_manager.get_assignees.side_effect = lambda by_group=False, user_type=UserGroupType.MAIN: (
        ["assigned_follower"] if user_type == UserGroupType.FOLLOWER else []
    )
    assignee_manager.get_notify_info.side_effect = lambda user_type=UserGroupType.MAIN: (
        {
            "mail": ["assigned_follower"],
            "wxwork-bot": ["robot_chat_id"],
            "bkchat|mail": ["bkchat_group_id"],
        }
        if user_type == UserGroupType.FOLLOWER
        else {}
    )
    processor.get_alert_related_users = mock.Mock(side_effect=CreateActionProcessor.get_alert_related_users)

    run_create_action_case(processor)

    alerts_follower = processor.update_alert_documents.call_args.args[5]
    assert alerts_follower == {"alert-id": ["assigned_follower", "follower_subscriber"]}


def test_non_notice_action_does_not_read_subscription_rules():
    processor, _, assignee_manager = build_create_action_case(({}, {}))

    noise_reduce_processor = run_create_action_case(processor, plugin_type="webhook")

    processor.do_create_action.assert_called_once()
    assignee_manager.get_subscription_notify_info.assert_not_called()
    noise_reduce_processor.assert_not_called()


def test_disabled_notice_action_does_not_read_subscription_rules():
    processor, _, assignee_manager = build_create_action_case(({}, {}))
    processor.is_action_config_valid.return_value = False

    noise_reduce_processor = run_create_action_case(processor)

    processor.do_create_action.assert_not_called()
    assignee_manager.get_subscription_notify_info.assert_not_called()
    noise_reduce_processor.assert_not_called()
