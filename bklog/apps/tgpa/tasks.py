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

import arrow
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery.celery import app
from celery.schedules import crontab
from django.utils import timezone


from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.tgpa.constants import TGPA_TASK_EXE_CODE_SUCCESS, TGPATaskProcessStatusEnum, FEATURE_TOGGLE_TGPA_TASK
from apps.tgpa.handlers.base import TGPAFileHandler, TGPACollectorConfigHandler
from apps.tgpa.handlers.report import TGPAReportHandler
from apps.tgpa.handlers.task import TGPATaskHandler
from apps.tgpa.models import TGPATask, TGPAReport
from apps.utils.lock import share_lock
from apps.utils.log import logger


@periodic_task(run_every=crontab(minute="*/1"), queue="tgpa_task")
@share_lock()
def fetch_and_process_tgpa_tasks():
    """
    定时任务，拉取任务列表，处理任务
    使用share_lock防止多个任务并行执行
    """
    feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
    if not feature_toggle:
        return
    bk_biz_id_list = feature_toggle.biz_id_white_list or []

    for bk_biz_id in bk_biz_id_list:
        logger.info("Begin to sync client log tasks, business id: %s", bk_biz_id)
        try:
            # 确保已经创建采集配置
            TGPACollectorConfigHandler.get_or_create_collector_config(bk_biz_id)
            # 获取任务列表，存量的任务只同步数据，不处理任务
            task_list = TGPATaskHandler.get_task_list({"cc_id": bk_biz_id})["list"]
            if not TGPATask.objects.filter(bk_biz_id=bk_biz_id).exists():
                TGPATask.objects.bulk_create(
                    [
                        TGPATask(
                            id=task["id"],
                            task_id=task["go_svr_task_id"],
                            bk_biz_id=bk_biz_id,
                            log_path=task["log_path"],
                            task_status=task["status"],
                            file_status=task["exe_code"],
                            process_status=TGPATaskProcessStatusEnum.INIT.value,
                        )
                        for task in task_list
                    ]
                )
                continue
        except Exception:
            logger.exception("Failed to sync client log tasks, business id: %s", bk_biz_id)
            continue

        # 对比任务列表和数据库中的任务
        existed_tasks = TGPATask.objects.filter(bk_biz_id=bk_biz_id)
        task_map = {task.task_id: task for task in existed_tasks}
        for task in task_list:
            if task_obj := task_map.get(task["go_svr_task_id"]):
                # 如果文件状态发生变化，并且文件状态为上传成功，处理任务
                if task["exe_code"] != task_obj.file_status and task["exe_code"] == TGPA_TASK_EXE_CODE_SUCCESS:
                    task_obj.process_status = TGPATaskProcessStatusEnum.PENDING.value
                    task_obj.save(update_fields=["process_status"])
                    process_single_task.delay(task)
                # 如果任务状态发生变化，更新任务状态
                if task_obj.task_status != task["status"] or task_obj.file_status != task["exe_code"]:
                    task_obj.task_status = task["status"]
                    task_obj.file_status = task["exe_code"]
                    task_obj.save(update_fields=["task_status", "file_status"])
            else:
                task_obj, created = TGPATask.objects.get_or_create(
                    task_id=task["go_svr_task_id"],
                    defaults={
                        "id": task["id"],
                        "bk_biz_id": task["cc_id"],
                        "log_path": task["log_path"],
                        "task_status": task["status"],
                        "file_status": task["exe_code"],
                        "process_status": TGPATaskProcessStatusEnum.INIT.value,
                    },
                )
                if created and task["exe_code"] == TGPA_TASK_EXE_CODE_SUCCESS:
                    task_obj.process_status = TGPATaskProcessStatusEnum.PENDING.value
                    task_obj.save(update_fields=["process_status"])
                    process_single_task.delay(task)


@app.task(ignore_result=True, queue="tgpa_task")
def process_single_task(task: dict):
    """
    异步处理单个任务
    """
    logger.info("Begin to process task, task_id: %s", task["go_svr_task_id"])
    task_obj = TGPATask.objects.get(task_id=task["go_svr_task_id"])
    if task_obj.process_status != TGPATaskProcessStatusEnum.PENDING.value:
        return

    task_obj.process_status = TGPATaskProcessStatusEnum.RUNNING.value
    task_obj.processed_at = timezone.now()
    task_obj.save(update_fields=["process_status", "processed_at"])
    try:
        TGPATaskHandler(bk_biz_id=task["cc_id"], task_info=task).download_and_process_file()
        task_obj.process_status = TGPATaskProcessStatusEnum.SUCCESS.value
        task_obj.save(update_fields=["process_status"])
        logger.info("Successfully processed task, task_id: %s", task["go_svr_task_id"])
    except Exception as e:
        logger.exception("Failed to process task, task_id %s", task["go_svr_task_id"])
        task_obj.process_status = TGPATaskProcessStatusEnum.FAILED.value
        task_obj.error_message = str(e)
        task_obj.save(update_fields=["process_status", "error_message"])


@periodic_task(run_every=crontab(minute="0", hour="1"), queue="tgpa_task")
def clear_expired_files():
    """
    清理过期文件
    """
    logger.info("Begin to clear expired client log files")
    TGPAFileHandler.clear_expired_files()
    logger.info("Successfully cleared expired client log files")


@periodic_task(run_every=crontab(minute="*/1"), queue="tgpa_task")
@share_lock()
def fetch_and_process_tgpa_reports():
    """
    定时任务，拉取客户端上报文件列表，处理文件
    使用share_lock防止多个任务并行执行
    """
    feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
    if not feature_toggle:
        return
    bk_biz_id_list = feature_toggle.biz_id_white_list or []

    for bk_biz_id in bk_biz_id_list:
        logger.info("Begin to sync tgpa report files, business id: %s", bk_biz_id)
        try:
            TGPACollectorConfigHandler.get_or_create_collector_config(bk_biz_id)

            now = arrow.now()
            last_process_at = now.shift(minutes=-1)  # 默认为1分钟前
            if process_record := TGPAReport.objects.filter(bk_biz_id=bk_biz_id).first():
                # 将数据库中上次处理时间设置为当前时间
                last_process_at = arrow.get(process_record.last_processed_at)
                process_record.last_processed_at = now.datetime
                process_record.save(update_fields=["last_processed_at"])
            else:
                process_record = TGPAReport.objects.create(bk_biz_id=bk_biz_id, last_processed_at=now.datetime)

            # 拉取文件列表并处理，如果发生异常，这批数据会被跳过
            report_list = TGPAReportHandler.iter_report_list(
                bk_biz_id,
                start_time=int(last_process_at.timestamp() * 1000),
                end_time=int(now.timestamp() * 1000),
            )
            report_count = 0
            for report_info in report_list:
                process_single_report.delay(bk_biz_id, report_info)
                report_count += 1

            # 更新处理统计信息
            process_record.last_processed_count = report_count
            process_record.total_processed_count += report_count
            process_record.save(update_fields=["last_processed_count", "total_processed_count"])
            logger.info("Successfully process report files for business %s, count: %s", bk_biz_id, report_count)
        except Exception as e:
            logger.exception("Failed to sync tgpa report files, business id: %s", bk_biz_id)
            # 记录错误信息
            if process_record := TGPAReport.objects.filter(bk_biz_id=bk_biz_id).first():
                process_record.last_error_message = str(e)
                process_record.last_error_at = timezone.now()
                process_record.save(update_fields=["last_error_message", "last_error_at"])
            continue


@app.task(ignore_result=True, queue="tgpa_task")
def process_single_report(bk_biz_id: int, report_info: dict):
    """
    异步处理单个客户端上报文件
    """
    logger.info("Begin to process report file, file_name: %s", report_info.get("file_name"))
    try:
        TGPAReportHandler(bk_biz_id=bk_biz_id, report_info=report_info).download_and_process_file()
        logger.info("Successfully processed report file, file_name: %s", report_info.get("file_name"))
    except Exception:
        logger.exception("Failed to process report file, file_name %s", report_info.get("file_name"))
