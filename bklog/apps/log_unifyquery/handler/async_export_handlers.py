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
from concurrent.futures import ThreadPoolExecutor

import arrow
from django.conf import settings
from django.utils.http import urlencode
from rest_framework.reverse import reverse

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import UNIFY_QUERY_SEARCH
from apps.log_databus.models import CollectorConfig
from apps.log_search.constants import (
    ASYNC_COUNT_SIZE,
    MAX_GET_ATTENTION_SIZE,
    ExportStatus,
    ExportType,
    IndexSetType,
)
from apps.log_search.exceptions import (
    BKBaseExportException,
    MissAsyncExportException,
    PreCheckAsyncExportException,
    DuplicateUnifyQueryExportException,
)
from apps.log_search.handlers.search.search_handlers_esquery import SearchHandler
from apps.log_search.models import AsyncTask, LogIndexSet, Scenario
from apps.log_unifyquery.handler.base import UnifyQueryHandler
from apps.models import model_to_dict
from apps.utils.db import array_chunk
from apps.utils.drf import DataPageNumberPagination
from apps.utils.local import (
    get_request,
    get_request_app_code,
    get_request_external_user_email,
    get_request_external_username,
    get_request_language_code,
    get_request_username,
)
from apps.utils.log import logger
from bkm_space.utils import bk_biz_id_to_space_uid
from apps.log_search.tasks.unify_query_async_export import async_export, union_async_export


class UnifyQueryAsyncExportHandlers:
    def __init__(
        self,
        index_set_id: int = None,
        bk_biz_id=None,
        search_dict: dict = None,
        export_fields=None,
        index_set_ids: list = None,
        export_file_type: str = "txt",
    ):
        self.index_set_id = index_set_id
        self.bk_biz_id = bk_biz_id
        self.index_set_ids = index_set_ids
        self.search_dict = search_dict
        search_dict = copy.deepcopy(self.search_dict)
        search_dict["index_set_ids"] = [index_set_id]
        search_dict["export_fields"] = export_fields
        self.unify_query_handler = UnifyQueryHandler(search_dict)
        self.request_user = get_request_external_username() or get_request_username()
        self.is_external = bool(get_request_external_username())
        self.export_file_type = export_file_type

    def async_export(self, is_quick_export: bool = False):
        # 判断是否存在 正在下载的相同检索参数的导出任务
        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, self.bk_biz_id):
            if AsyncTask.objects.filter(
                request_param=self.search_dict,
                created_by=self.request_user,
                export_status=ExportStatus.DOWNLOAD_LOG,
            ).exists():
                raise DuplicateUnifyQueryExportException()
        # 计算平台暂不支持快速下载
        if is_quick_export and self.unify_query_handler.index_info_list[0]["scenario_id"] == Scenario.BKDATA:
            raise BKBaseExportException()
        # 判断fields是否支持
        fields = self._pre_check_fields()
        # 获取排序字段
        sorted_list = self.unify_query_handler._get_user_sorted_list(fields["async_export_fields"])
        result = self.unify_query_handler.pre_get_result(
            sorted_fields=sorted_list,
            size=ASYNC_COUNT_SIZE,
        )
        # 判断是否进行导出
        if not result["list"]:
            logger.error("can not create async_export task, reason: no data")
            raise PreCheckAsyncExportException()

        async_task = AsyncTask.objects.create(
            **{
                "request_param": self.search_dict,
                "sorted_param": fields["async_export_fields"],
                "scenario_id": self.unify_query_handler.index_info_list[0]["scenario_id"],
                "index_set_id": self.index_set_id,
                "bk_biz_id": self.bk_biz_id,
                "start_time": self.search_dict["start_time"],
                "end_time": self.search_dict["end_time"],
                "export_type": ExportType.ASYNC,
                "created_by": self.request_user,
            }
        )

        url = self._get_url()
        search_url = self._get_search_url()

        async_export.delay(
            unify_query_handler=self.unify_query_handler,
            sorted_fields=sorted_list,
            async_task_id=async_task.id,
            url_path=url,
            search_url_path=search_url,
            language=get_request_language_code(),
            is_external=self.is_external,
            is_quick_export=is_quick_export,
            export_file_type=self.export_file_type,
            external_user_email=get_request_external_user_email(),
        )
        return async_task.id, self.search_dict.get("size", 30)

    def _pre_check_fields(self):
        fields = self.unify_query_handler.fields()
        for config in fields["config"]:
            if config["name"] == "async_export":
                if not config["is_active"]:
                    raise MissAsyncExportException(config["extra"]["usable_reason"])
                return {"async_export_fields": config["extra"]["fields"]}

    def _get_url(self):
        url = reverse("tasks-download-file", request=get_request())
        return url

    def _get_search_url(self):
        request = get_request()
        search_dict = copy.deepcopy(self.search_dict)
        if "host_scopes" in search_dict:
            search_dict["host_scopes"] = json.dumps(search_dict["host_scopes"])

        if "addition" in search_dict:
            search_dict["addition"] = json.dumps(search_dict["addition"])

        if "bk_biz_id" in search_dict:
            search_dict["bizId"] = search_dict["bk_biz_id"]
            search_dict["spaceUid"] = bk_biz_id_to_space_uid(search_dict["bk_biz_id"])

        url_params = urlencode(search_dict)
        # 这里是为了拼接前端检索请求
        search_url = (
            f"{request.scheme}://{request.get_host()}{settings.SITE_URL}#/retrieve/{self.index_set_id}?{url_params}"
        )
        return search_url

    def get_export_history(self, request, view, show_all=False, is_union_search=False):
        # 这里当show_all为true的时候则给前端返回当前业务全部导出历史
        source_app_code = get_request_app_code()
        external_username = get_request_external_username()
        query_set = AsyncTask.objects.filter(bk_biz_id=self.bk_biz_id, source_app_code=source_app_code)
        # 外部用户只能看到自己的导出历史
        if external_username:
            query_set = query_set.filter(created_by=external_username)
        if is_union_search:
            query_set = query_set.filter(index_set_type=IndexSetType.UNION.value)
            if not show_all:
                query_set = query_set.filter(index_set_ids=self.index_set_ids)
        else:
            # 这里当show_all为true的时候则给前端返回当前业务全部导出历史
            query_set = query_set.filter(index_set_type=IndexSetType.SINGLE.value)
            if not show_all:
                query_set = query_set.filter(index_set_id=self.index_set_id)
        pg = DataPageNumberPagination()
        page_export_task_history = pg.paginate_queryset(
            queryset=query_set.order_by("-created_at", "created_by"), request=request, view=view
        )
        index_set_retention = self.get_index_set_retention(
            index_set_ids=[history.index_set_id for history in page_export_task_history]
        )
        res = pg.get_paginated_response(
            [
                self.generate_export_history(
                    model_to_dict(history), index_set_retention, is_union_search=is_union_search
                )
                for history in page_export_task_history
            ]
        )
        return res

    @classmethod
    def generate_export_history(cls, export_task_history, index_set_retention, is_union_search=False):
        download_able = cls.judge_download_able(export_task_history["export_status"])
        retry_able = cls.judge_retry_able(
            export_task_history["end_time"], retention=index_set_retention.get(export_task_history["index_set_id"])
        )

        res = {
            "id": export_task_history["id"],
            "search_dict": export_task_history["request_param"],
            "start_time": export_task_history["start_time"],
            "end_time": export_task_history["end_time"],
            "export_type": export_task_history["export_type"],
            "export_status": export_task_history["export_status"] if retry_able else ExportStatus.DATA_EXPIRED,
            "error_msg": export_task_history["failed_reason"],
            "download_url": export_task_history["download_url"],
            "export_pkg_name": export_task_history["file_name"],
            "export_pkg_size": export_task_history["file_size"],
            "export_created_at": export_task_history["created_at"],
            "export_created_by": export_task_history["created_by"],
            "export_completed_at": export_task_history["completed_at"],
            "download_able": download_able,
            "retry_able": retry_able,
            "index_set_type": export_task_history["index_set_type"],
        }

        if not is_union_search:
            res.update({"log_index_set_id": export_task_history["index_set_id"]})
        else:
            res.update(
                {
                    "log_index_set_ids": export_task_history["index_set_ids"],
                }
            )

        return res

    @classmethod
    def judge_download_able(cls, status):
        if status == ExportStatus.DOWNLOAD_EXPIRED:
            return False
        return True

    @classmethod
    def judge_retry_able(cls, end_time, retention):
        if retention and end_time:
            return arrow.now() < arrow.get(end_time, tzinfo=settings.TIME_ZONE).shift(days=retention)
        return True

    @classmethod
    def get_index_set_retention(cls, index_set_ids):
        index_set_id_dict = cls.get_data_id(index_set_ids)
        data_id_retention_dict = cls.get_retention(list(index_set_id_dict.keys()))
        return {index_set_id_dict.get(data_id): retention for data_id, retention in data_id_retention_dict.items()}

    @classmethod
    def get_data_id(cls, index_set_ids: list):
        log_index_sets = LogIndexSet.objects.filter(index_set_id__in=index_set_ids)
        log_index_set_dict = {
            log_index_set.collector_config_id: log_index_set.index_set_id
            for log_index_set in log_index_sets
            if log_index_set.collector_config_id
        }
        collector_configs = CollectorConfig.objects.filter(collector_config_id__in=log_index_set_dict.keys())
        return {
            collector_config.bk_data_id: log_index_set_dict.get(collector_config.collector_config_id)
            for collector_config in collector_configs
        }

    @classmethod
    def get_retention(cls, data_ids):
        data_ids_array = array_chunk(data_ids, size=MAX_GET_ATTENTION_SIZE)
        result = {}
        for data_id_array in data_ids_array:
            with ThreadPoolExecutor() as executor:
                # 这里这样写是因为只有这种方式executor.map才能把kwargs传进去 方能cache的时候取到对应的key
                # https://stackoverflow.com/questions/59520376/how-to-use-executor-map-function-in-python-on-keyword-arguments
                res = executor.map(
                    lambda kwargs: CollectorConfig.get_data_id_conf(**kwargs),
                    [{"bk_data_id": data_id} for data_id in data_id_array],
                )
            for val in res:
                if not val["result_table_list"]:
                    continue
                result_table, *_ = val["result_table_list"]
                shipper, *_ = result_table["shipper_list"]
                result[val["bk_data_id"]] = shipper["storage_config"]["retention"]
        return result


class UnifyQueryUnionAsyncExportHandlers:
    def __init__(
        self,
        bk_biz_id=None,
        search_dict: dict = None,
        export_fields=None,
        index_set_ids: list = None,
        export_file_type: str = "txt",
    ):
        self.bk_biz_id = bk_biz_id
        self.index_set_ids = index_set_ids
        self.search_dict = search_dict
        search_dict = copy.deepcopy(self.search_dict)
        search_dict["index_set_ids"] = index_set_ids
        search_dict["export_fields"] = export_fields
        self.unify_query_handler = UnifyQueryHandler(search_dict)
        self.request_user = get_request_external_username() or get_request_username()
        self.is_external = bool(get_request_external_username())
        self.export_file_type = export_file_type

    def async_export(self, is_quick_export: bool = False):
        # 判断是否存在 正在下载的相同检索参数的导出任务
        if FeatureToggleObject.switch(UNIFY_QUERY_SEARCH, self.bk_biz_id):
            if AsyncTask.objects.filter(
                request_param=self.search_dict,
                created_by=self.request_user,
                export_status=ExportStatus.DOWNLOAD_LOG,
            ).exists():
                raise DuplicateUnifyQueryExportException()
        sort_fields_flag = []
        sort_fields_list = []
        # 计算平台暂不支持快速下载
        for index_info in self.unify_query_handler.index_info_list:
            if is_quick_export and index_info["scenario_id"] == Scenario.BKDATA:
                raise BKBaseExportException()
            index_set_id = index_info["index_set_id"]
            search_handler = SearchHandler(
                index_set_id=index_set_id,
                search_dict={
                    "start_time": self.search_dict.get("start_time"),
                    "end_time": self.search_dict.get("end_time"),
                },
            )
            # 判断fields是否支持
            fields = self._pre_check_fields(search_handler)
            # 获取排序字段
            sorted_list = search_handler._get_user_sorted_list(fields["async_export_fields"])
            # 整合排序字段
            for fields_list in sorted_list:
                field = fields_list[0]
                if field not in sort_fields_flag:
                    sort_fields_flag.append(field)
                    sort_fields_list.append(fields_list)
        result = self.unify_query_handler.pre_get_result(
            sorted_fields=sort_fields_list,
            size=ASYNC_COUNT_SIZE,
        )
        # 判断是否进行导出
        if not result["list"]:
            logger.error("can not create async_export task, reason: no data")
            raise PreCheckAsyncExportException()

        async_task = AsyncTask.objects.create(
            **{
                "request_param": self.search_dict,
                "sorted_param": sort_fields_list,
                "index_set_ids": self.index_set_ids,
                "index_set_type": IndexSetType.UNION.value,
                "bk_biz_id": self.bk_biz_id,
                "start_time": self.search_dict["start_time"],
                "end_time": self.search_dict["end_time"],
                "export_type": ExportType.ASYNC,
                "created_by": self.request_user,
            }
        )

        url = self._get_url()
        search_url = self._get_search_url()

        union_async_export.delay(
            unify_query_handler=self.unify_query_handler,
            sorted_fields=sort_fields_list,
            async_task_id=async_task.id,
            url_path=url,
            search_url_path=search_url,
            language=get_request_language_code(),
            is_external=self.is_external,
            is_quick_export=is_quick_export,
            export_file_type=self.export_file_type,
            external_user_email=get_request_external_user_email(),
        )
        return async_task.id, self.search_dict.get("size", 30)

    @staticmethod
    def _pre_check_fields(search_handler: SearchHandler):
        fields = search_handler.fields()
        for config in fields["config"]:
            if config["name"] == "async_export":
                if not config["is_active"]:
                    raise MissAsyncExportException(config["extra"]["usable_reason"])
                return {"async_export_fields": config["extra"]["fields"]}

    def _get_url(self):
        url = reverse("tasks-download-file", request=get_request())
        return url

    def _get_search_url(self):
        request = get_request()
        search_dict = copy.deepcopy(self.search_dict)
        if "host_scopes" in search_dict:
            search_dict["host_scopes"] = json.dumps(search_dict["host_scopes"])

        if "addition" in search_dict:
            search_dict["addition"] = json.dumps(search_dict["addition"])

        if "bk_biz_id" in search_dict:
            search_dict["bizId"] = search_dict["bk_biz_id"]
            search_dict["spaceUid"] = bk_biz_id_to_space_uid(search_dict["bk_biz_id"])
        search_dict["unionList"] = self.index_set_ids
        if search_dict["keyword"] is None:
            search_dict.pop("keyword")
        url_params = urlencode(search_dict)
        # 这里是为了拼接前端检索请求
        search_url = f"{request.scheme}://{request.get_host()}{settings.SITE_URL}#/retrieve?{url_params}"
        return search_url
