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

import hashlib

import arrow
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery.celery import app
from celery.schedules import crontab
from django.utils import timezone


from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.tgpa.constants import (
    TGPA_TASK_EXE_CODE_SUCCESS,
    TGPATaskProcessStatusEnum,
    FEATURE_TOGGLE_TGPA_TASK,
    TGPAReportSyncStatusEnum,
)
from apps.tgpa.handlers.base import TGPAFileHandler, TGPACollectorConfigHandler
from apps.tgpa.handlers.report import TGPAReportHandler
from apps.tgpa.handlers.task import TGPATaskHandler
from apps.tgpa.models import TGPATask, TGPAReport, TGPAReportSyncRecord
from apps.utils.lock import share_lock, RedisLock
from apps.utils.log import logger
from apps.utils.thread import MultiExecuteFunc


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
            # 统一将 go_svr_task_id 转换为 int 类型，确保与数据库字段类型一致
            for task in task_list:
                task["go_svr_task_id"] = int(task["go_svr_task_id"])
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


@app.task(ignore_result=True, queue="tgpa_task")
def fetch_and_process_tgpa_reports(record_id: int, params: dict):
    """
    拉取客户端上报文件列表，处理文件
    """
    logger.info("Begin to sync tgpa reports, record_id: %s", record_id)
    record_obj = TGPAReportSyncRecord.objects.get(id=record_id)
    record_obj.status = TGPAReportSyncStatusEnum.RUNNING.value
    record_obj.save(update_fields=["status"])
    try:
        multi_execute_func = MultiExecuteFunc()
        report_list = TGPAReportHandler.iter_report_list(
            bk_biz_id=params["bk_biz_id"],
            openid_list=params.get("openid_list"),
            file_name_list=params.get("file_name_list"),
            start_time=params.get("start_time"),
            end_time=params.get("end_time"),
        )
        for report in report_list:
            multi_execute_func.append(
                result_key=report["file_name"],
                func=process_single_report,
                params={"report_info": report, "record_id": record_id},
                multi_func_params=True,
            )
        multi_execute_func.run(return_exception=True)
        TGPAReportHandler.update_process_status(record_id=record_id)
        logger.info("Successfully synced tgpa reports, record_id: %s", record_id)
    except Exception as e:
        record_obj.status = TGPAReportSyncStatusEnum.FAILED.value
        record_obj.error_message = str(e)
        record_obj.save(update_fields=["status", "error_message"])
        logger.exception("Failed to sync tgpa reports, record_id %s", record_id)


@app.task(ignore_result=True, queue="tgpa_task")
def process_single_report(report_info: dict, record_id: int):
    """
    处理单个客户端上报文件
    """
    file_name = report_info["file_name"]
    bk_biz_id = report_info["bk_biz_id"]
    logger.info("Begin to process report file, file_name: %s", file_name)

    # 避免并发处理同一文件
    lock_key = f"tgpa_report_lock_{file_name}"
    lock = RedisLock(lock_key, ttl=600)  # 锁超时时间10分钟
    if not lock.acquire(_wait=0.1):
        logger.warning("Failed to acquire lock for file_name: %s", file_name)
        return

    try:
        if TGPAReport.objects.filter(
            file_name=file_name,
            process_status=TGPATaskProcessStatusEnum.SUCCESS.value,
        ).exists():
            logger.info("Report file already processed successfully, skip. file_name: %s", file_name)
            return

        report_obj = TGPAReport.objects.create(
            file_name=file_name,
            bk_biz_id=bk_biz_id,
            record_id=record_id,
            openid=report_info.get("openid"),
            process_status=TGPATaskProcessStatusEnum.RUNNING.value,
            processed_at=timezone.now(),
        )

        try:
            TGPAReportHandler(bk_biz_id=bk_biz_id, report_info=report_info).download_and_process_file()
            report_obj.process_status = TGPATaskProcessStatusEnum.SUCCESS.value
            report_obj.save(update_fields=["process_status"])
            logger.info("Successfully processed report file, file_name: %s", file_name)
        except Exception as e:
            logger.exception("Failed to process report file, file_name %s", file_name)
            report_obj.process_status = TGPATaskProcessStatusEnum.FAILED.value
            report_obj.error_message = str(e)
            report_obj.save(update_fields=["process_status", "error_message"])
    finally:
        lock.release()


@periodic_task(run_every=crontab(minute="*/5"), queue="tgpa_task")
@share_lock()
def periodic_sync_tgpa_reports():
    """
    定期同步客户端上报文件
    - 从 FeatureToggle 获取需要处理的业务列表
    - 记录处理时间，根据上次处理时间进行增量同步
    - 支持采样率配置，只处理部分数据
    - 使用 Celery 异步任务处理单个文件
    """
    feature_toggle = FeatureToggleObject.toggle(FEATURE_TOGGLE_TGPA_TASK)
    if not feature_toggle:
        return
    bk_biz_id_list = feature_toggle.biz_id_white_list or []

    # 同步百分比配置格式: {"tgpa_report_sync_percent": {"bk_biz_id": sync_percent, ...}}
    # sync_percent 为 1-100 的整数，表示同步百分比
    feature_config = feature_toggle.feature_config or {}
    sync_percent_config = feature_config.get("tgpa_report_sync_percent", {})

    for bk_biz_id in bk_biz_id_list:
        # 获取该业务的同步百分比，默认为 0（不处理），范围 1-100
        sync_percent = sync_percent_config.get(str(bk_biz_id), 0)
        if not isinstance(sync_percent, int) or not (1 <= sync_percent <= 100):
            logger.warning(
                "Invalid sync percent for business: %s, sync_percent: %s (should be 1-100)", bk_biz_id, sync_percent
            )
            continue

        logger.info("Begin periodic sync tgpa reports for business: %s, sync_percent: %s", bk_biz_id, sync_percent)
        # 获取上一次同步记录
        last_sync_record = (
            TGPAReportSyncRecord.objects.filter(bk_biz_id=bk_biz_id, created_by="periodic_task")
            .order_by("-created_at")
            .first()
        )
        # 创建新的同步记录
        current_sync_record = TGPAReportSyncRecord.objects.create(
            bk_biz_id=bk_biz_id,
            status=TGPAReportSyncStatusEnum.RUNNING.value,
            created_by="periodic_task",
        )

        # 更新上一次同步记录的状态，获取时间范围
        if last_sync_record:
            TGPAReportHandler.update_process_status(record_id=last_sync_record.id)
            start_time = int(arrow.get(last_sync_record.created_at).timestamp() * 1000)
        else:
            # 如果没有上一次同步记录，从 5 分钟前开始同步
            start_time = int(arrow.now().shift(minutes=-5).timestamp() * 1000)
        end_time = int(arrow.get(current_sync_record.created_at).timestamp() * 1000)

        try:
            # 获取时间范围内的上报文件列表
            report_list = TGPAReportHandler.iter_report_list(
                bk_biz_id=bk_biz_id, start_time=start_time, end_time=end_time
            )

            processed_count = 0
            skipped_count = 0
            for report in report_list:
                # 计算标识符的 MD5 哈希值，取前8位转换为整数
                hash_value = int(hashlib.md5(report["file_name"].encode()).hexdigest()[:8], 16)
                # 将哈希值映射到 0-99 的范围，判断是否小于覆盖百分比
                if (hash_value % 100) >= sync_percent:
                    skipped_count += 1
                    continue

                process_single_report.delay(report_info=report, record_id=current_sync_record.id)
                processed_count += 1

            logger.info(
                "Finished periodic sync tgpa reports for business: %s, processed: %s, skipped: %s",
                bk_biz_id,
                processed_count,
                skipped_count,
            )
        except Exception as e:
            logger.exception("Failed to periodic sync tgpa reports for business: %s", bk_biz_id)
            current_sync_record.status = TGPAReportSyncStatusEnum.FAILED.value
            current_sync_record.error_message = str(e)
            current_sync_record.save(update_fields=["status", "error_message"])
