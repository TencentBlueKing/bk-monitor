#!/usr/bin/env python
"""
蓝鲸监控告警动作重试脚本
用于重试执行失败的 FTA Action

使用方法：
result = retry_action_ids([12345, 67890], skip_success=True, ignore_error=False)
print(result)
"""

from collections.abc import Iterable
from datetime import datetime

from alarm_backends.service.fta_action.utils import PushActionProcessor
from bkmonitor.documents import AlertDocument
from bkmonitor.models import ActionInstance
from constants.action import ActionPluginType, ActionStatus


def retry_action_ids(
    action_ids: Iterable[int | str], skip_success: bool = True, ignore_error: bool = False
) -> tuple[bool, dict]:
    """
    重试多个message_queue/webhook类型的action_id

    :param action_ids: 需要重试的action_id列表
    :param skip_success: 是否跳过已经成功的action，如果跳过，则不会重试已经成功的action
    :param ignore_error: 是否忽略异常的action，如果不忽略，当前任务将会直接失败，所有的action都不会被重试
    :return: 是否成功，重试结果
    {
        "success_action_ids": 已经成功的action_id列表
        "not_exist_action_ids": 不存在的action_id列表
        "not_webhook_action_ids": 不是webhook/message_queue类型的action_id列表
        "normal_action_ids": 需要重试的action_id列表
    }
    """
    action_origin_id_map: dict[int, int] = {}
    for action_id in action_ids:
        # 如果action_id是12位以上，则认为action_id是action_instance_document的id，需要去掉前面的时间戳
        if len(str(action_id)) > 12:
            action_origin_id_map[int(str(action_id)[10:])] = int(action_id)
        else:
            action_origin_id_map[int(action_id)] = int(action_id)

    # 获取ActionInstance
    action_instances = ActionInstance.objects.filter(id__in=list(action_origin_id_map.values()))
    exists_action_ids = {action_instance.id: action_instance for action_instance in action_instances}

    # 检查action_id是否存在及插件类型是否为webhook/message_queue
    normal_action_ids = []
    not_exist_action_ids = []
    not_webhook_action_ids = []
    success_action_ids = []
    for action_instance_id, origin_id in action_origin_id_map.items():
        # 检查action_id是否存在
        if action_instance_id not in exists_action_ids:
            not_exist_action_ids.append(origin_id)
            continue

        # 检查插件类型是否为webhook/message_queue
        action_instance = exists_action_ids[action_instance_id]
        if action_instance.action_plugin.get("plugin_type") not in [
            ActionPluginType.WEBHOOK,
            ActionPluginType.MESSAGE_QUEUE,
        ]:
            not_webhook_action_ids.append(origin_id)
            continue

        # 检查是否已经是成功状态
        if action_instance.status == ActionStatus.SUCCESS:
            success_action_ids.append(origin_id)
            # 如果skip_success为True，则跳过已经成功的action
            if skip_success:
                continue

        normal_action_ids.append(origin_id)

    if success_action_ids:
        print(f"[WARNING] Action {success_action_ids} is already success")

    # 如果存在异常的action_id，且skip_error为False，则直接返回
    if not_exist_action_ids:
        print(f"[ERROR] Action {not_exist_action_ids} not found")
    if not_webhook_action_ids:
        print(f"[ERROR] Action {not_webhook_action_ids} is not webhook/message_queue type")

    if (not_exist_action_ids or not_webhook_action_ids) and not ignore_error:
        return False, {
            "success_action_ids": success_action_ids,
            "not_exist_action_ids": not_exist_action_ids,
            "not_webhook_action_ids": not_webhook_action_ids,
            "normal_action_ids": normal_action_ids,
        }

    # 检查action_id是否存在
    for action_instance in action_instances:
        # 只处理normal_action_ids中的action_id
        if action_instance.id not in normal_action_ids:
            continue

        # 更新action_instance状态
        action_instance.status = ActionStatus.RETRYING
        action_instance.update_time = datetime.now()
        action_instance.save()

        alerts = AlertDocument.mget(ids=action_instance.alerts)
        PushActionProcessor.push_action_to_execute_queue(action_instance, alerts=alerts)
        print(f"[INFO] Pushed action {action_origin_id_map[action_instance.id]} to execute queue")

    return True, {
        "success_action_ids": success_action_ids,
        "not_exist_action_ids": not_exist_action_ids,
        "not_webhook_action_ids": not_webhook_action_ids,
        "normal_action_ids": normal_action_ids,
    }
