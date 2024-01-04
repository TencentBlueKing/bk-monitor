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
import time
import typing
from functools import wraps

from celery.task import periodic_task as _periodic_task
from celery.task import task as _task

__implements__ = ["task", "periodic_task"]


# 函数计时器
def timer(queue: str = None) -> typing.Callable[[typing.Callable], typing.Callable]:
    """
    函数计时器
    """
    if not queue:
        queue = "celery"

    def actual_timer(func) -> typing.Callable:
        from core.prometheus import metrics

        @wraps(func)
        def wrapper(*args, **kwargs):
            result, exception = None, None
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
            except Exception as e:  # noqa
                exception = e

            # 记录函数执行时间
            metrics.CELERY_TASK_EXECUTE_TIME.labels(
                task_name=func.__name__,
                queue=queue,
                status="failed" if exception else "success",
            ).observe(time.time() - start_time)
            metrics.report_all()

            # 如果函数执行失败，抛出异常
            if exception:
                raise exception
            return result
        return wrapper
    return actual_timer


def task(*args, **kwargs):
    """Deprecated decorator, please use :func:`celery.task`."""
    decorator = _task(*args, **kwargs)

    def wrapper(func):
        return decorator(timer(queue=kwargs.get("queue"))(func))
    return wrapper


def periodic_task(*args, **options):
    """Deprecated decorator, please use :setting:`beat_schedule`."""
    decorator = _periodic_task(*args, **options)

    def wrapper(func):
        return decorator(timer(queue=options.get("queue"))(func))
    return wrapper
