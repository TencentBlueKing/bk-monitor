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


import functools
import logging
import random

from alarm_backends.service.selfmonitor.tasks import healthz

from .checker import CHECKER_FAILED, CHECKER_OK, CheckerRegister
from .utils import get_process_info_by_group

register = CheckerRegister.celery
logger = logging.getLogger("self_monitor")


@register.execution.status()
def execution_status(manager, result, queues, timeout=3):
    """Celery worker 任务执行测试"""
    value = random.random()
    proxy_items = []
    queue_result = []
    # 批量发送celery任务
    for queue in queues:
        proxy = healthz.apply_async(queue=queue, args=(value,), expires=timeout)
        proxy_items.append({"queue": queue, "proxy": proxy})
    # 批量检查celery任务结果，检查失败则增加失败任务统计
    for proxy_item in proxy_items:
        proxy = proxy_item["proxy"]
        status_check_info = functools.partial(generate_check_info, name=str({"queue": proxy_item["queue"]}))
        try:
            res = proxy.get(timeout=timeout)
            if res:
                queue_result.append(status_check_info(status=CHECKER_OK, value="ok"))
            else:
                queue_result.append(status_check_info(status=CHECKER_FAILED, message="get celery task result failed"))
        except Exception as e:
            logger.exception(e)
            queue_result.append(status_check_info(status=CHECKER_FAILED, message=str(e)))
        finally:
            proxy.forget()

    result.update(value=queue_result)


@register.process.status()
def process_info(manager, result, group_name, process_name):
    """celery worker 进程状态"""
    processes_result = []
    # 遍历所选组内所有任务
    for name in process_name:
        status_check_info = functools.partial(generate_check_info, name=str({"process_name": name}))
        found = False
        ok = False
        for info in get_process_info_by_group(group_name):
            # 如果任务名含有process_name，证明是该类型任务
            if info.get("name").startswith(name):
                found = True
                if info and (info.get("statename") == "RUNNING" or info.get("description") == "Not started"):
                    ok = True
                    break
        if found:
            if ok:
                processes_result.append(status_check_info(status=CHECKER_OK, value="ok"))
            else:
                processes_result.append(status_check_info(status=CHECKER_FAILED, message="celery process not running"))
        else:
            processes_result.append(status_check_info(status=CHECKER_FAILED, message="celery process not found"))

    return result.update(value=processes_result)


def generate_check_info(name, status=CHECKER_OK, message="", value=""):
    return {
        "name": name,
        "status": status,
        "message": message,
        "value": value,
    }
