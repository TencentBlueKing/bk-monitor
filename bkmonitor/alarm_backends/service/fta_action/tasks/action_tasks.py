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

import importlib
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from celery.task import task
from django.db.models import Q
from django.utils.translation import ugettext as _

from alarm_backends.constants import CONST_MINUTES
from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.core.cache.key import (
    DEMO_ACTION_KEY_LOCK,
    LATEST_TIME_OF_SYNC_ACTION_KEY,
    SYNC_ACTION_LOCK_KEY,
    TIMEOUT_ACTION_KEY_LOCK,
)
from alarm_backends.core.lock.service_lock import service_lock
from alarm_backends.service.fta_action import (
    ActionAlreadyFinishedError,
    BaseActionProcessor,
)
from alarm_backends.service.fta_action.utils import (
    DutyCalendar,
    PushActionProcessor,
    to_document,
)
from alarm_backends.service.scheduler.tasks import perform_sharding_task
from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.models import ActionInstance, ConvergeRelation
from bkmonitor.models.strategy import DutyArrange, DutyArrangeSnap, DutyPlan, UserGroup
from bkmonitor.utils import time_tools
from bkmonitor.utils.common_utils import count_md5
from constants.action import ActionSignal, ActionStatus, ConvergeType, FailureType
from core.errors.alarm_backends import LockError
from core.prometheus import metrics

logger = logging.getLogger("fta_action.run")


@task(ignore_result=True, queue="celery_running_action")
def run_action(action_type, action_info):
    """
    自愈动作的执行入口函数
    :param action_type: 处理动作类型
    :param action_info: 处理动作信息，包含事件ID，处理函数，以及对应的回调参数
                        如：
                        {"id":1,
                         "function": "callback",
                         "kwargs":{"inputs": "xxx"}}
    :return:
    """
    # import action's call function
    module_name = "alarm_backends.service.fta_action.%s.processor" % action_type or action_info.get("module")
    logger.info("$%s Action start, call back module name %s", action_info["id"], module_name)
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        logger.error("import module %s error %s", module_name, error)
        ActionInstance.objects.filter(id=action_info["id"]).update(
            status=ActionStatus.FAILURE, failure_type=FailureType.FRAMEWORK_CODE, end_time=datetime.now(timezone.utc)
        )
        return

    exc = None
    action_instance = None
    alert = None
    processor = None
    func_name = ""
    is_finished = False
    start_time = time.time()
    try:
        processor: BaseActionProcessor = module.ActionProcessor(action_info["id"], alerts=action_info.get("alerts"))
        # 如果带了执行函数，则执行执行函数，没有的话，直接做执行操作
        func_name = action_info.get("function", "execute")
        func = getattr(processor, func_name)
        # call func
        logger.info("$%s Action callback: module name %s function %s", action_info["id"], module_name, func_name)
        func(**action_info.get("kwargs", {}))
    except ActionAlreadyFinishedError as error:
        logger.info("action(%s) already finished: %s", action_info["id"], str(error))
    except LockError as error:
        logger.info("action(%s) get execute lock error: %s", action_info["id"], str(error))
    except BaseException as error:  # NOCC:broad-except(设计如此:)
        logger.exception("execute action(%s) error, %s", action_info["id"], str(error))
        ActionInstance.objects.filter(id=action_info["id"]).update(
            status=ActionStatus.FAILURE,
            failure_type=FailureType.FRAMEWORK_CODE,
            end_time=datetime.now(timezone.utc),
            ex_data={"message": str(error)},
        )
        is_finished = True
        exc = error

    if processor:
        if getattr(processor, "is_finished", True):
            is_finished = True
            logger.info("$%s Action %s finished", action_info["id"], func_name)
        else:
            logger.info("$%s Action %s not finished: wait for callback", action_info["id"], func_name)
        try:
            action_instance = processor.action
            alert = processor.context.get("alert")
        except BaseException as error:
            logger.exception("$%s(%s) get action context failed: %s", action_info["id"], func_name, str(error))

    labels = {
        "bk_biz_id": action_instance.bk_biz_id if action_instance else 0,
        "plugin_type": action_type,
        "strategy_id": metrics.TOTAL_TAG,
        "signal": action_instance.signal if action_instance else "",
    }

    metrics.ACTION_EXECUTE_TIME.labels(**labels).observe(time.time() - start_time)
    metrics.ACTION_EXECUTE_COUNT.labels(status=metrics.StatusEnum.from_exc(exc), exception=exc, **labels).inc()
    if is_finished and action_instance:
        # 结束之后统计任务的执行情况
        status_labels = {
            "status": metrics.StatusEnum.FAILED
            if action_instance.status == ActionStatus.FAILURE
            else metrics.StatusEnum.SUCCESS,
            "failure_type": action_instance.failure_type,
        }
        status_labels.update(labels)
        metrics.ACTION_EXECUTE_STATUS_COUNT.labels(**status_labels).inc()

    if (
        action_info.get("function", "execute") == "execute"
        and action_instance
        and action_instance.is_first_process
        and alert
    ):
        # 第一次执行才统计处理延迟,且以执行结果来实现
        # 所有的通知处理中，仅支持普通通知的到达记录即可，解除屏蔽和升级告警不算
        latency = int(time.time()) - alert.create_time
        if latency > 10 * CONST_MINUTES:
            # 这里有部分异常数据，如果超过了5分钟的延迟，打印一下异常日志
            logger.warning(
                "long execute action latency find for alert(%s), current action(%s)", alert.id, action_instance.id
            )
        metrics.ACTION_EXECUTE_LATENCY.labels(**labels).observe(latency)

    metrics.report_all()


@task(ignore_result=True, queue="celery_webhook_action")
def run_webhook_action(action_type, action_info):
    """
    支持webhook回调和队列回调的任务
    :param action_type:
    :param action_info:
    :return:
    """
    run_action(action_type, action_info)


def sync_action_instances():
    """
    同步处理记录至ES
    :return:
    """
    for interval in range(0, 6):
        sync_action_instances_every_10_secs.apply_async(countdown=interval * 10, expires=120)


@task(ignore_result=True, queue="celery_action_cron")
def sync_action_instances_every_10_secs(last_sync_time=None):
    """
    每隔十秒同步任务
    :param last_sync_time:
    :return:
    """
    try:
        with service_lock(SYNC_ACTION_LOCK_KEY):
            current_sync_time = datetime.now(timezone.utc)
            redis_client = LATEST_TIME_OF_SYNC_ACTION_KEY.client
            cache_key = LATEST_TIME_OF_SYNC_ACTION_KEY.get_key()
            try:
                last_sync_time = int(redis_client.get(cache_key))
            except (ValueError, TypeError):
                # 如果获取缓存记录异常，表示要全库更新或者指定变量，这种可能性很小，但是无法保证redis一直正常运行
                three_days_ago = current_sync_time - timedelta(days=3)
                last_sync_time = last_sync_time or int(three_days_ago.timestamp())

            # 同步逻辑： 如果不存在最近更新时间的缓存key， 直接更新全表， 如果有，则更新对应时间范围内的数据即可
            # 汇总并且处于休眠期的内容不做同步
            # 刚接收到的处理记录也不做同步
            # demo任务也不同步到ES库
            updated_action_instances = ActionInstance.objects.filter(update_time__lte=current_sync_time)

            if last_sync_time:
                # 同步的时候，默认用5分钟之前的数据
                last_sync_time -= 5 * CONST_MINUTES
                updated_action_instances = updated_action_instances.filter(
                    update_time__gte=datetime.fromtimestamp(last_sync_time)
                )

            updated_action_instances = updated_action_instances.filter(
                Q(signal__in=ActionSignal.NORMAL_SIGNAL, status__in=ActionStatus.CAN_SYNC_STATUS)
                | Q(signal=ActionSignal.COLLECT, status__in=ActionStatus.COLLECT_SYNC_STATUS)
            ).order_by("update_time")

            logger.info("start sync_action_instances from time %s", last_sync_time)

            perform_sharding_task(
                updated_action_instances.values_list("id", flat=True), sync_actions_sharding_task, num_per_task=200
            )
            redis_client.set(cache_key, int(current_sync_time.timestamp()))
    except LockError:
        # 加锁失败
        logger.info("[get service lock fail] sync_action_instances_every_10_secs. will process later")
        return
    except BaseException as e:  # NOCC:broad-except(设计如此:)
        logger.exception("[process error] sync_action_instances_every_10_secs, reason：{msg}".format(msg=str(e)))
        return


@task(ignore_result=True, queue="celery_action_cron")
def sync_actions_sharding_task(action_ids):
    """
    分片任务同步信息，避免一次任务量太大
    :param action_ids:
    :return:
    """
    action_documents = []
    current_sync_time = datetime.now(timezone.utc)
    converge_relations = {
        item["related_id"]: item
        for item in ConvergeRelation.objects.filter(related_id__in=action_ids, related_type=ConvergeType.ACTION).values(
            "converge_id", "related_id", "converge_status", "is_primary"
        )
    }
    all_actions = []
    all_alerts = []
    for instance in ActionInstance.objects.filter(id__in=action_ids):
        all_alerts.extend(instance.alerts)
        all_actions.append(instance)
    all_alert_docs = {alert.id: alert for alert in AlertDocument.mget(ids=all_alerts)}
    # 记录需要更新的主任务
    updated_parent_actions = {}
    for instance in all_actions:
        instance.converge_info = converge_relations.get(instance.id, {})
        if not instance.action_config:
            continue
        if instance.parent_action_id and instance.real_status not in ActionStatus.IGNORE_STATUS:
            updated_parent_actions.update({instance.parent_action_id: instance.generate_uuid})
        try:
            alert_doc = all_alert_docs.get(instance.alerts[0]) if instance.alerts else None
            action_documents.append(to_document(instance, current_sync_time, alerts=[alert_doc] if alert_doc else None))
        except BaseException as error:  # NOCC:broad-except(设计如此:)
            logger.exception(
                "sync action error: %s , action_info %s",
                error,
                "{}{}".format(instance.id, instance.action_config.get("name", "")),
            )
    ActionInstanceDocument.bulk_create(action_documents, action=BulkActionType.INDEX)

    # 涉及到相关的主任务也进行一次同步
    sync_updated_parent_actions(updated_parent_actions, all_alert_docs, current_sync_time)


def sync_updated_parent_actions(updated_parent_actions, alert_docs, current_sync_time):
    """
    同步需要更新的主任务状态
    """
    if not updated_parent_actions:
        return
    failed_actions = []
    partial_failed_actions = []
    all_sub_actions = ActionInstance.objects.filter(
        generate_uuid__in=list(updated_parent_actions.values()),
        parent_action_id__in=list(updated_parent_actions.keys()),
    ).values("status", "id", "real_status", "parent_action_id")
    sub_action_status = defaultdict(list)
    for sub_action in all_sub_actions:
        action_status = sub_action["real_status"] or sub_action["status"]
        sub_action_status[sub_action["parent_action_id"]].append(action_status)
    action_documents = []
    for parent_action_id, sub_action_status in sub_action_status.items():
        priority_status = set(sub_action_status) - ActionStatus.IGNORE_STATUS
        # 一般成功状态下，是不需要更新的，因为主任务一般是成功状态
        if priority_status == {ActionStatus.FAILURE}:
            # 子任务完全失败，默认为失败
            failed_actions.append(parent_action_id)
        elif ActionStatus.FAILURE in priority_status:
            # 存在有失败情况下（夹杂着其他状态）
            partial_failed_actions.append(parent_action_id)
    updated_actions = failed_actions + partial_failed_actions
    for instance in ActionInstance.objects.filter(id__in=updated_actions):
        try:
            alert_doc = alert_docs.get(instance.alerts[0]) if instance.alerts else None
            # 同步的时候直接在ES同步的时候更新, 不再进行mysql的更新
            if instance.id in failed_actions:
                instance.status = ActionStatus.FAILURE
            if instance.id in partial_failed_actions:
                instance.status = ActionStatus.PARTIAL_FAILURE
            action_documents.append(to_document(instance, current_sync_time, alerts=[alert_doc] if alert_doc else None))
        except BaseException as error:  # NOCC:broad-except(设计如此:)
            logger.exception(
                "sync action error: %s , action_info %s",
                error,
                "{}{}".format(instance.id, instance.action_config.get("name", "")),
            )
    ActionInstanceDocument.bulk_create(action_documents, action=BulkActionType.INDEX)


def check_timeout_actions():
    """
    清除最近3天内的超时任务
    """
    three_days_ago = datetime.now(tz=timezone.utc) - timedelta(days=3)
    try:
        with service_lock(TIMEOUT_ACTION_KEY_LOCK):
            ten_minutes_ago = datetime.now(tz=timezone.utc) - timedelta(minutes=10)
            running_actions = (
                ActionInstance.objects.filter(
                    status__in=ActionStatus.PROCEED_STATUS,
                    create_time__lt=ten_minutes_ago,
                    create_time__gte=three_days_ago,
                )
                .only("status", "id", "action_config_id", "create_time")
                .order_by("create_time")
            )
            timeout_actions = []
            for running_action in running_actions:
                action_config = ActionConfigCacheManager.get_action_config_by_id(running_action.action_config_id)
                timeout_setting = action_config.get("execute_config", {}).get("timeout", 0)
                if running_action.status == ActionStatus.WAITING:
                    timeout_setting = 30 * CONST_MINUTES
                timeout_timestamp = (ten_minutes_ago - timedelta(seconds=timeout_setting)).timestamp()
                if int(timeout_timestamp) >= int(running_action.create_time.timestamp()):
                    timeout_actions.append(running_action.id)
            if timeout_actions:
                ActionInstance.objects.filter(id__in=timeout_actions).update(
                    end_time=datetime.now(tz=timezone.utc),
                    update_time=datetime.now(tz=timezone.utc),
                    status=ActionStatus.FAILURE,
                    failure_type=FailureType.TIMEOUT,
                    ex_data=dict(message=_("处理执行时间超过套餐配置的最大时长{}分钟, 按失败处理").format(timeout_setting // 60 or 10)),
                )
                logger.info("setting actions(%s) to failure because of timeout", len(timeout_actions))
    except LockError:
        # 加锁失败
        logger.info("[get service lock fail] check timeout action. will process later")
        return
    except BaseException as e:  # NOCC:broad-except(设计如此:)
        logger.exception("[process error] check timeout action, reason：{msg}".format(msg=str(e)))
        return


@task(ignore_result=True, queue="celery_action_cron")
def execute_demo_actions():
    """
    从DB获取调试任务推送到执行任务队列
    :return:
    """
    try:
        with service_lock(DEMO_ACTION_KEY_LOCK):
            demo_actions = ActionInstance.objects.filter(status=ActionStatus.RECEIVED, signal=ActionSignal.DEMO)
            for demo_action in demo_actions:
                PushActionProcessor.push_action_to_execute_queue(demo_action)
    except LockError:
        # 加锁失败，重新发布任务
        logger.info("[get service lock fail] run demo action. will process later")
        return
    except BaseException as e:  # NOCC:broad-except(设计如此:)
        logger.exception("[process error] run demo action, reason：{msg}".format(msg=str(e)))  # NOCC:broad-except(设计如此:)
        return


def dispatch_demo_action_tasks():
    """
    分发demo任务, 每隔10s钟进行一次任务执行
    :return:
    """
    for interval in range(0, 6):
        execute_demo_actions.apply_async(countdown=interval * 10, expires=120)


def clear_mysql_action_data(days=7, count=5000):
    """
    定期清理 MySQL 中的处理记录数据
    :return:
    """
    expire_datetime = datetime.now(timezone.utc) - timedelta(days=days)

    first_item = ActionInstance.objects.order_by("id").first()
    if not first_item:
        return

    del_count, _ = (
        ActionInstance.objects.filter(id__lt=first_item.id + count, create_time__lte=expire_datetime)
        .only("id")
        .delete()
    )

    logger.info(
        "[clear_mysql_action_data] from ActionInstance(%s), time(%s => %s), delete_count(%s)",
        first_item.id,
        first_item.create_time,
        expire_datetime,
        del_count,
    )


def generate_duty_plan_task():
    """
    生成值班周期任务
    :return:
    """
    current_time = datetime.now(tz=timezone.utc)
    current_time = (
        current_time - timedelta(seconds=current_time.second) - timedelta(microseconds=current_time.microsecond)
    )
    task_time = current_time + timedelta(minutes=1)
    logger.info(
        "[generate_duty_plan_task]generate_duty_plan_task for current_time(%s)", time_tools.localtime(task_time)
    )
    # 当前计算上一分钟之内应该生效的内容
    manage_duty_arrange_snap.delay(task_time)

    # 针对最近一小时内删除的轮值信息进行更新，缩小查找范围
    deleted_duties = list(
        DutyArrange.origin_objects.filter(
            is_deleted=True, update_time__gte=current_time - timedelta(hours=1)
        ).values_list("id", flat=True)
    )
    logger.info(
        "[delete_duty_plan_task]delete duty snap and plan from current_time(%s)， deleted arranges(%s)",
        time_tools.localtime(task_time),
        len(deleted_duties),
    )
    if deleted_duties:
        DutyArrangeSnap.objects.filter(duty_arrange_id__in=deleted_duties, is_active=True).update(is_active=False)
        DutyPlan.objects.filter(duty_arrange_id__in=deleted_duties, is_active=True).update(is_active=False)


@task(ignore_result=True, queue="celery_action_cron")
def manage_duty_arrange_snap(task_time, is_delay=True):
    """
    :param is_delay:
    :param task_time:
    :return:
    """
    new_duty_snaps = {}
    logger.info(
        "[manage_duty_arrange_snap] begin to manage duty snap for current_time(%s)", time_tools.localtime(task_time)
    )
    current_time = datetime.now(tz=timezone.utc)
    current_time = (
        current_time - timedelta(seconds=current_time.second) - timedelta(microseconds=current_time.microsecond)
    )
    task_time = max(current_time, task_time)
    duty_groups = UserGroup.objects.filter(need_duty=True).values_list("id", flat=True)
    for duty_arrange in DutyArrange.objects.filter(effective_time__lte=task_time, user_group_id__in=duty_groups):
        effective_time = max(duty_arrange.effective_time, current_time)
        new_duty_snaps.update(
            {
                duty_arrange.id: DutyArrangeSnap(
                    is_active=True,
                    next_plan_time=effective_time,
                    first_effective_time=effective_time,
                    duty_arrange_id=duty_arrange.id,
                    user_group_id=duty_arrange.user_group_id,
                    duty_snap=dict(
                        order=duty_arrange.order,
                        duty_time=duty_arrange.duty_time,
                        duty_users=duty_arrange.duty_users,
                        users=duty_arrange.users,
                        handoff_time=duty_arrange.handoff_time,
                        need_rotation=duty_arrange.need_rotation,
                    ),
                )
            }
        )
    no_change_duty_arrange_ids = []
    duty_arrange_ids = set(new_duty_snaps.keys())
    for duty_snap in DutyArrangeSnap.objects.filter(duty_arrange_id__in=new_duty_snaps.keys(), is_active=True):
        new_snap = new_duty_snaps[duty_snap.duty_arrange_id].duty_snap
        new_order = new_snap.pop("order", None)
        duty_snap.duty_snap.pop("order", None)
        if count_md5(new_snap, list_sort=False) == count_md5(duty_snap.duty_snap, list_sort=False):
            # 如果没有发生任何变化，不做改动
            no_change_duty_arrange_ids.append(duty_snap.duty_arrange_id)
        new_snap["order"] = new_order
    duty_arrange_ids = set(duty_arrange_ids).difference(set(no_change_duty_arrange_ids))

    if duty_arrange_ids:
        logger.info(
            "[manage_duty_arrange_snap] delete history duty arrange plan for %s",
            ",".join([str(item) for item in duty_arrange_ids]),
        )
        # 删除掉需要更改的的快照
        DutyArrangeSnap.objects.filter(duty_arrange_id__in=duty_arrange_ids).delete()
        DutyArrangeSnap.objects.bulk_create([new_duty_snaps[duty_id] for duty_id in duty_arrange_ids])

    duty_snaps = DutyArrangeSnap.objects.filter(next_plan_time__lte=task_time, is_active=True).values(
        "id", "duty_arrange_id"
    )
    duty_snap_ids = [snap["id"] for snap in duty_snaps]

    if is_delay is False:
        return

    for snap_id in duty_snap_ids:
        # 生成新的任务
        manage_duty_arrange_plan.delay(current_time, snap_id)

    logger.info(
        "[manage_duty_arrange_snap] begin to manage duty snap for current_time(%s)", time_tools.localtime(task_time)
    )


@task(ignore_result=True, queue="celery_action_cron")
def manage_duty_arrange_plan(current_time, snap_id):
    # step 1 当前分组的原计划都设置为False
    logger.info("[manage_duty_arrange_plan] begin to manage duty plan for snap(%s)", snap_id)
    try:
        duty_arrange_snap = DutyArrangeSnap.objects.get(id=snap_id, is_active=True)
    except DutyArrangeSnap.DoesNotExist:
        logger.warning("[manage_duty_arrange_plan] duty snap(%s) not existed", snap_id)
        return

    try:
        duty_arrange = DutyArrange.objects.get(id=duty_arrange_snap.duty_arrange_id)
    except DutyArrange.DoesNotExist:
        # 如果不存在，则表示已经删除
        logger.warning(
            "[manage_duty_arrange_plan] duty arrange(%s|%s) not existed", duty_arrange_snap.duty_arrange_id, snap_id
        )
        DutyPlan.objects.filter(duty_arrange_id=duty_arrange_snap.duty_arrange_id, is_active=True).update(
            is_active=False
        )
        duty_arrange_snap.is_active = False
        duty_arrange_snap.save()
        return

    # step 2 根据当前的轮值模式生成新的计划
    duty_snap = duty_arrange_snap.duty_snap
    duty_plans = []
    handoff_time = duty_snap["handoff_time"]
    begin_time = max(current_time, duty_arrange_snap.next_plan_time)

    # 当前已经结束或者未来不会生效的直接设置为False
    DutyPlan.objects.filter(duty_arrange_id=duty_arrange.id, is_active=True).filter(
        Q(end_time__lte=current_time) | Q(begin_time__gte=begin_time)
    ).update(is_active=False)

    # 当前还要继续生效的设置结束为当前snap的开始时间
    DutyPlan.objects.filter(duty_arrange_id=duty_arrange.id, is_active=True).filter(
        Q(end_time__gt=begin_time) | Q(end_time=None)
    ).update(end_time=begin_time)

    end_time = None
    for users in duty_snap["duty_users"]:
        if duty_snap["need_rotation"] and handoff_time:
            end_time = getattr(
                DutyCalendar,
                "get_{}_rotation_end_time".format(handoff_time["rotation_type"]),
                DutyCalendar.get_daily_rotation_end_time,
            )(begin_time, handoff_time)
        duty_plans.append(
            DutyPlan(
                user_group_id=duty_arrange_snap.user_group_id,
                duty_arrange_id=duty_arrange_snap.duty_arrange_id,
                duty_time=duty_snap["duty_time"],
                is_active=True,
                order=duty_arrange.order,
                begin_time=begin_time,
                end_time=end_time,
                users=users,
            )
        )
        begin_time = end_time

    DutyPlan.objects.bulk_create(duty_plans)
    duty_arrange_snap.next_plan_time = end_time
    duty_arrange_snap.save(update_fields=["next_plan_time"])

    logger.info(
        "[manage_duty_arrange_plan] end to manage duty plan for snap(%s), next_plan_time(%s)",
        snap_id,
        time_tools.localtime(end_time) if end_time else "no ending",
    )
