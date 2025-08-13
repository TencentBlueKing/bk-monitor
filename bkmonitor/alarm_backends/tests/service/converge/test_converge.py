import time
from unittest.mock import patch, MagicMock
import pytest

from alarm_backends.core.alert import Alert
from alarm_backends.service.fta_action.tasks.create_action import CreateActionProcessor
from alarm_backends.service.converge.processor import ConvergeProcessor
from bkmonitor.models.fta.action import ConvergeInstance, ConvergeRelation, ActionInstance, ActionPlugin
from bkmonitor.models.base import CacheRouter, CacheNode
from alarm_backends.service.scheduler.app import app

pytestmark = pytest.mark.django_db
NOW = int(time.time())

ONE_HOUR = 60 * 60

# 10小时之前
ten_hour_ago = NOW - ONE_HOUR * 10
# 5小时之前
five_hour_ago = NOW - ONE_HOUR * 5


def get_alert_dict():
    alert_dict = {
        "dedupe_md5": "632af25faf3bddc789c579f0961f0232",
        "create_time": 1745120417,
        "update_time": 1745121000,
        "begin_time": 1745120413,
        "latest_time": 1745120413,
        "first_anomaly_time": 1745120413,
        "severity": 2,
        "event": {
            "_related_instance_to_ignore": None,
            "id": "d440a16e31f70db8d7f6b3a518ed6b4f",
            "event_id": "0431b726bf65abbeab7c02c70194ab98.1745120413.10.10.2",
            "plugin_id": "bkmonitor",
            "strategy_id": 10,
            "alert_name": "OOM异常告警",
            "description": "发现OOM异常事件发生（进程:bk-monitor-work），共OOM次数1次, 信息:系统发生OOM异常事件",
            "severity": 2,
            "data_type": "event",
            "tags": [],
            "target_type": "HOST",
            "target": "127.0.0.1|0",
            "status": "ABNORMAL",
            "metric": ["bk_monitor.oom-gse"],
            "category": "os",
            "dedupe_keys": ["strategy_id", "target_type", "target", "bk_biz_id"],
            "dedupe_md5": "632af25faf3bddc789c579f0961f0232",
            "time": 1745120413,
            "anomaly_time": 1745120413,
            "bk_ingest_time": 1745120417,
            "bk_clean_time": 1745120417,
            "create_time": 1745120417,
            "bk_biz_id": 2,
            "ip": "127.0.0.1",
            "bk_cloud_id": 0,
            "bk_host_id": 3,
            "ipv6": "",
            "bk_topo_node": ["set|2", "biz|2", "module|3"],
            "extra_info": {},
        },
        "status": "ABNORMAL",
        "alert_name": "OOM异常告警",
        "strategy_id": 10,
        "dimensions": [
            {"display_value": "127.0.0.1", "display_key": "目标IP", "value": "127.0.0.1", "key": "ip"},
            {"display_value": 0, "display_key": "云区域ID", "value": 0, "key": "bk_cloud_id"},
        ],
        "extra_info": {
            "origin_alarm": {
                "trigger_time": 1745120417,
                "data": {
                    "time": 1745120413,
                    "value": "",
                    "values": {"time": 1745120413, "value": ""},
                    "dimensions": {
                        "bk_target_ip": "127.0.0.1",
                        "bk_target_cloud_id": 0,
                        "bk_host_id": 3,
                        "bk_topo_node": ["biz|2", "module|3", "set|2"],
                        "process": "bk-monitor-work",
                        "message": "系统发生OOM异常事件",
                        "oom_memcg": "/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod5821a63d_0b6b_46ab_821d_0312358c6548.slice",
                        "task_memcg": "/kubepods.slice/kubepods-burstable.slice/kubepods-burstable-pod5821a63d_0b6b_46ab_821d_0312358c6548.slice/docker-d11dec24bf722b8003edb122414bebd0f4f19fb31930fc2758dcae37a34d411b.scope",
                        "task": "bk-monitor-work",
                        "constraint": "CONSTRAINT_MEMCG",
                    },
                    "record_id": "0431b726bf65abbeab7c02c70194ab98.1745120413",
                    "dimension_fields": ["bk_target_ip", "bk_target_cloud_id"],
                },
                "trigger": {"level": "2", "anomaly_ids": ["0431b726bf65abbeab7c02c70194ab98.1745120413.10.10.2"]},
                "anomaly": {
                    "2": {
                        "anomaly_id": "0431b726bf65abbeab7c02c70194ab98.1745120413.10.10.2",
                        "anomaly_time": "2025-04-20 03:40:17",
                        "anomaly_message": "发现OOM异常事件发生（进程:bk-monitor-work），共OOM次数1次, 信息:系统发生OOM异常事件",
                    }
                },
                "dimension_translation": {},
                "strategy_snapshot_key": "bk_monitorv3.ce.cache.strategy.snapshot.10.1741003216",
            },
            "strategy": {
                "id": 10,
                "version": "v2",
                "bk_biz_id": 2,
                "name": "OOM异常告警",
                "source": "bk_monitorv3",
                "scenario": "os",
                "type": "monitor",
                "items": [],
                "detects": [],
                "actions": [],
                "notice": {},
                "is_enabled": True,
                "is_invalid": False,
                "invalid_type": "",
                "update_time": 1741003216,
                "update_user": "system",
                "create_time": 1741003216,
                "create_user": "system",
                "labels": [],
                "app": "",
                "path": "",
                "priority": None,
                "priority_group_key": "",
                "edit_allowed": True,
                "metric_type": "event",
            },
            "matched_rule_info": {
                "notice_upgrade_user_groups": [],
                "follow_groups": [],
                "notice_appointees": [],
                "itsm_actions": {},
                "severity": 0,
                "additional_tags": [],
                "rule_snaps": {},
                "group_info": {},
            },
            "cycle_handle_record": {
                "2": {
                    "execute_times": 1,
                    "is_shielded": False,
                    "last_time": 1745120417,
                    "latest_anomaly_time": 1745120413,
                }
            },
            "is_recovering": True,
            "end_description": "连续 5 个周期不满足触发条件，告警已关闭",
        },
        "is_blocked": False,
        "next_status_time": 1745124017,
        "next_status": "CLOSED",
        "id": "174512041721",
        "seq_id": 21,
        "duration": 60,
        "appointee": ["admin"],
        "is_shielded": False,
        "assignee": ["admin"],
        "is_handled": True,
        "handle_stage": ["handle"],
        "shield_left_time": 0,
        "end_time": 1745121000,
        "ack_duration": 583,
    }

    return alert_dict


def get_action() -> dict:
    action = {
        "id": 2,
        "config_id": 1002,
        "user_groups": [2],
        "user_type": "main",
        "signal": ["abnormal"],
        "options": {
            "end_time": "23:59:59",
            "start_time": "00:00:00",
            "converge_config": {
                "count": 1,
                "condition": [{"value": ["self"], "dimension": "action_info"}],
                "timedelta": 3600,
                "is_enabled": True,
                "converge_func": "skip_when_success",
                "need_biz_converge": True,
            },
            # "skip_delay": ONE_HOUR  # 显示一小时
        },
        "relate_type": "ACTION",
        "config": {
            "id": 1002,
            "is_enabled": True,
            "name": "agent_lose",
            "desc": "",
            "bk_biz_id": "2",
            "plugin_id": "2",
            "plugin_type": "webhook",
            "execute_config": {
                "template_detail": {
                    "need_poll": True,
                    "notify_interval": 7200,
                    "interval_notify_mode": "standard",
                    "method": "GET",
                    "url": "http://www.baidu.com",
                    "headers": [],
                    "authorize": {"auth_type": "none", "auth_config": {}},
                    "body": {"data_type": "default", "params": [], "content": "", "content_type": ""},
                    "query_params": [],
                    "failed_retry": {"is_enabled": True, "timeout": 10, "max_retry_times": 2, "retry_interval": 2},
                },
                "timeout": 600,
            },
        },
    }
    return action


@pytest.fixture(scope="module", autouse=True)
def reset_celery_config():
    origin_app_config = app.conf

    # 清除配置，并使用同步执行
    app.config_from_object({})
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    yield
    # 恢复原来的配置
    app.conf.update(origin_app_config)


@pytest.fixture(scope="function", autouse=True)
def prepare_database():
    ConvergeInstance.objects.all().delete()
    ActionInstance.objects.all().delete()
    ConvergeRelation.objects.all().delete()

    webhook_plugin = {
        "id": 2,
        "is_enabled": 1,
        "is_deleted": 0,
        "create_user": "",
        "update_user": "admin",
        "plugin_type": "webhook",
        "name": "HTTP回调",
        "is_builtin": 1,
        "is_peripheral": 0,
        "has_child": 0,
        "category": "",
        "config_schema": '{"content_template": "HTTP\\u56de\\u8c03\\u4efb\\u52a1\\u3010{{action_name}}\\u3011\\u5904\\u7406{{status_display}}"}',
        "backend_config": '[{"function": "execute_webhook", "name": "HTTP\\u56de\\u8c03"}]',
        "description": '告警回调是内置的套餐类型，由平台自身实现，可以将每次告警触发的内容通过GET/POST方式提交到目标地址，可以对告警内容进行二次消费。变量可以用于key的value和body内容。\n\n注意： 告警回调的内容不等于通知内容，是未做收敛的告警事件。\n\n完整的告警数据可通过变量 `{{alarm.callback_message}}` 进行引用。数据样例如下：\n\n```json\n{\n  "bk_biz_id": 2, // 业务ID\n  "bk_biz_name": "蓝鲸", // 业务名称\n  "current_value": "10", // 告警指标当前值\n "description": "告警已恢复，当前值为10ms", // 通知内容\n "latest_anomaly_record":{ // 最新异常点信息\n    "origin_alarm":{\n      "anomaly":{ // 异常信息\n        "1":{ // 告警级别\n          "anomaly_message":"avg(使用率) >= 0.0, 当前值46.17", // 异常消息\n          "anomaly_time":"2020-03-03 04:10:02", // 异常产生事件\n          "anomaly_id":"48af047a4251b9f49b7cdbc66579c23a.1583208540.999.999.1" // 异常数据ID\n        }\n      },\n      "data":{ // 数据信息\n        "record_id":"48af047a4251b9f49b7cdbc66579c23a.1583208540", // 数据ID\n        "values":{\t// 数据值\n          "usage":46.17,\n          "time":1583208540\n        },\n        "dimensions":{ // 数据维度\n          "bk_topo_node":[\n            "module|6"\n          ],\n          "bk_target_ip":"127。0。0。1",\n          "bk_target_cloud_id":"0"\n        },\n        "value":46.17,\t// 指标值\n        "time":1583208540 // 时间\n      }\n    },\n    "create_time":"2020-03-03 04:10:02", // 产生事件\n    "source_time":"2020-03-03 04:09:00", // 数据事件\n    "anomaly_id":6211913 // 异常ID\n  },\n  "type":"ANOMALY_NOTICE", // 通知类型 ANOMALY_NOTICE异常通知，RECOVERY_NOTICE恢复通知\n  "event":{ // 事件信息\n    "create_time":"2020-03-03 03:09:54", // 产生时间\n    "end_time":"2020-03-03 04:19:00", // 结束时间\n    "begin_time":"2020-03-03 03:08:00", // 开始时间\n    "event_id":"48af047a4251b9f49b7cdbc66579c23a.1583204880.999.999.1",\n    "level":1, // 告警级别\n    "level_name": "致命", // 级别名称\n    "id":8817 // 事件ID\n  },\n  "strategy":{\n        "item_list":[\n            {\n                "metric_field_name":"使用率", // 指标名称\n                "metric_field":"usage" // 指标\n            }\n        ],\n        "id":144, // 策略ID\n        "name":"测试策略" // 策略名称\n    }\n}\n```\n\n',
        "plugin_key": "webhook",
        "plugin_source": "builtin",
    }

    # 如果不存在，则创建
    ActionPlugin.objects.get_or_create(**webhook_plugin)

    cache_node = {
        "id": 1,
        "cache_type": "RedisCache",
        "host": "127.0.0.1",
        "port": 6379,
        "password": "aes_str:::UoOGW2Bf+NYpKZQF6qeF8QR1iBbUcSMeErbeSwWbe1Y=",
        "connection_kwargs": "{}",
        "is_enable": 1,
        "is_default": 1,
        "cluster_name": "default",
        "node_alias": "",
    }

    CacheNode.objects.get_or_create(**cache_node)

    cache_router = {"id": 1, "strategy_score": 1048577, "node_id": 1, "cluster_name": "default"}

    CacheRouter.objects.get_or_create(**cache_router)


@pytest.fixture()
def mock_get_action_config_by_id():
    with patch(
        "alarm_backends.core.cache.action_config.ActionConfigCacheManager.get_action_config_by_id"
    ) as get_action_config_by_id:
        get_action_config_by_id.return_value = get_action()["config"]
        yield get_action_config_by_id


@pytest.fixture()
def mock_mget():
    with patch("alarm_backends.core.alert.alert.Alert.mget") as mget:
        yield mget


@pytest.fixture()
def mock_alert_assign_handle():
    with (
        patch.object(CreateActionProcessor, "alert_assign_handle") as alert_assign_handle,
        patch.object(CreateActionProcessor, "get_alert_shield_result") as get_alert_shield_result,
        patch.object(CreateActionProcessor, "update_alert_documents"),
    ):
        mock_assign_handle = MagicMock()
        mock_assign_handle.is_matched = True
        mock_assign_handle.match_manager = False
        mock_assign_handle.get_supervisors.return_value = ["zhangsan"]
        mock_assign_handle.get_assignees.return_value = ["lisi"]
        mock_assign_handle.get_appointees.return_value = ["wangwu"]
        alert_assign_handle.return_value = mock_assign_handle

        get_alert_shield_result.return_value = (False, [])

        yield alert_assign_handle


@pytest.fixture()
def mock_push_converge_queue():
    with patch.object(ConvergeProcessor, "push_converge_queue") as push_converge_queue:
        yield push_converge_queue


@pytest.fixture()
def mock_push_to_action_queue():
    with patch.object(ConvergeProcessor, "push_to_action_queue") as push_to_action_queue:
        yield push_to_action_queue


class TestActionConverge:
    @classmethod
    def get_alert(cls, actions_mapping):
        alert_dict = get_alert_dict()
        handle_record = {
            "execute_times": 1,
            "is_shielded": False,
            "last_time": ten_hour_ago,
            "latest_anomaly_time": ten_hour_ago,
        }

        cycle_handle_record = {r: handle_record for r in list(actions_mapping.keys())}

        for _id, action in actions_mapping.items():
            action["id"] = int(_id)
            alert_dict["extra_info"]["strategy"]["actions"].append(action)

        alert_dict["extra_info"]["cycle_handle_record"] = cycle_handle_record

        update_params = {
            "create_time": ten_hour_ago,
            "begin_time": ten_hour_ago,
            "latest_time": five_hour_ago,
            "first_anomaly_time": ten_hour_ago,
        }

        update_event_params = {
            "create_time": ten_hour_ago,
            "anomaly_time": ten_hour_ago,
        }

        alert_dict.update(update_params)
        alert_dict["event"].update(update_event_params)

        return Alert(alert_dict)

    def test_action_converge_by_converge_config(
        self,
        mock_get_action_config_by_id,
        mock_mget,
        mock_alert_assign_handle,
        mock_push_to_action_queue,
        mock_push_converge_queue,
    ):
        actions_mapping = {"1": get_action(), "2": get_action()}

        alert = self.get_alert(actions_mapping)
        mock_mget.return_value = [alert]

        strategy = alert.strategy

        actions = []
        for action in alert.strategy["actions"]:
            params = {
                "strategy_id": strategy["id"],
                "signal": "abnormal",
                "alert_ids": [alert.id],
                "severity": alert.severity,
                "execute_times": alert.cycle_handle_record[str(action["id"])]["execute_times"],
                "relation_id": action["id"],
            }
            # 创建动作，并进行动作收敛
            action_ids = CreateActionProcessor(**params).do_create_actions()
            actions.extend(action_ids)

            # 确保没有执行第二次动作收敛操作
            mock_push_converge_queue.assert_not_called()
            if action["id"] == 1:
                # 第一次执行，动作不收敛，执行动作
                assert len(action_ids) == 1
                mock_push_to_action_queue.assert_called()
                # 更新动作状态为执行成功
                ActionInstance.objects.filter(id=action_ids[0]).update(status="success")
            else:
                # 第二次执行，动作收敛，不执行动作,所以还是上次执行过的那一次
                mock_push_to_action_queue.assert_called_once()

        assert len(actions) == len(actions_mapping)

    def test_action_converge_by_enable_delay(
        self,
        mock_get_action_config_by_id,
        mock_mget,
        mock_alert_assign_handle,
        mock_push_to_action_queue,
        mock_push_converge_queue,
    ):
        actions_mapping = {
            "1": get_action(),  # 创建action，并执行动作
            "2": get_action(),  # 不创建action，超时
            "3": get_action(),  # 创建action，超时，但信号错误，会成功执行动作
            "4": get_action(),  # 创建action,但是动作被收敛
            "5": get_action(),  # 创建action,但是动作被收敛
        }
        # 设置enable_delay时间限制为1小时
        actions_mapping["2"]["options"]["skip_delay"] = ONE_HOUR  # 设置为1小时，会超时
        actions_mapping["3"]["options"]["skip_delay"] = ONE_HOUR
        actions_mapping["3"]["signal"] = ["manual"]  # 设置错误的信号
        actions_mapping["4"]["options"]["skip_delay"] = ONE_HOUR * 20  # 设置为20小时，不会超时
        actions_mapping["5"]["signal"] = ["manual"]

        alert = self.get_alert(actions_mapping)
        mock_mget.return_value = [alert]

        strategy = alert.strategy

        actions = []
        execute_action_count = 0
        for action in alert.strategy["actions"]:
            params = {
                "strategy_id": strategy["id"],
                "signal": "abnormal",
                "alert_ids": [alert.id],
                "severity": alert.severity,
                "execute_times": alert.cycle_handle_record[str(action["id"])]["execute_times"],
                "relation_id": action["id"],
            }

            if action["id"] in [3, 5]:
                params["signal"] = "manual"
                alert.data["status"] = "MANUAL"  # 同步告警的状态，避免在判断enable_delay参数之前被过滤
            else:
                # 恢复为正确的状态
                alert.data["status"] = "ABNORMAL"

            # 创建动作，并进行动作收敛
            action_ids = CreateActionProcessor(**params).do_create_actions()
            actions.extend(action_ids)

            # 确保没有执行第二次动作收敛操作
            mock_push_converge_queue.assert_not_called()
            # action id 为1和3时，会执行动作
            if action["id"] in [1, 3]:
                assert len(action_ids) == 1
                execute_action_count += 1
                assert mock_push_to_action_queue.call_count == execute_action_count
                # 更新动作状态为执行成功
                ActionInstance.objects.filter(id=action_ids[0]).update(status="success")
            elif action["id"] in [4, 5]:
                assert mock_push_to_action_queue.call_count == 2

        # 创建了4个action，但成功执行的action只有两个
        assert len(actions) == 4
        assert execute_action_count == 2
