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

import logging

from celery.schedules import crontab
from celery.task import periodic_task
from django.conf import settings

from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.lock.service_lock import share_lock
from alarm_backends.service.report.tasks import (
    operation_data_custom_report_v2,
    report_mail_detect,
    report_transfer_operation_data,
)
from alarm_backends.service.scheduler.tasks.cron import task_duration
from bkmonitor.utils.custom_report_aggate import register_report_task
from metadata.task.config_refresh import refresh_es_storage

logger = logging.getLogger("bkmonitor.cron_report")


@share_lock()
def register_report_task_cron():
    """注册聚合网关上报任务"""
    register_report_task()


REPORT_CRONTAB = [
    (operation_data_custom_report_v2, "*/5 * * * *", "global"),
    (report_transfer_operation_data, "*/5 * * * *", "global"),
    (refresh_es_storage, "*/10 * * * *", "global"),  # NOTE: ES 周期性任务先放到当前队列中
    # SLI指标和运营数据调整到report周期任务
    (register_report_task_cron, "* * * * *", "cluster"),
]

if int(settings.MAIL_REPORT_BIZ):
    # 如果配置了订阅报表默认业务
    # 订阅报表定时任务 REPORT_CRONTAB
    REPORT_CRONTAB.append((report_mail_detect, "*/1 * * * *", "global"))

for func, cron_expr, run_type in REPORT_CRONTAB:
    # 全局任务在非默认集群不执行
    if run_type == "global" and not get_cluster().is_default():
        continue

    cron_list = cron_expr.split()
    new_func = task_duration(func.__name__)(func)
    locals()[new_func.__name__] = periodic_task(
        run_every=crontab(*cron_list),
        ignore_result=True,
        queue="celery_report_cron",
        expires=300,  # The task will not be executed after the expiration time.
    )(new_func)
