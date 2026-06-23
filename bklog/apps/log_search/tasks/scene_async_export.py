"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import arrow
from blueapps.core.celery.celery import app
from django.utils import timezone
from django.utils.crypto import get_random_string

from apps.log_search.constants import (
    ASYNC_APP_CODE,
    ASYNC_EXPORT_EMAIL_ERR_TEMPLATE,
    ASYNC_EXPORT_EXPIRED,
    ExportStatus,
    MsgModel,
)
from apps.log_search.models import AsyncTask
from apps.log_unifyquery.handler.scene_async_export import SceneExportUtils
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler
from apps.utils.log import logger


@app.task(ignore_result=True, queue="async_export")
def scene_async_export(
    scene_handler: SceneUnifyQueryHandler,
    sorted_fields: list,
    async_task_id: int,
    url_path: str,
    search_url_path: str,
    language: str,
    is_external: bool = False,
    is_quick_export: bool = False,
    export_file_type: str = "txt",
    external_user_email: str = "",
):
    random_hash = get_random_string(length=10)
    time_now = arrow.now().format("YYYYMMDDHHmmss")
    bk_biz_id = scene_handler.bk_biz_id or 0
    file_name = f"{ASYNC_APP_CODE}_scene_{bk_biz_id}_{time_now}_{random_hash}"
    tar_file_name = f"{file_name}.tar.gz"

    async_task = AsyncTask.objects.filter(id=async_task_id).first()
    export_util = SceneExportUtils(
        scene_handler=scene_handler,
        sorted_fields=sorted_fields,
        file_name=file_name,
        tar_file_name=tar_file_name,
        is_external=is_external,
        is_quick_export=is_quick_export,
        export_file_type=export_file_type,
        external_user_email=external_user_email,
    )

    try:
        if not async_task:
            logger.error("Can not find scene async_task record: id=%s", async_task_id)
            raise BaseException(f"Can not find scene async_task: id={async_task_id}")

        async_task.export_status = ExportStatus.DOWNLOAD_LOG
        async_task.save()

        try:
            export_util.export_package(async_task_id=async_task.id)
        except Exception as e:
            _set_failed(async_task, f"export package error: {e}")
            raise

        async_task.export_status = ExportStatus.EXPORT_PACKAGE
        async_task.file_name = tar_file_name
        async_task.file_size = export_util.get_file_size()
        async_task.save()

        try:
            export_util.export_upload()
        except Exception as e:
            _set_failed(async_task, f"export upload error: {e}")
            raise

        async_task.export_status = ExportStatus.EXPORT_UPLOAD
        async_task.save()

        try:
            url = export_util.generate_download_url(url_path=url_path)
        except Exception as e:
            _set_failed(async_task, f"generate download url error: {e}")
            raise

        async_task.download_url = url

        try:
            export_util.send_msg(
                async_task=async_task,
                search_url_path=search_url_path,
                language=language,
            )
        except Exception as e:
            logger.error("scene async_task_id:%s, send msg error: %s", async_task_id, e)

    except Exception as e:
        logger.exception(e)
        export_util.send_msg(
            async_task=async_task,
            search_url_path=search_url_path,
            language=language,
            name=ASYNC_EXPORT_EMAIL_ERR_TEMPLATE,
            title_model=MsgModel.ABNORMAL,
        )
        return

    async_task.result = True
    async_task.export_status = ExportStatus.SUCCESS
    async_task.completed_at = timezone.now()
    async_task.save()

    export_util.clean_package()

    from apps.log_search.tasks.unify_query_async_export import set_expired_status

    set_expired_status.apply_async(args=[async_task.id], countdown=ASYNC_EXPORT_EXPIRED)


def _set_failed(async_task: AsyncTask, reason: str):
    async_task.failed_reason = reason
    async_task.export_status = ExportStatus.FAILED
    logger.error(reason)
    async_task.save()
