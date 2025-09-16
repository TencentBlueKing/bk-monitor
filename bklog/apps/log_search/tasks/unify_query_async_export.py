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

import copy
import json
import os
import tarfile

import arrow
import ujson
from blueapps.core.celery.celery import app
from django.conf import settings
from django.utils import timezone, translation
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _

from apps.constants import RemoteStorageType
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import UNIFY_QUERY_SEARCH
from apps.log_search.constants import (
    ASYNC_APP_CODE,
    ASYNC_DIR,
    ASYNC_EXPORT_EMAIL_ERR_TEMPLATE,
    ASYNC_EXPORT_EMAIL_TEMPLATE,
    ASYNC_EXPORT_EXPIRED,
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_EXTERNAL,
    FEATURE_ASYNC_EXPORT_NOTIFY_TYPE,
    FEATURE_ASYNC_EXPORT_STORAGE_TYPE,
    ExportStatus,
    MsgModel,
    SCROLL,
)
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_search.models import (
    AsyncTask,
    LogIndexSet,
)
from apps.utils.log import logger
from apps.utils.notify import NotifyType
from apps.utils.remote_storage import StorageType
from apps.utils.thread import MultiExecuteFunc


@app.task(ignore_result=True, queue="async_export")
def async_export(
    unify_query_handler: UnifyQueryHandler,
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
    """
    异步导出任务
    @param unify_query_handler {UnifyQueryHandler}
    @param sorted_fields {List}
    @param async_task_id {Int}
    @param url_path {Str}
    @param search_url_path {Str}
    @param language {Str}
    @param is_external {Bool}
    @param is_quick_export {Bool}
    @param export_file_type {str}
    @param external_user_email {Str}
    @param unify_query_handler: {UnifyQueryHandler}
    """
    index_set_id = unify_query_handler.index_info_list[0]["index_set_id"]
    random_hash = get_random_string(length=10)
    time_now = arrow.now().format("YYYYMMDDHHmmss")
    file_name = f"{ASYNC_APP_CODE}_{index_set_id}_{time_now}_{random_hash}"
    tar_file_name = f"{file_name}.tar.gz"
    async_task = AsyncTask.objects.filter(id=async_task_id).first()
    async_export_util = AsyncExportUtils(
        unify_query_handler=unify_query_handler,
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
            logger.error(f"Can not find this: id: {async_task_id} record")
            raise BaseException(f"Can not find this: id: {async_task_id} record")

        async_task.export_status = ExportStatus.DOWNLOAD_LOG
        async_task.save()
        try:
            async_export_util.export_package()
        except Exception as e:  # pylint: disable=broad-except
            async_task = set_failed_status(async_task=async_task, reason=f"export package error: {e}")
            raise

        async_task.export_status = ExportStatus.EXPORT_PACKAGE
        async_task.file_name = tar_file_name
        async_task.file_size = async_export_util.get_file_size()
        async_task.save()
        try:
            async_export_util.export_upload()
        except Exception as e:  # pylint: disable=broad-except
            async_task = set_failed_status(async_task=async_task, reason=f"export upload error: {e}")
            raise

        async_task.export_status = ExportStatus.EXPORT_UPLOAD
        async_task.save()
        try:
            url = async_export_util.generate_download_url(url_path=url_path)
        except Exception as e:  # pylint: disable=broad-except
            async_task = set_failed_status(async_task=async_task, reason=f"generate download url error: {e}")
            raise

        async_task.download_url = url

        try:
            async_export_util.send_msg(
                index_set_id=index_set_id,
                async_task=async_task,
                search_url_path=search_url_path,
                language=language,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"async_task_id:{async_task_id}, send msg error: {e}")

    except Exception as e:  # pylint: disable=broad-except
        logger.exception(e)
        async_export_util.send_msg(
            index_set_id=index_set_id,
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

    async_export_util.clean_package()
    # 过$ASYNC_EXPORT_EXPIRED将对应状态置为ExportStatus.EXPIRED
    set_expired_status.apply_async(args=[async_task.id], countdown=ASYNC_EXPORT_EXPIRED)


@app.task(ignore_result=True, queue="async_export")
def union_async_export(
    unify_query_handler: UnifyQueryHandler,
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
    """
    异步导出任务
    @param unify_query_handler {UnifyQueryHandler}
    @param sorted_fields {List}
    @param async_task_id {Int}
    @param url_path {Str}
    @param search_url_path {Str}
    @param language {Str}
    @param is_external {Bool}
    @param is_quick_export {Bool}
    @param export_file_type {str}
    @param external_user_email {Str}
    @param unify_query_handler: {UnifyQueryHandler}
    """
    random_hash = get_random_string(length=10)
    time_now = arrow.now().format("YYYYMMDDHHmmss")
    file_name = f"{ASYNC_APP_CODE}_{time_now}_{random_hash}"
    tar_file_name = f"{file_name}.tar.gz"
    async_task = AsyncTask.objects.filter(id=async_task_id).first()
    async_export_util = UnionAsyncExportUtils(
        unify_query_handler=unify_query_handler,
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
            logger.error(f"Can not find this: id: {async_task_id} record")
            raise BaseException(f"Can not find this: id: {async_task_id} record")

        async_task.export_status = ExportStatus.DOWNLOAD_LOG
        async_task.save()
        try:
            async_export_util.export_package()
        except Exception as e:  # pylint: disable=broad-except
            async_task = set_failed_status(async_task=async_task, reason=f"export package error: {e}")
            raise

        async_task.export_status = ExportStatus.EXPORT_PACKAGE
        async_task.file_name = tar_file_name
        async_task.file_size = async_export_util.get_file_size()
        async_task.save()
        try:
            async_export_util.export_upload()
        except Exception as e:  # pylint: disable=broad-except
            async_task = set_failed_status(async_task=async_task, reason=f"export upload error: {e}")
            raise

        async_task.export_status = ExportStatus.EXPORT_UPLOAD
        async_task.save()
        try:
            url = async_export_util.generate_download_url(url_path=url_path)
        except Exception as e:  # pylint: disable=broad-except
            async_task = set_failed_status(async_task=async_task, reason=f"generate download url error: {e}")
            raise

        async_task.download_url = url

        try:
            async_export_util.send_msg(
                index_set_ids=unify_query_handler.index_set_ids,
                async_task=async_task,
                search_url_path=search_url_path,
                language=language,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"async_task_id:{async_task_id}, send msg error: {e}")

    except Exception as e:  # pylint: disable=broad-except
        logger.exception(e)
        async_export_util.send_msg(
            index_set_ids=unify_query_handler.index_set_ids,
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

    async_export_util.clean_package()
    # 过$ASYNC_EXPORT_EXPIRED将对应状态置为ExportStatus.EXPIRED
    set_expired_status.apply_async(args=[async_task.id], countdown=ASYNC_EXPORT_EXPIRED)


def set_failed_status(async_task: AsyncTask, reason):
    async_task.failed_reason = reason
    async_task.export_status = ExportStatus.FAILED
    logger.error(async_task.failed_reason)
    async_task.save()
    return async_task


@app.task(ignore_result=True, queue="async_export")
def set_expired_status(async_task_id):
    async_task = AsyncTask.objects.get(id=async_task_id)
    async_task.export_status = ExportStatus.DOWNLOAD_EXPIRED
    async_task.save()


class BaseExportUtils:
    def __init__(
        self,
        unify_query_handler: UnifyQueryHandler,
        sorted_fields: list,
        file_name: str,
        tar_file_name: str,
        is_external: bool = False,
        is_quick_export: bool = False,
        export_file_type: str = "txt",
        external_user_email: str = "",
    ):
        """
        @param unify_query_handler: the handler cls to search
        @param sorted_fields: the fields to sort search result
        @param file_name: the export file name
        @param tar_file_name: the file name which will be tar
        @param is_external: is external_request
        """
        self.unify_query_handler = unify_query_handler
        self.sorted_fields = sorted_fields
        self.file_name = file_name
        self.tar_file_name = tar_file_name
        self.is_external = is_external
        self.is_quick_export = is_quick_export
        self.export_file_type = export_file_type
        self.external_user_email = external_user_email
        self.file_path = f"{ASYNC_DIR}/{self.file_name}.{self.export_file_type}"
        self.tar_file_path = f"{ASYNC_DIR}/{self.tar_file_name}"
        self.storage = self.init_remote_storage()
        self.notify = self.init_notify_type()
        self.file_path_list = []

    def export_upload(self):
        """
        文件上传
        """
        self.storage.export_upload(file_path=self.tar_file_path, file_name=self.tar_file_name)

    def generate_download_url(self, url_path: str):
        """
        生成url
        """
        return self.storage.generate_download_url(url_path=url_path, file_name=self.tar_file_name)

    def clean_package(self):
        """
        清空产生的临时文件
        """
        for file_path in self.file_path_list:
            os.remove(file_path)
        os.remove(self.tar_file_path)

    def init_remote_storage(self):
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

    def get_file_size(self):
        """
        获取文件大小 单位：m，保留小数2位
        """
        return max(round(os.path.getsize(self.tar_file_path) / float(1024 * 1024), 2), 0.01)

    @classmethod
    def init_notify_type(cls):
        notify_type = FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_COMMON).feature_config.get(
            FEATURE_ASYNC_EXPORT_NOTIFY_TYPE
        )

        return NotifyType.get_instance(notify_type=notify_type)()

    @classmethod
    def write_file(cls, f, result):
        """
        将对应数据写到文件中
        """
        for res in result:
            origin_result_list = res.get("origin_log_list")
            for item in origin_result_list:
                f.write(f"{ujson.dumps(item, ensure_ascii=False)}\n")

    def fetch_data_and_package(self):
        summary_file_path = f"{ASYNC_DIR}/{self.file_name}_summary.{self.export_file_type}"

        with open(summary_file_path, "a+", encoding="utf-8") as f:
            generate_result = self.unify_query_handler.export_data(is_quick_export=self.is_quick_export)
            self.write_file(f, generate_result)

        with tarfile.open(self.tar_file_path, "w:gz") as tar:
            tar.add(summary_file_path, arcname=os.path.basename(summary_file_path))
            self.file_path_list.append(summary_file_path)


class AsyncExportUtils(BaseExportUtils):
    """
    async export utils(export_package, export_upload, generate_download_url, send_msg, clean_package)
    """

    def export_package(self):
        """
        检索结果文件打包
        """
        if not (os.path.exists(ASYNC_DIR) and os.path.isdir(ASYNC_DIR)):
            os.makedirs(ASYNC_DIR)
        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, self.unify_query_handler.bk_biz_id):
            self.fetch_data_and_package()
        else:
            export_method = self.quick_export if self.is_quick_export else self.async_export
            export_method()

    def _async_export(self, file_path):
        try:
            index_set = self.unify_query_handler.index_info_list[0]["index_set_obj"]
            max_result_window = index_set.result_window
            result = self.unify_query_handler.pre_get_result(sorted_fields=self.sorted_fields, size=max_result_window)
            with open(file_path, "a+", encoding="utf-8") as f:
                result_list = self.unify_query_handler._deal_query_result(result_dict=result).get("origin_log_list")
                for item in result_list:
                    f.write(f"{ujson.dumps(item, ensure_ascii=False)}\n")
                generate_result = self.unify_query_handler.search_after_result(result, self.sorted_fields)
                self.write_file(f, generate_result)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("async export error: index_set_id: %s, reason: %s", index_set.index_set_id, e)
            raise e

        return file_path

    def async_export(self):
        summary_file_path = f"{ASYNC_DIR}/{self.file_name}_summary.{self.export_file_type}"
        result = self._async_export(file_path=summary_file_path)
        self.file_path_list.append(result)
        with tarfile.open(self.tar_file_path, "w:gz") as tar:
            tar.add(summary_file_path, arcname=os.path.basename(summary_file_path))
            self.file_path_list.append(summary_file_path)

    def _quick_export(self):
        try:
            index_set = self.unify_query_handler.index_info_list[0]["index_set_obj"]
            max_result_window = index_set.result_window
            file_path = f"{ASYNC_DIR}/{self.file_name}_summary.{self.export_file_type}"
            result = self.unify_query_handler.pre_get_result(
                sorted_fields=self.sorted_fields, size=max_result_window, scroll=SCROLL
            )
            with open(file_path, "a+", encoding="utf-8") as f:
                result_list = self.unify_query_handler._deal_query_result(result_dict=result).get("origin_log_list")
                for item in result_list:
                    f.write(f"{ujson.dumps(item, ensure_ascii=False)}\n")
                generate_result = self.unify_query_handler.scroll_search(result)
                self.write_file(f, generate_result)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("async export error: index_set_id: %s, reason: %s", index_set.index_set_id, e)
            raise e

        return file_path

    def quick_export(self):
        result = self._quick_export()
        self.file_path_list.append(result)
        with tarfile.open(self.tar_file_path, "w:gz") as tar:
            for file_path in self.file_path_list:
                tar.add(file_path, arcname=os.path.basename(file_path))

    def send_msg(
        self,
        index_set_id: int,
        async_task: AsyncTask,
        search_url_path: str,
        language: str,
        name: str = ASYNC_EXPORT_EMAIL_TEMPLATE,
        title_model: str = MsgModel.NORMAL,
    ):
        """
        发送邮件
        """
        index_set_obj = LogIndexSet.objects.get(index_set_id=index_set_id)

        platform = settings.EMAIL_TITLE["en"] if translation.get_language() == "en" else settings.EMAIL_TITLE["zh"]

        title = self.notify.title(
            self.generate_title_template(title_model=title_model),
            platform=platform,
            index_set_name=index_set_obj.index_set_name,
        )

        content = self.notify.content(
            name=name,
            file={
                "platform": platform,
                "created_at": arrow.now().format("YYYY-MM-DD HH:mm:ss"),
                "index_set_name": index_set_obj.index_set_name,
                "index": ",".join([index["result_table_id"].replace(".", "_") for index in index_set_obj.indexes]),
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

    @classmethod
    def generate_title_template(cls, title_model):
        title_template_map = {
            MsgModel.NORMAL: _("【{platform}】{index_set_name} 检索导出"),
            MsgModel.ABNORMAL: _("【{platform}】{index_set_name} 检索导出失败"),
        }
        return title_template_map.get(title_model, title_template_map.get(MsgModel.NORMAL))


class UnionAsyncExportUtils(BaseExportUtils):
    """
    union query async export utils(export_package, export_upload, generate_download_url, send_msg, clean_package)
    """

    def export_package(self):
        """
        检索结果文件打包
        """
        if not (os.path.exists(ASYNC_DIR) and os.path.isdir(ASYNC_DIR)):
            os.makedirs(ASYNC_DIR)
        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, self.unify_query_handler.bk_biz_id):
            self.fetch_data_and_package()
        else:
            self.async_export()

    def _async_export(self, file_path, unify_query_handler: UnifyQueryHandler):
        try:
            index_set = unify_query_handler.index_info_list[0]["index_set_obj"]
            max_result_window = index_set.result_window
            result = unify_query_handler.pre_get_result(sorted_fields=self.sorted_fields, size=max_result_window)
            with open(file_path, "a+", encoding="utf-8") as f:
                result_list = unify_query_handler._deal_query_result(result_dict=result).get("origin_log_list")
                for item in result_list:
                    f.write(f"{ujson.dumps(item, ensure_ascii=False)}\n")
                generate_result = unify_query_handler.search_after_result(result, self.sorted_fields)
                self.write_file(f, generate_result)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("async export error: index_set_id: %s, reason: %s", index_set.index_set_id, e)
            raise e

        return file_path

    def async_export(self):
        index_info_list = copy.deepcopy(self.unify_query_handler.index_info_list)
        multi_execute_func = MultiExecuteFunc()
        export_method = self._quick_export if self.is_quick_export else self._async_export
        for index_info in index_info_list:
            self.unify_query_handler.index_info_list = [index_info]
            # 基础查询参数初始化
            self.unify_query_handler.base_dict = self.unify_query_handler.init_base_dict()
            index_set_id = index_info["index_set_id"]
            file_path = f"{ASYNC_DIR}/{self.file_name}_{index_set_id}.{self.export_file_type}"
            multi_execute_func.append(
                result_key=index_set_id,
                func=export_method,
                params={"file_path": file_path, "unify_query_handler": copy.deepcopy(self.unify_query_handler)},
                multi_func_params=True,
            )
        multi_result = multi_execute_func.run(return_exception=True)
        summary_file_path = f"{ASYNC_DIR}/{self.file_name}_summary.{self.export_file_type}"
        with open(summary_file_path, "a+", encoding="utf-8") as summary_file:
            for result_key, result in multi_result.items():
                if isinstance(result, Exception):
                    logger.exception("async export error: %s -- %s, reason: %s", self.file_name, result_key, result)
                else:
                    self.file_path_list.append(result)
                    # 读取文件内容并写入汇总文件
                    with open(result, encoding="utf-8") as f:
                        for line in f:
                            summary_file.write(line)
        with tarfile.open(self.tar_file_path, "w:gz") as tar:
            tar.add(summary_file_path, arcname=os.path.basename(summary_file_path))
            self.file_path_list.append(summary_file_path)

    def _quick_export(self, file_path, unify_query_handler: UnifyQueryHandler):
        try:
            index_set = unify_query_handler.index_info_list[0]["index_set_obj"]
            max_result_window = index_set.result_window
            result = unify_query_handler.pre_get_result(
                sorted_fields=self.sorted_fields, size=max_result_window, scroll=SCROLL
            )
            with open(file_path, "a+", encoding="utf-8") as f:
                result_list = unify_query_handler._deal_query_result(result_dict=result).get("origin_log_list")
                for item in result_list:
                    f.write(f"{ujson.dumps(item, ensure_ascii=False)}\n")
                generate_result = unify_query_handler.scroll_search(result)
                self.write_file(f, generate_result)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("async export error: index_set_id: %s, reason: %s", index_set.index_set_id, e)
            raise e

        return file_path

    def send_msg(
        self,
        index_set_ids: list,
        async_task: AsyncTask,
        search_url_path: str,
        language: str,
        name: str = ASYNC_EXPORT_EMAIL_TEMPLATE,
        title_model: str = MsgModel.NORMAL,
    ):
        """
        发送邮件
        """
        index_set_objs = LogIndexSet.objects.filter(index_set_id__in=index_set_ids)
        index_set_names = ",".join([obj.index_set_name for obj in index_set_objs])
        platform = settings.EMAIL_TITLE["en"] if translation.get_language() == "en" else settings.EMAIL_TITLE["zh"]
        title = self.notify.title(
            self.generate_title_template(title_model=title_model),
            platform=platform,
            index_set_names=index_set_names,
        )
        indexs = []
        for index_set_obj in index_set_objs:
            indexs.append(",".join([index["result_table_id"].replace(".", "_") for index in index_set_obj.indexes]))
        content = self.notify.content(
            name=name,
            file={
                "platform": platform,
                "created_at": arrow.now().format("YYYY-MM-DD HH:mm:ss"),
                "index_set_name": index_set_names,
                "index": indexs,
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

    @classmethod
    def generate_title_template(cls, title_model):
        title_template_map = {
            MsgModel.NORMAL: _("【{platform}】【{index_set_names}】 检索导出"),
            MsgModel.ABNORMAL: _("【{platform}】【{index_set_names}】 检索导出失败"),
        }
        return title_template_map.get(title_model, title_template_map.get(MsgModel.NORMAL))
