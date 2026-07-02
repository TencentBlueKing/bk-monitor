"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
"""

import copy
import json
import os
import tarfile

import arrow
import ujson
from django.conf import settings
from django.db.models import F
from django.utils import translation
from django.utils.translation import gettext as _
from rest_framework.reverse import reverse

from apps.constants import RemoteStorageType
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import UNIFY_QUERY_SEARCH_EXPORT
from apps.log_search.constants import (
    ASYNC_DIR,
    ASYNC_EXPORT_EMAIL_TEMPLATE,
    ASYNC_EXPORT_EXPIRED,
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_EXTERNAL,
    FEATURE_ASYNC_EXPORT_NOTIFY_TYPE,
    FEATURE_ASYNC_EXPORT_STORAGE_TYPE,
    ExportStatus,
    ExportType,
    MAX_ASYNC_COUNT,
    MAX_QUICK_EXPORT_ASYNC_COUNT,
    MsgModel,
)
from apps.log_search.models import AsyncTask
from apps.log_unifyquery.handler.scene_search import SceneUnifyQueryHandler
from apps.utils.local import (
    get_request,
    get_request_app_code,
    get_request_external_user_email,
    get_request_external_username,
    get_request_language_code,
    get_request_username,
)
from apps.utils.drf import DataPageNumberPagination
from apps.utils.log import logger
from apps.utils.notify import NotifyType
from apps.utils.remote_storage import StorageType


class SceneAsyncExportHandler:
    """Async export handler for scene-based search (no index_set_id dependency)."""

    def __init__(
        self,
        bk_biz_id=None,
        search_dict: dict = None,
        export_fields=None,
        export_file_type: str = "txt",
    ):
        self.bk_biz_id = bk_biz_id
        self.search_dict = search_dict or {}
        self.export_file_type = export_file_type

        if search_dict and search_dict.get("table_id_conditions"):
            search_dict_copy = copy.deepcopy(self.search_dict)
            search_dict_copy["export_fields"] = export_fields
            self.scene_handler = SceneUnifyQueryHandler(search_dict_copy)
        else:
            self.scene_handler = None

        self.request_user = get_request_external_username() or get_request_username()
        self.is_external = bool(get_request_external_username())

    def async_export(self, is_quick_export: bool = False):
        from apps.log_search.exceptions import (
            DuplicateUnifyQueryExportException,
            PreCheckAsyncExportException,
        )

        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH_EXPORT, self.bk_biz_id):
            if AsyncTask.objects.filter(
                request_param=self.search_dict,
                created_by=self.request_user,
                export_status=ExportStatus.DOWNLOAD_LOG,
            ).exists():
                raise DuplicateUnifyQueryExportException()

        result = self.scene_handler.pre_get_result(
            sorted_fields=self.scene_handler.origin_order_by,
            size=1000,
        )
        # 提交时即按 ts/raw 返回的 result_table_id 做结果表级检索权限校验，无权限直接报错
        self.scene_handler.verify_result_table_search_permission(result.get("result_table_id"))
        if not result.get("list"):
            logger.error("can not create scene async_export task, reason: no data")
            raise PreCheckAsyncExportException()

        export_total_count = self.get_export_total_count(
            total_count=result.get("total", 0),
            is_quick_export=is_quick_export,
        )
        async_task = AsyncTask.objects.create(
            request_param=self.search_dict,
            sorted_param=self.scene_handler.origin_order_by,
            scenario_id="scene",
            index_set_id=0,
            bk_biz_id=self.bk_biz_id,
            start_time=self.search_dict.get("start_time", ""),
            end_time=self.search_dict.get("end_time", ""),
            export_type=ExportType.ASYNC,
            export_total_count=export_total_count,
            created_by=self.request_user,
        )

        url = reverse("tasks-download-file", request=get_request())
        search_url = self._get_search_url()

        from apps.log_search.tasks.scene_async_export import scene_async_export

        scene_async_export.delay(
            scene_handler=self.scene_handler,
            sorted_fields=self.scene_handler.origin_order_by,
            async_task_id=async_task.id,
            url_path=url,
            search_url_path=search_url,
            language=get_request_language_code(),
            is_external=self.is_external,
            is_quick_export=is_quick_export,
            export_file_type=self.export_file_type,
            external_user_email=get_request_external_user_email(),
        )
        return async_task.id, export_total_count

    def _get_search_url(self):
        request = get_request()
        return f"{request.scheme}://{request.get_host()}{settings.SITE_URL}#/retrieve/scene"

    def get_export_history(self, request, view, show_all=False, table_id_conditions=None):
        source_app_code = get_request_app_code()
        external_username = get_request_external_username()
        query_set = AsyncTask.objects.filter(
            bk_biz_id=self.bk_biz_id,
            source_app_code=source_app_code,
            scenario_id="scene",
        )
        if table_id_conditions:
            query_set = query_set.filter(
                request_param__table_id_conditions=table_id_conditions,
            )
        if external_username:
            query_set = query_set.filter(created_by=external_username)
        if not show_all:
            query_set = query_set.filter(created_by=self.request_user)

        pg = DataPageNumberPagination()
        page_history = (
            pg.paginate_queryset(
                queryset=query_set.order_by("-created_at", "created_by"),
                request=request,
                view=view,
            )
            or []
        )
        from apps.models import model_to_dict

        return pg.get_paginated_response([self._format_history(model_to_dict(h)) for h in page_history])

    @staticmethod
    def _format_history(task_dict):
        download_able = task_dict["export_status"] != ExportStatus.DOWNLOAD_EXPIRED
        return {
            "id": task_dict["id"],
            "search_dict": task_dict["request_param"],
            "start_time": task_dict["start_time"],
            "end_time": task_dict["end_time"],
            "export_type": task_dict["export_type"],
            "export_status": task_dict["export_status"],
            "error_msg": task_dict["failed_reason"],
            "download_url": task_dict["download_url"],
            "export_pkg_name": task_dict["file_name"],
            "export_pkg_size": task_dict["file_size"],
            "export_created_at": task_dict["created_at"],
            "export_created_by": task_dict["created_by"],
            "export_completed_at": task_dict["completed_at"],
            "exported_count": task_dict["exported_count"],
            "export_total_count": task_dict["export_total_count"],
            "download_count": task_dict["download_count"],
            "download_able": download_able,
            "retry_able": True,
            "index_set_type": "scene",
        }

    @staticmethod
    def get_export_total_count(total_count, is_quick_export: bool = False):
        export_limit = MAX_QUICK_EXPORT_ASYNC_COUNT if is_quick_export else MAX_ASYNC_COUNT
        return min(total_count or export_limit, export_limit)


class SceneExportUtils:
    """Package / upload / notify utilities for scene-based async export."""

    def __init__(
        self,
        scene_handler: SceneUnifyQueryHandler,
        sorted_fields: list,
        file_name: str,
        tar_file_name: str,
        is_external: bool = False,
        is_quick_export: bool = False,
        export_file_type: str = "txt",
        external_user_email: str = "",
    ):
        self.scene_handler = scene_handler
        self.sorted_fields = sorted_fields
        self.file_name = file_name
        self.tar_file_name = tar_file_name
        self.is_external = is_external
        self.is_quick_export = is_quick_export
        self.export_file_type = export_file_type
        self.external_user_email = external_user_email
        self.tar_file_path = f"{ASYNC_DIR}/{self.tar_file_name}"
        self.storage = self._init_remote_storage()
        self.notify = self._init_notify_type()
        self.file_path_list = []

    def export_package(self, async_task_id: int):
        if not (os.path.exists(ASYNC_DIR) and os.path.isdir(ASYNC_DIR)):
            os.makedirs(ASYNC_DIR)
        summary_file_path = f"{ASYNC_DIR}/{self.file_name}_summary.{self.export_file_type}"
        with open(summary_file_path, "a+", encoding="utf-8") as f:
            for result_batch in self.scene_handler.export_data(is_quick_export=self.is_quick_export):
                origin_log_list = result_batch.get("origin_log_list", [])
                for item in origin_log_list:
                    f.write(f"{ujson.dumps(item, ensure_ascii=False)}\n")
                AsyncTask.objects.filter(id=async_task_id).update(
                    exported_count=F("exported_count") + len(origin_log_list)
                )

        with tarfile.open(self.tar_file_path, "w:gz") as tar:
            tar.add(summary_file_path, arcname=os.path.basename(summary_file_path))
            self.file_path_list.append(summary_file_path)

    def export_upload(self):
        self.storage.export_upload(file_path=self.tar_file_path, file_name=self.tar_file_name)

    def generate_download_url(self, url_path: str):
        return self.storage.generate_download_url(url_path=url_path, file_name=self.tar_file_name)

    def get_file_size(self):
        return max(round(os.path.getsize(self.tar_file_path) / float(1024 * 1024), 2), 0.01)

    def clean_package(self):
        for file_path in self.file_path_list:
            if os.path.exists(file_path):
                os.remove(file_path)
        if os.path.exists(self.tar_file_path):
            os.remove(self.tar_file_path)

    def send_msg(
        self,
        async_task: AsyncTask,
        search_url_path: str,
        language: str,
        name: str = ASYNC_EXPORT_EMAIL_TEMPLATE,
        title_model: str = MsgModel.NORMAL,
    ):
        platform = settings.EMAIL_TITLE["en"] if translation.get_language() == "en" else settings.EMAIL_TITLE["zh"]

        title_map = {
            MsgModel.NORMAL: _("【{platform}】场景化检索导出"),
            MsgModel.ABNORMAL: _("【{platform}】场景化检索导出失败"),
        }
        title = self.notify.title(
            title_map.get(title_model, title_map[MsgModel.NORMAL]),
            platform=platform,
        )

        content = self.notify.content(
            name=name,
            file={
                "platform": platform,
                "created_at": arrow.now().format("YYYY-MM-DD HH:mm:ss"),
                "index_set_name": "场景化检索",
                "index": "",
                "create_by": async_task.created_by,
                "size": async_task.file_size,
                "request_param": json.dumps(async_task.request_param),
                "search_url": search_url_path,
                "download_url": async_task.download_url,
            },
            language=language,
        )
        receivers = self.external_user_email if self.is_external else async_task.created_by
        self.notify.send(receivers=receivers, title=title, content=content, is_external=self.is_external)

    def _init_remote_storage(self):
        if self.is_external:
            toggle = FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_EXTERNAL).feature_config
        else:
            toggle = FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_COMMON).feature_config
        storage_type = toggle.get(FEATURE_ASYNC_EXPORT_STORAGE_TYPE)
        storage = StorageType.get_instance(storage_type)
        if not storage_type or storage_type == RemoteStorageType.NFS.value:
            return storage(settings.EXTRACT_SAAS_STORE_DIR)
        if storage_type == RemoteStorageType.BKREPO.value:
            return storage(expired=ASYNC_EXPORT_EXPIRED)
        return storage(
            toggle.get("qcloud_secret_id"),
            toggle.get("qcloud_secret_key"),
            toggle.get("qcloud_cos_region"),
            toggle.get("qcloud_cos_bucket"),
            ASYNC_EXPORT_EXPIRED,
        )

    @classmethod
    def _init_notify_type(cls):
        notify_type = FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_COMMON).feature_config.get(
            FEATURE_ASYNC_EXPORT_NOTIFY_TYPE
        )
        return NotifyType.get_instance(notify_type=notify_type)()
