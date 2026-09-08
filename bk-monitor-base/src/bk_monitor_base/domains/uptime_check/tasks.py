"""
拨测任务相关的Celery异步任务
"""

import json
import logging
import time

from bkmonitor.nodeman_integration.backend import node_man_backend
from bkmonitor.nodeman_integration.exceptions import NodeManV3CapabilityBlocked

from bk_monitor_base.domains.space.cache import bk_biz_id_to_bk_tenant_id
from bk_monitor_base.domains.uptime_check.models import (
    UptimeCheckTaskCollectorLog,
    UptimeCheckTaskModel,
    UptimeCheckTaskSubscription,
)
from bk_monitor_base.infras.exception import BaseError as BKAPIError
from bk_monitor_base.infras.third_party_api.nodeman import api as node_man_v2_api

from .constants import CollectStatus
from .define import UptimeCheckTaskStatus

logger = logging.getLogger(__name__)


def check_single_task_status(bk_tenant_id: str, subscription_id: int) -> tuple[str, list[str], int]:
    """
    周期查询单个拨测任务启动状态

    Args:
        subscription_id: 订阅ID
        bk_tenant_id: 租户ID

    Returns:
        (状态, 错误日志列表, 节点管理任务ID)
    """
    if node_man_backend.is_v3:
        raise NodeManV3CapabilityBlocked(
            "legacy uptime subscription polling cannot interpret a NodeMan V3 binding; use refresh_task_status"
        )

    while True:
        time.sleep(3)
        error_count = 0
        try:
            status_result, _ = node_man_v2_api.batch_get_subscription_task_result(
                bk_tenant_id=bk_tenant_id, params={"subscription_id": subscription_id, "need_aggregate_all_tasks": True}
            )
        except BKAPIError as e:
            logger.error(f"请求节点管理任务{subscription_id}执行结果接口:batch_task_result失败: {e}")
            return UptimeCheckTaskStatus.STARTING.value, [], 0

        log: list[str] = []
        nodeman_task_id = 0

        if len(status_result) == 0:
            logger.info(f"celery period task: 订阅任务{subscription_id}正在启用中")
            logger.info(f"error_log: {log}")
            return UptimeCheckTaskStatus.STARTING.value, log, nodeman_task_id

        for item in status_result:
            if item["status"] in [CollectStatus.RUNNING, CollectStatus.PENDING]:
                break
            if item["status"] == CollectStatus.FAILED:
                error_count += 1
                result = node_man_v2_api.get_subscription_task_result_detail(
                    bk_tenant_id=bk_tenant_id,
                    subscription_id=subscription_id,
                    instance_id=item["instance_id"],
                )
                if result:
                    nodeman_task_id = int(result["task_id"]) if result.get("task_id") else 0
                    for step in result.get("steps", []):
                        if step["status"] == CollectStatus.FAILED:
                            for sub_step in step["target_hosts"][0].get("sub_steps", []):
                                if sub_step["ex_data"]:
                                    log.append(json.dumps(sub_step["ex_data"], ensure_ascii=False))
        else:
            if error_count == 0:
                logger.info(f"celery period task: 订阅任务{subscription_id}正在运行中")
                logger.info(f"error_log: {log}")
                return UptimeCheckTaskStatus.RUNNING.value, log, nodeman_task_id
            else:
                logger.info(f"celery period task: 订阅任务{subscription_id}启动失败")
                logger.info(f"error_log: {log}")
                return UptimeCheckTaskStatus.START_FAILED.value, log, nodeman_task_id


def update_task_running_status(task_id: int) -> None:
    """
    异步查询拨测任务启动状态，更新拨测任务列表中的运行状态
    """
    logger.info("start celery period task: update uptime check task running status")

    task = UptimeCheckTaskModel.objects.get(id=task_id)
    bk_biz_id = task.bk_biz_id
    bk_tenant_id = bk_biz_id_to_bk_tenant_id(bk_biz_id)

    if node_man_backend.is_v3:
        from bk_monitor_base.domains.uptime_check.operation import refresh_task_status

        refresh_task_status(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id, task_ids=[task_id])
        return

    subscriptions = UptimeCheckTaskSubscription.objects.filter(
        uptimecheck_id=task_id,
        node_man_backend="v2",
        is_deleted=False,
    )
    has_fail = False

    # 遍历所有订阅，获取全部的状态
    for subscription in subscriptions:
        status, log, nodeman_task_id = check_single_task_status(
            bk_tenant_id=bk_tenant_id, subscription_id=subscription.subscription_id
        )
        if status == UptimeCheckTaskStatus.START_FAILED.value:
            for item in log:
                UptimeCheckTaskCollectorLog.objects.create(
                    task_id=task.pk,
                    error_log=item,
                    subscription_id=subscription.subscription_id,
                    nodeman_task_id=nodeman_task_id,
                )
            has_fail = True

    # 存在失败则判定为全部失败
    if has_fail:
        task.status = UptimeCheckTaskStatus.START_FAILED.value
    else:
        task.status = UptimeCheckTaskStatus.RUNNING.value

    task.save()
