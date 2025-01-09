import time
from datetime import datetime, timedelta

import mock as _mock
import pytz
from django.conf import settings
from django.test import TestCase
from elasticsearch_dsl import AttrDict
from mock import MagicMock, patch

from alarm_backends.core.cache.key import ALERT_SNAPSHOT_KEY
from alarm_backends.service.converge.shield.shield_obj import ShieldObj
from alarm_backends.service.fta_action.message_queue.processor import (
    ActionProcessor as MessageQueueActionProcessor,
)
from alarm_backends.service.fta_action.tasks import (
    create_actions,
    sync_actions_sharding_task,
)
from alarm_backends.service.fta_action.tasks.create_action import CreateActionProcessor
from alarm_backends.tests.service.fta_action.test_notice_execute import (
    get_strategy_dict,
    register_builtin_plugins,
)
from bkmonitor.documents import ActionInstanceDocument, AlertDocument, EventDocument
from bkmonitor.models import ActionInstance, DutyPlan, UserGroup
from bkmonitor.utils import time_tools
from constants.action import ActionSignal, ActionStatus
from constants.alert import EventStatus

_mock.patch("alarm_backends.service.fta_action.tasks.run_webhook_action.apply_async", return_value=11111).start()
_mock.patch("alarm_backends.service.fta_action.tasks.run_action.apply_async", return_value=11111).start()


def clear_index():
    for doc in [AlertDocument, EventDocument, ActionInstanceDocument]:
        ilm = doc.get_lifecycle_manager()
        ilm.es_client.indices.delete(index=doc.Index.name)
        ilm.es_client.indices.create(index=doc.Index.name)


class TestActionFakeESProcessor(TestCase):
    def setUp(self) -> None:
        ALERT_SNAPSHOT_KEY.client.flushall()
        UserGroup.objects.all().delete()
        DutyPlan.objects.all().delete()
        ActionInstance.objects.all().delete()
        clear_index()
        settings.ENABLE_MESSAGE_QUEUE = False
        settings.MESSAGE_QUEUE_DSN = ""
        settings.ENABLE_PUSH_SHIELDED_ALERT = True

    def tearDown(self) -> None:
        ActionInstance.objects.all().delete()
        clear_index()
        settings.ENABLE_MESSAGE_QUEUE = False
        settings.MESSAGE_QUEUE_DSN = ""
        settings.ENABLE_PUSH_SHIELDED_ALERT = True

    def test_job_with_appointees(self):
        register_builtin_plugins()

        local_timezone = pytz.timezone("Asia/Shanghai")
        today_begin = time_tools.datetime2str(datetime.now(tz=local_timezone), "%Y-%m-%d 00:00")
        today_end = time_tools.datetime2str(datetime.now(tz=local_timezone), "%Y-%m-%d 23:59")
        duty_plans = [
            {
                "duty_rule_id": 1,
                "is_effective": 1,
                "start_time": time_tools.datetime2str(datetime.now(tz=local_timezone)),
                "finished_time": time_tools.datetime2str(datetime.now(tz=local_timezone) + timedelta(hours=1)),
                "work_times": [{'start_time': today_begin, 'end_time': today_end}],
                "order": 1,
                "users": [
                    {"id": "admin", "display_name": "admin", "logo": "", "type": "user"},
                    {"id": "operator", "display_name": "主机负责人", "logo": "", "type": "group"},
                ],
            },
            {
                "duty_rule_id": 1,
                "start_time": time_tools.datetime2str(datetime.now(tz=local_timezone)),
                "finished_time": time_tools.datetime2str(datetime.now(tz=local_timezone) + timedelta(hours=1)),
                "is_effective": 1,
                "order": 2,
                "work_times": [{'start_time': today_begin, 'end_time': today_end}],
                "users": [{"id": "lisa", "display_name": "xxxxx", "logo": "", "type": "user"}],
            },
        ]

        user_group_data = {
            "name": "蓝鲸业务的告警组-全职通知组",
            "desc": "用户组的说明用户组的说明用户组的说明用户组的说明用户组的说明",
            "bk_biz_id": 2,
            "need_duty": True,
            "duty_rules": [1],
            "alert_notice": [  # 告警通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式配置
                        {
                            "level": 3,  # 级别
                            "type": [  # 通知渠道列表
                                "mail",
                                "weixin",
                                "voice",
                            ],
                        },
                        {"level": 2, "type": ["mail", "voice"]},
                        {
                            "level": 1,
                            "type": ["mail", "weixin", "voice", "wxwork-bot"],
                            "chatid": "hihihihihh;hihihiashihi",
                        },
                    ],
                }
            ],
            "action_notice": [  # 执行通知配置
                {
                    "time_range": "00:00:00--23:59:59",  # 生效时间段
                    "notify_config": [  # 通知方式
                        {"phase": 3, "type": ["mail", "weixin", "voice"]},  # 执行阶段，3-执行前，2-成功时，1-失败时
                        {"phase": 2, "type": ["mail", "weixin", "voice"]},
                        {
                            "phase": 1,
                            "type": ["mail", "weixin", "voice", "wxwork-bot"],
                            "chatid": "hihihihihh;hihihiashihi",
                        },
                    ],
                }
            ],
        }
        group = UserGroup.objects.create(**user_group_data)
        for duty in duty_plans:
            duty.update({"user_group_id": group.id})
            DutyPlan.objects.create(**duty)

        job_config = {
            "execute_config": {
                "template_id": 1000043,
                "template_detail": {"1000005_3": "{{alert.event.ip}}", "1000004_1": "hello, {{alert.event.ip}}"},
                "timeout": 60,
            },
            "name": "uwork重启",
            "desc": "这是描述，这是描述",
            "is_enabled": True,
            "plugin_id": 3,
            "bk_biz_id": 2,
            "id": 4444,
        }

        strategy_dict = get_strategy_dict(group.id)
        event = EventDocument(
            **{
                "bk_biz_id": 2,
                "ip": "127.0.0.1",
                "time": int(time.time()),
                "create_time": int(time.time()),
                "bk_cloud_id": 0,
                "id": 123,
            }
        )
        current_time = int(time.time())
        alert_info = {
            "id": "1",
            "event": event,
            "severity": 1,
            "strategy_id": 1,
            "dedupe_md5": "68e9f0598d72a4b6de2675d491e5b922",
            "begin_time": int(time.time()),
            "create_time": int(time.time()),
            "latest_time": current_time,
            "first_anomaly_time": current_time,
            "duration": 60,
            "common_dimensions": {},
            "dimensions": [
                AttrDict({"key": "bk_target_ip", "value": "127.0.0.1"}),
                AttrDict({"key": "bk_target_cloud_id", "value": "2"}),
            ],
            "extra_info": {"strategy": {}},
            "status": EventStatus.ABNORMAL,
            "appointee": ["admin", "lisa"],
        }
        alert_info["extra_info"].update(strategy=strategy_dict)
        job_alert = AlertDocument(**alert_info)
        AlertDocument.bulk_create([job_alert])

        with patch(
            "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id",
            MagicMock(return_value=job_config),
        ):
            actions = create_actions(1, "abnormal", alerts=[job_alert])
            self.assertEqual(len(actions), 1)

            # assignee一定是一个有序的列表
            self.assertEqual(["admin", "lisa"], ActionInstance.objects.get(id=actions[0]).assignee)

    def test_shield_config_dimension_match_and(self):
        config = {
            "id": 1,
            "category": "dimension",
            "cycle_config": {},
            "begin_time": datetime.now(),
            "end_time": datetime.now() + timedelta(days=1),
            "dimension_config": {
                "dimension_conditions": [
                    {"key": "ip", "value": "127.0.0.1", "method": "eq"},
                    {"key": "ip", "value": "127.0.0.2", "method": "eq", "condition": "or"},
                    {"key": "name", "value": "test", "method": "eq", "condition": "and"},
                ]
            },
        }

        s = ShieldObj(config)
        assert s.dimension_check.is_match({"ip": "127.0.0.1"}) is True
        assert s.dimension_check.is_match({"ip": "127.0.0.2", "name": "test"}) is True
        assert s.dimension_check.is_match({"ip": "127.0.0.3", "name": "test"}) is False

    def test_shield_config_dimension_match_or(self):
        config = {
            "id": 1,
            "category": "dimension",
            "cycle_config": {},
            "begin_time": datetime.now(),
            "end_time": datetime.now() + timedelta(days=1),
            "dimension_config": {
                "dimension_conditions": [
                    {"key": "ip", "value": "127.0.0.1", "method": "eq", "condition": "or"},
                    {"key": "ip", "value": "127.0.0.2", "method": "eq", "condition": "or"},
                    {"key": "name", "value": "test", "method": "eq", "condition": "and"},
                ]
            },
        }

        s = ShieldObj(config)
        assert s.dimension_check.is_match({"ip": "127.0.0.1"}) is True
        assert s.dimension_check.is_match({"ip": "127.0.0.2", "name": "test"}) is True
        assert s.dimension_check.is_match({"ip": "127.0.0.3", "name": "test"}) is False

    def test_send_message_queue_shield_true(self):
        alert_info = {"id": str(int(time.time() * 1000)), "event": EventDocument(bk_biz_id=2), "is_shielded": True}
        alerts = [AlertDocument(**alert_info)]
        AlertDocument.bulk_create(alerts)
        p = CreateActionProcessor(strategy_id=0, signal="abnormal", alerts=alerts, severity=1)

        settings.ENABLE_MESSAGE_QUEUE = True
        settings.MESSAGE_QUEUE_DSN = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0/fta_message_queue"
        new_actions = []
        p.is_alert_shielded = True
        p.create_message_queue_action(new_actions)
        self.assertEqual(len(new_actions), 1)
        settings.ENABLE_PUSH_SHIELDED_ALERT = False
        processor = MessageQueueActionProcessor(action_id=new_actions[0])
        processor.execute()
        processor.action.refresh_from_db()
        self.assertEqual(processor.action.status, ActionStatus.FAILURE)

    def test_send_message_queue_shield_false(self):
        alert_info = {"id": str(int(time.time() * 1000)), "event": EventDocument(bk_biz_id=2)}
        alerts = [AlertDocument(**alert_info)]
        AlertDocument.bulk_create(alerts)
        p = CreateActionProcessor(strategy_id=0, signal="abnormal", alerts=alerts, severity=1)
        settings.ENABLE_PUSH_SHIELDED_ALERT = False
        settings.ENABLE_MESSAGE_QUEUE = True
        settings.MESSAGE_QUEUE_DSN = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0/fta_message_queue"
        new_actions = []
        p.is_alert_shielded = True
        p.create_message_queue_action(new_actions)
        self.assertEqual(p.is_alert_shielded, True)
        self.assertEqual(len(new_actions), 0)

    def test_sync_parent_action(self):
        alert_info = {"id": str(int(time.time() * 1000)), "event": EventDocument(bk_biz_id=2), "is_shielded": True}
        alerts = [AlertDocument(**alert_info)]
        AlertDocument.bulk_create(alerts)
        p_action = ActionInstance.objects.create(
            alerts=[alert_info["id"]],
            signal=ActionSignal.ABNORMAL,
            strategy_id=1,
            alert_level=1,
            bk_biz_id=2,
            dimensions=[],
            action_plugin={"plugin_type": "notice"},
            action_config={"plugin_type": "notice"},
            is_parent_action=True,
            status=ActionStatus.SUCCESS,
        )
        action_ids = []
        for i in range(0, 10):
            a = ActionInstance.objects.create(
                alerts=[alert_info["id"]],
                signal=ActionSignal.ABNORMAL,
                strategy_id=1,
                alert_level=1,
                bk_biz_id=2,
                dimensions=[],
                action_plugin={"plugin_type": "notice"},
                parent_action_id=p_action.id,
                status=ActionStatus.FAILURE,
                real_status=ActionStatus.FAILURE,
                action_config={"plugin_type": "notice"},
            )
            action_ids.append(a.id)

        sync_actions_sharding_task(action_ids)

        # 都是失败的时候，最后显示为失败
        p_doc = ActionInstanceDocument.get(id=p_action.es_action_id)
        self.assertEqual(p_doc.status, ActionStatus.FAILURE)

        last_a = ActionInstance.objects.create(
            alerts=[alert_info["id"]],
            signal=ActionSignal.ABNORMAL,
            strategy_id=1,
            alert_level=1,
            bk_biz_id=2,
            dimensions=[],
            action_plugin={"plugin_type": "notice"},
            parent_action_id=p_action.id,
            status=ActionStatus.SUCCESS,
            real_status=ActionStatus.SUCCESS,
            action_config={"plugin_type": "notice"},
        )

        # 当有一个是成功的时候，其他都是失败的时候，最后显示为部分失败
        sync_actions_sharding_task([last_a.id])
        p_doc = ActionInstanceDocument.get(id=p_action.es_action_id)
        self.assertEqual(p_doc.status, ActionStatus.PARTIAL_FAILURE)

        ActionInstance.objects.filter(parent_action_id=p_action.id).update(real_status=ActionStatus.SUCCESS)

        # 当所有子任务状态都是成功的时候， 先同步主任务
        sync_actions_sharding_task([p_action.id])
        p_doc = ActionInstanceDocument.get(id=p_action.es_action_id)
        self.assertEqual(p_doc.status, ActionStatus.SUCCESS)

        # 再同步所有的子任务，此时不会更改主任务状态
        sync_actions_sharding_task([last_a.id])
        p_doc = ActionInstanceDocument.get(id=p_action.es_action_id)
        self.assertEqual(p_doc.status, ActionStatus.SUCCESS)
