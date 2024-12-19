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
import datetime
import functools
import logging
import time

from celery.schedules import crontab
from django.conf import settings
from django.utils.module_loading import import_string

from alarm_backends.core.cluster import get_cluster
from alarm_backends.service.scheduler.app import periodic_task
from core.prometheus import metrics

logger = logging.getLogger("cron")


def task_duration(task_name, queue_name=None):
    def wrapper(_func):
        @functools.wraps(_func)
        def _inner(*args, **kwargs):
            start = time.time()
            logger.info("^[Cron Task](%s)" % task_name)
            exception = None
            try:
                return _func(*args, **kwargs)
            except Exception as e:
                logger.exception("![Cron Task]({}) error: {}".format(task_name, e))
                exception = e
            finally:
                time_cost = time.time() - start
                logger.info("$[Cron Task]({}) cost: {}".format(task_name, time_cost))
                metrics.CRON_TASK_EXECUTE_TIME.labels(task_name=task_name, queue=queue_name).observe(time_cost)
                metrics.CRON_TASK_EXECUTE_COUNT.labels(
                    task_name=task_name,
                    exception=exception,
                    status=metrics.StatusEnum.from_exc(exception),
                    queue=queue_name,
                ).inc()
                metrics.report_all()

        return _inner

    return wrapper


def _get_func(module_path, queue=None):
    def _inner_func(*args, **kwargs):
        try:
            process_func = import_string(module_path)
            process_func = getattr(process_func, "main", process_func)
        except ImportError:
            process_func = import_string("%s.main" % module_path)

        return task_duration(module_path, queue)(process_func)(*args, **kwargs)

    return _inner_func


def get_interval(cron_obj):
    # 获取当前时间
    now = cron_obj.now()
    # 下次执行需等待时间
    next_delta = cron_obj.remaining_estimate(now)
    # 下下次执行需等待时间
    next_next_delta = cron_obj.remaining_estimate(now + next_delta + datetime.timedelta(minutes=1))
    # 计算周期
    interval = (next_next_delta - next_delta).seconds
    return interval


queue_define = {
    # 默认周期任务
    "celery_cron": settings.DEFAULT_CRONTAB,
    "celery_action_cron": settings.ACTION_TASK_CRONTAB,
    # 耗时过大的任务单独队列
    "celery_long_task_cron": settings.LONG_TASK_CRONTAB,
}

for queue, crontab_tasks in queue_define.items():
    for module_name, cron_expr, run_type in crontab_tasks:
        # 全局任务在非默认集群不执行
        if run_type == "global" and not get_cluster().is_default():
            continue

        func_name = str(module_name.replace(".", "_"))
        cron_list = cron_expr.split()
        func = _get_func(module_name, queue=queue)
        func.__name__ = func_name
        run_every = crontab(*cron_list)
        locals()[func_name] = periodic_task(
            run_every=run_every,
            ignore_result=True,
            queue=queue,
            # 超时范围: 5m-1h
            expires=min(3600, max(get_interval(run_every), 300)),
        )(func)
