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

from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery.celery import app
from celery.schedules import crontab

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.tgpa.constants import TGPA_TASK_EXE_CODE_SUCCESS, TGPATaskProcessStatusEnum, FEATURE_TOGGLE_TGPA_TASK
from apps.tgpa.handlers.task import TGPATaskHandler
from apps.tgpa.models import TGPATask
from apps.utils.log import logger


@periodic_task(run_every=crontab(minute="*/1"), queue="tgpa_task")
def fetch_and_process_tgpa_tasks():
    """
    定时任务，拉取任务列表，处理任务
    """
    feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
    if not feature_toggle:
        return
    bk_biz_id_list = feature_toggle.biz_id_white_list or []

    for bk_biz_id in bk_biz_id_list:
        try:
            # 确保已经创建采集配置
            TGPATaskHandler.get_or_create_collector_config(bk_biz_id)
            # 请求接口获取任务列表，过滤掉已经处理过的任务
            task_list = TGPATaskHandler.get_task_list({"cc_id": bk_biz_id})["list"]
            processed_ids = set(TGPATask.objects.filter(bk_biz_id=bk_biz_id).values_list("task_id", flat=True))
            new_tasks = [task for task in task_list if task["id"] not in processed_ids]
        except Exception:
            continue

        for task in new_tasks:
            if task["exe_code"] == TGPA_TASK_EXE_CODE_SUCCESS:
                TGPATask.objects.create(bk_biz_id=bk_biz_id, task_id=task["id"], log_path=task["log_path"])
                process_single_task.delay(task)


@app.task(ignore_result=True, queue="tgpa_task")
def process_single_task(task: dict):
    """
    异步处理单个任务
    """
    task_obj = TGPATask.objects.get(task_id=task["id"])
    task_obj.process_status = TGPATaskProcessStatusEnum.PROCESSING.value
    task_obj.save()
    try:
        TGPATaskHandler(bk_biz_id=task["cc_id"], task_info=task).download_and_process_file()
        task_obj.process_status = TGPATaskProcessStatusEnum.SUCCESS.value
        task_obj.save()
    except Exception as e:
        logger.exception("failed to process task %s", task["id"])
        task_obj.process_status = TGPATaskProcessStatusEnum.FAILED.value
        task_obj.error_message = str(e)
        task_obj.save()
