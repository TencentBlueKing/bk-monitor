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
from alarm_backends.service.fta_action.utils import PushActionProcessor, to_document
from alarm_backends.service.scheduler.tasks import perform_sharding_task
from bkmonitor.action.duty_manage import GroupDutyRuleManager
from bkmonitor.action.serializers import DutyRuleDetailSlz
from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.models import ActionInstance, ConvergeRelation
from bkmonitor.models.strategy import DutyRule, DutyRuleRelation, UserGroup
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
    if is_finished and action_instance and not action_instance.is_parent_action:
        # 结束之后统计任务的执行情况
        # 统计是否成功失败的指标，忽略掉主任务（主任务没有真正执行的内容）
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
    周期维护
    """
    duty_rule_ids = set(DutyRuleRelation.objects.all().values_list("duty_rule_id", flat=True))
    duty_rule_dict = {
        d["id"]: d
        for d in DutyRuleDetailSlz(instance=DutyRule.objects.filter(id__in=list(duty_rule_ids)), many=True).data
    }
    managers = []
    for user_group in UserGroup.objects.filter(need_duty=True).only(
        "id", "bk_biz_id", "duty_rules", "duty_notice", "timezone"
    ):
        # 获取有轮值关联的用户组进行任务管理
        group_duties = [duty_rule_dict[rule_id] for rule_id in user_group.duty_rules if rule_id in duty_rule_dict]
        if not group_duties:
            logger.info("[generate_duty_plan_task] empty duty group(%s), turn to next one", user_group.id)
            continue
        duty_manager = GroupDutyRuleManager(user_group, group_duties)
        manage_group_duty_snap.delay(duty_manager)
        if user_group.duty_notice and any(
            [
                user_group.duty_notice.get("plan_notice", {}).get("enabled"),
                user_group.duty_notice.get("personal_notice", {}).get("enabled"),
            ]
        ):
            # 当有需要进行通知任务的时候，才推送通知任务
            manage_group_duty_notice.delay(duty_manager)
        managers.append(duty_manager)
    return managers


@task(ignore_result=True, queue="celery_action_cron")
def manage_group_duty_snap(duty_manager: GroupDutyRuleManager):
    """
    单个任务组的排班计划管理
    """
    # 每天做一次管理检查
    logger.info("start to manage group(%s)'s duty plan", duty_manager.user_group.id)
    task_time = datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    duty_manager.manage_duty_rule_snap(task_time)
    logger.info("finished to manage group(%s)'s duty plan", duty_manager.user_group.id)


@task(ignore_result=True, queue="celery_action_cron")
def manage_group_duty_notice(duty_manager: GroupDutyRuleManager):
    """
    单个任务组的排班计划管理
    """
    # 每天做一次管理检查
    logger.info("start to manage group(%s)'s duty notice", duty_manager.user_group.id)
    duty_manager.manage_duty_notice()
    logger.info("finished to manage group(%s)'s duty notice", duty_manager.user_group.id)
