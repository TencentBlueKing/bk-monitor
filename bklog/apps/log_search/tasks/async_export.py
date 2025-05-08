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
import datetime
import json
import os
import tarfile

import arrow
import pytz
import ujson
from blueapps.contrib.celery_tools.periodic import periodic_task
from blueapps.core.celery.celery import app
from celery.schedules import crontab
from django.conf import settings
from django.utils import timezone, translation
from django.utils.crypto import get_random_string
from django.utils.translation import gettext as _

from apps.constants import RemoteStorageType
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.log_search.constants import (
    ASYNC_APP_CODE,
    ASYNC_DIR,
    ASYNC_EXPORT_EMAIL_ERR_TEMPLATE,
    ASYNC_EXPORT_EMAIL_TEMPLATE,
    ASYNC_EXPORT_EXPIRED,
    ASYNC_EXPORT_FILE_EXPIRED_DAYS,
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_EXTERNAL,
    FEATURE_ASYNC_EXPORT_NOTIFY_TYPE,
    FEATURE_ASYNC_EXPORT_STORAGE_TYPE,
    ExportStatus,
    MsgModel,
)
from apps.log_search.exceptions import PreCheckAsyncExportException
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.log_search.models import (
    AsyncTask,
    LogIndexSet,
    Scenario,
    StorageClusterRecord,
)
from apps.utils.local import get_local_param
from apps.utils.log import logger
from apps.utils.notify import NotifyType
from apps.utils.remote_storage import StorageType
from apps.utils.thread import MultiExecuteFunc


@app.task(ignore_result=True, queue="async_export")
def async_export(
    search_handler: SearchHandler,
    sorted_fields: list,
    async_task_id: int,
    url_path: str,
    search_url_path: str,
    language: str,
    is_external: bool = False,
    is_quick_export: bool = False,
    export_file_type: str = "txt",
    external_user_email: str = "",
    unify_query_handler: UnifyQueryHandler = None,
):
    """
    异步导出任务
    @param search_handler {SearchHandler}
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
    file_name = f"{ASYNC_APP_CODE}_{search_handler.index_set_id}_{time_now}_{random_hash}"
    tar_file_name = f"{file_name}.tar.gz"
    async_task = AsyncTask.objects.filter(id=async_task_id).first()
    async_export_util = AsyncExportUtils(
        search_handler=search_handler,
        sorted_fields=sorted_fields,
        file_name=file_name,
        tar_file_name=tar_file_name,
        is_external=is_external,
        is_quick_export=is_quick_export,
        export_file_type=export_file_type,
        external_user_email=external_user_email,
        unify_query_handler=unify_query_handler,
    )
    try:
        if not async_task:
            logger.error(f"Can not find this: id: {async_task_id} record")
            raise BaseException(f"Can not find this: id: {async_task_id} record")

        async_task.export_status = ExportStatus.DOWNLOAD_LOG
        try:
            async_export_util.export_package()
        except Exception as e:  # pylint: disable=broad-except
            async_task = set_failed_status(async_task=async_task, reason=f"export package error: {e}")
            raise

        async_task.export_status = ExportStatus.EXPORT_PACKAGE
        async_task.file_name = tar_file_name
        async_task.file_size = async_export_util.get_file_size()
        try:
            async_export_util.export_upload()
        except Exception as e:  # pylint: disable=broad-except
            async_task = set_failed_status(async_task=async_task, reason=f"export upload error: {e}")
            raise

        async_task.export_status = ExportStatus.EXPORT_UPLOAD
        try:
            url = async_export_util.generate_download_url(url_path=url_path)
        except Exception as e:  # pylint: disable=broad-except
            async_task = set_failed_status(async_task=async_task, reason=f"generate download url error: {e}")
            raise

        async_task.download_url = url

        try:
            async_export_util.send_msg(
                index_set_id=search_handler.index_set_id,
                async_task=async_task,
                search_url_path=search_url_path,
                language=language,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"async_task_id:{async_task_id}, send msg error: {e}")

    except Exception as e:  # pylint: disable=broad-except
        logger.exception(e)
        async_export_util.send_msg(
            index_set_id=search_handler.index_set_id,
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


@periodic_task(run_every=crontab(minute="10", hour="3"))
def clean_expired_status():
    """
    change success status -> export_expired status
    """

    AsyncTask.objects.filter(export_status=ExportStatus.SUCCESS).filter(
        completed_at__lt=arrow.now().shift(seconds=-ASYNC_EXPORT_EXPIRED).datetime
    ).update(export_status=ExportStatus.DOWNLOAD_EXPIRED)


@periodic_task(run_every=crontab(minute="0", hour="3"))
def clean_expired_task():
    """
    clean expired task file
    expired_time:  2days

    """
    day_ago = datetime.datetime.now(pytz.timezone("UTC")) - datetime.timedelta(days=ASYNC_EXPORT_FILE_EXPIRED_DAYS)
    # 获取过期的内网下载文件
    expired_task_list = AsyncTask.objects.filter(created_at__lt=day_ago, is_clean=False)
    # nfs文件需要进行定期清理操作
    storage_type = FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_COMMON).feature_config.get(
        FEATURE_ASYNC_EXPORT_STORAGE_TYPE
    )

    if storage_type or storage_type == RemoteStorageType.NFS.value:
        # 删除NFS文件
        for expired_task in expired_task_list:
            target_file_dir = os.path.join(settings.EXTRACT_SAAS_STORE_DIR, expired_task.file_name)
            if os.path.isfile(target_file_dir):
                os.remove(os.path.abspath(target_file_dir))
            expired_task.is_clean = True
            expired_task.save()


class AsyncExportUtils:
    """
    async export utils(export_package, export_upload, generate_download_url, send_msg, clean_package)
    """

    def __init__(
        self,
        search_handler: SearchHandler,
        sorted_fields: list,
        file_name: str,
        tar_file_name: str,
        is_external: bool = False,
        is_quick_export: bool = False,
        export_file_type: str = "txt",
        external_user_email: str = "",
        unify_query_handler: UnifyQueryHandler = None,
    ):
        """
        @param search_handler: the handler cls to search
        @param sorted_fields: the fields to sort search result
        @param file_name: the export file name
        @param tar_file_name: the file name which will be tar
        @param is_external: is external_request
        """
        self.search_handler = search_handler
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
        self.unify_query_handler = unify_query_handler

    def export_package(self):
        """
        检索结果文件打包
        """
        if not (os.path.exists(ASYNC_DIR) and os.path.isdir(ASYNC_DIR)):
            os.makedirs(ASYNC_DIR)
        export_method = self.quick_export if self.is_quick_export else self.async_export
        export_method()

    def process_time(self, time_value, tz_info):
        """
        处理时间值并返回转换后的 datetime 对象
        """
        if isinstance(time_value, (int, float)):
            return arrow.get(time_value).to(tz=tz_info).datetime
        else:
            return arrow.get(time_value).replace(tzinfo=tz_info).datetime

    def get_storage_cluster_record(self):
        """
        获取集群切换记录
        """
        tz_info = pytz.timezone(get_local_param("time_zone", settings.TIME_ZONE))
        start_time = self.process_time(self.search_handler.start_time, tz_info)
        end_time = self.process_time(self.search_handler.end_time, tz_info)
        storage_cluster_record_objs = StorageClusterRecord.objects.filter(
            index_set_id=int(self.search_handler.index_set_id),
            created_at__gt=(start_time - datetime.timedelta(hours=1)),
        ).order_by("created_at")
        max_created_at = None
        for obj in storage_cluster_record_objs:
            if end_time <= obj.created_at:
                max_created_at = obj.created_at
                break
        if max_created_at:
            storage_cluster_record_objs = storage_cluster_record_objs.filter(created_at__lte=max_created_at)
            storage_cluster_ids = set(storage_cluster_record_objs.values_list("storage_cluster_id", flat=True))
        else:
            storage_cluster_ids = set(storage_cluster_record_objs.values_list("storage_cluster_id", flat=True))
            storage_cluster_ids.add(self.search_handler.storage_cluster_id)
        return storage_cluster_ids

    def _unify_query_async_export(self, file_path, **kwargs):
        try:
            index_set = self.unify_query_handler.index_info_list[0]["index_set_obj"]
            max_result_window = index_set.result_window
            result = self.unify_query_handler.pre_get_result(sorted_fields=self.sorted_fields, size=max_result_window)
            with open(file_path, "a+", encoding="utf-8") as f:
                result_list = self.unify_query_handler._deal_query_result(result_dict=result).get("origin_log_list")
                for item in result_list:
                    f.write("%s\n" % ujson.dumps(item, ensure_ascii=False))
                generate_result = self.unify_query_handler.search_after_result(result, self.sorted_fields)
                self.write_file(f, generate_result)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("async export error: index_set_id: %s, reason: %s", index_set.index_set_id, e)
            raise e

        return file_path

    def _async_export(self, search_handler, file_path):
        try:
            max_result_window = search_handler.index_set.result_window
            result = search_handler.pre_get_result(sorted_fields=self.sorted_fields, size=max_result_window)
            # 判断是否成功
            if result["_shards"]["total"] != result["_shards"]["successful"]:
                logger.error("can not create async_export task, reason: {}".format(result["_shards"]["failures"]))
                raise PreCheckAsyncExportException()
            with open(file_path, "a+", encoding="utf-8") as f:
                result_list = search_handler._deal_query_result(result_dict=result).get("origin_log_list")
                for item in result_list:
                    f.write("%s\n" % ujson.dumps(item, ensure_ascii=False))
                if search_handler.scenario_id == Scenario.ES:
                    generate_result = search_handler.scroll_result(result)
                else:
                    generate_result = search_handler.search_after_result(result, self.sorted_fields)
                self.write_file(f, generate_result)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception("async export error: index_set_id: %s, reason: %s", search_handler.index_set_id, e)
            raise e

        return file_path

    def async_export(self):
        storage_cluster_record_ids = self.get_storage_cluster_record()
        multi_execute_func = MultiExecuteFunc()
        for storage_cluster_record_id in storage_cluster_record_ids:
            search_handler = SearchHandler(
                index_set_id=self.search_handler.index_set_id,
                search_dict=copy.deepcopy(self.search_handler.search_dict),
                export_fields=self.search_handler.export_fields,
                export_log=True,
            )
            search_handler.storage_cluster_id = storage_cluster_record_id
            current_cluster_id = search_handler.storage_cluster_id
            file_path = f"{ASYNC_DIR}/{self.file_name}_cluster_{current_cluster_id}.{self.export_file_type}"
            params = {
                "search_handler": search_handler,
                "file_path": file_path,
            }
            func = self._unify_query_async_export if self.unify_query_handler else self._async_export
            multi_execute_func.append(
                result_key=search_handler.storage_cluster_id,
                func=func,
                params=params,
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

    def _quick_export(self, search_handler):
        multi_result = search_handler.multi_get_slice_data(
            pre_file_name=self.file_name, export_file_type=self.export_file_type
        )
        for idx, result in multi_result.items():
            if isinstance(result, Exception):
                logger.exception("quick export error: %s -- %s, reason: %s", self.file_name, idx, result)
            else:
                self.file_path_list.append(result)

    def quick_export(self):
        storage_cluster_record_ids = self.get_storage_cluster_record()
        for storage_cluster_record_id in storage_cluster_record_ids:
            self.search_handler.storage_cluster_id = storage_cluster_record_id
            self._quick_export(self.search_handler)
        with tarfile.open(self.tar_file_path, "w:gz") as tar:
            for file_path in self.file_path_list:
                tar.add(file_path, arcname=os.path.basename(file_path))

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
                f.write("%s\n" % ujson.dumps(item))
