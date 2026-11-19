"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

import datetime

from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.log_clustering.constants import (
    ClusteringOperationStatusEnum,
    ClusteringOperationTypeEnum,
    ClusteringRuntimePhaseEnum,
)
from apps.log_clustering.exceptions import (
    ClusteringOperationConflictException,
    QuixClusteringParamsInvalidException,
)
from apps.log_clustering.handlers.quix.operation import QuixClusteringOperationRunner
from apps.log_clustering.models import ClusteringConfig, LogClusteringOperation, LogClusteringRuntime
from apps.utils.log import logger
from apps.utils.task import high_priority_task

OPERATION_LOCK_TTL_SECONDS = 600
# 超过计划重试时间仍未执行，视为调度消息丢失
STALE_SCHEDULE_SECONDS = 300


@high_priority_task(ignore_result=True)
def run_quix_clustering_operation(operation_id: str):
    lock_key = f"quix_clustering_operation_{operation_id}"
    if not cache.add(lock_key, 1, OPERATION_LOCK_TTL_SECONDS):
        return
    try:
        countdown = QuixClusteringOperationRunner(operation_id).run()
    finally:
        cache.delete(lock_key)
    if countdown is not None:
        run_quix_clustering_operation.apply_async(args=[operation_id], countdown=countdown)


@periodic_task(run_every=crontab(minute="*/5"))
def resume_stale_quix_clustering_operations():
    stale_before = timezone.now() - datetime.timedelta(seconds=STALE_SCHEDULE_SECONDS)
    operation_ids = LogClusteringOperation.objects.filter(
        Q(next_retry_at__isnull=True, updated_at__lt=stale_before) | Q(next_retry_at__lt=stale_before),
        status__in=ClusteringOperationStatusEnum.runnable_statuses(),
    ).values_list("operation_id", flat=True)
    for operation_id in operation_ids:
        run_quix_clustering_operation.delay(operation_id)


@high_priority_task(ignore_result=True)
def follow_quix_clustering_storage(index_set_id: int):
    """索引集切存储后，重新下发聚类配置和路由，使 Pattern、独立结果表跟随新集群。

    仅处理运行中的聚类；已关闭的在重开时按当前集群下发。已有在途操作时跳过，
    该操作尚未下发配置时会读取当前集群，否则需在其结束后修改一次配置。
    """
    runtime = LogClusteringRuntime.objects.filter(index_set_id=index_set_id).first()
    if not runtime or not runtime.sink:
        logger.info("[quix_clustering] index_set(%s) storage switched, skip following", index_set_id)
        return
    filter_rules = ClusteringConfig.objects.get(index_set_id=index_set_id).filter_rules or []
    try:
        with transaction.atomic():
            _runtime, operation = LogClusteringRuntime.start_operation(
                index_set_id,
                ClusteringOperationTypeEnum.UPDATE.value,
                {"filter_rules": filter_rules, "update_model": False},
                allowed_phases=(ClusteringRuntimePhaseEnum.RUNNING.value,),
                updates={"phase": ClusteringRuntimePhaseEnum.UPDATING.value},
            )
    except (ClusteringOperationConflictException, QuixClusteringParamsInvalidException) as exc:
        logger.warning("[quix_clustering] index_set(%s) storage switched, skip following: %s", index_set_id, exc)
        return
    run_quix_clustering_operation.delay(operation.operation_id)
