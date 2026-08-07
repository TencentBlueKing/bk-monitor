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

from django.http import StreamingHttpResponse
from rest_framework.response import Response

from apps.api import TGPATaskApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.generic import APIViewSet
from apps.iam import ActionEnum
from apps.iam.handlers.drf import BusinessActionPermission
from apps.tgpa.constants import FEATURE_TOGGLE_TGPA_TASK
from apps.utils.local import get_request_external_username
from apps.tgpa.handlers.base import TGPACollectorConfigHandler
from apps.tgpa.handlers.report import TGPAReportHandler
from apps.tgpa.handlers.search import TGPASearchHandler
from apps.tgpa.handlers.task import TGPATaskHandler
from apps.tgpa.models import TGPAReportSyncRecord
from apps.tgpa.serializers import (
    CreateTGPATaskSerializer,
    GetTGPATaskListSerializer,
    GetDownloadUrlSerializer,
    GetIndexSetIdSerializer,
    GetReportListSerializer,
    SyncReportSerializer,
    SyncTaskSerializer,
    GetFileStatusSerializer,
    GetTaskStatusSerializer,
    RetrieveSyncRecordSerializer,
    GetCountInfoSerializer,
    GetUsernameListSerializer,
    DownloadFileSerializer,
    GetOpenidListSerializer,
    GetMergedTaskListSerializer,
    GetClientInfoSerializer,
)
from apps.tgpa.tasks import fetch_and_process_tgpa_reports, sync_and_process_tgpa_tasks
from bkm_search_module.constants import list_route


class TGPAViewSet(APIViewSet):
    """客户端日志"""

    @list_route(methods=["GET"], url_path="count")
    def get_count_info(self, request, *args, **kwargs):
        """
        @api {get} /tgpa/count/?bk_biz_id=$bk_biz_id 01_TGPA-数量统计
        @apiName tgpa_get_count_info
        @apiGroup TGPA
        @apiDescription 获取客户端日志任务数和上报数统计信息
        @apiParam {Int} bk_biz_id 业务ID
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "task": 12,
                "report": 34
            },
            "result": true
        }
        """
        params = self.params_valid(GetCountInfoSerializer)
        return Response(
            {
                "task": TGPATaskHandler.get_task_count(params["bk_biz_id"]),
                "report": TGPAReportHandler.get_report_count(params["bk_biz_id"]),
            }
        )

    @list_route(methods=["GET"], url_path="openid_list")
    def get_openid_list(self, request, *args, **kwargs):
        """
        @api {get} /tgpa/openid_list/?bk_biz_id=$bk_biz_id 02_TGPA-openid列表
        @apiName tgpa_get_openid_list
        @apiGroup TGPA
        @apiDescription 根据关键字和时间范围查询 openid 列表，并从 task 与 report 中合并去重
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {String} keyword 搜索关键字
        @apiParam {Int} start_time 开始时间（毫秒时间戳）
        @apiParam {Int} end_time 结束时间（毫秒时间戳）
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": [
                "openid_1",
                "openid_2"
            ],
            "result": true
        }
        """
        params = self.params_valid(GetOpenidListSerializer)
        return Response(TGPASearchHandler.get_openid_list(params))

    @list_route(methods=["GET"], url_path="task_list")
    def get_merged_task_list(self, request, *args, **kwargs):
        """
        @api {get} /tgpa/task_list/?bk_biz_id=$bk_biz_id 03_TGPA-合并任务列表
        @apiName tgpa_get_merged_task_list
        @apiGroup TGPA
        @apiDescription 查询检索页合并任务列表，返回日志捞取任务与用户上报记录的统一结果
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {String} [source] 数据源过滤，可选值：task、report，为空时查询全部
        @apiParam {Int} [task_id] 后台任务ID（指定时仅查询 task 数据源，不查 report）
        @apiParam {String} [openid] openid
        @apiParam {Int} start_time 开始时间（毫秒时间戳）
        @apiParam {Int} end_time 结束时间（毫秒时间戳）
        @apiParam {Int} page 页码
        @apiParam {Int} pagesize 分页大小
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "total": 2,
                "list": [
                    {
                        "source": "task",
                        "id": 1,
                        "task_id": "T1",
                        "openid": "openid_1",
                        "file_name": "file_1.log",
                        "os_type": "Android",
                        "os_version": "13",
                        "sdk_version": "1.0.0",
                        "model": "Pixel",
                        "xid": "",
                        "report_time": "2026-04-24 10:00:00",
                        "process_status": "done",
                        "processed_at": "2026-04-24 10:00:00"
                    },
                    {
                        "source": "report",
                        "id": null,
                        "task_id": null,
                        "openid": "openid_2",
                        "file_name": "report.log",
                        "os_type": "iOS",
                        "os_version": "16.0",
                        "sdk_version": "3.0",
                        "model": "iPhone14",
                        "xid": "",
                        "report_time": "2026-04-24 09:00:00",
                        "process_status": "pending",
                        "processed_at": ""
                    }
                ]
            },
            "result": true
        }
        """
        params = self.params_valid(GetMergedTaskListSerializer)
        return Response(TGPASearchHandler.get_merged_task_list(params))

    @list_route(methods=["GET"], url_path="client_info")
    def get_client_info(self, request, *args, **kwargs):
        """
        @api {get} /tgpa/client_info/?bk_biz_id=$bk_biz_id&openid=$openid 04_TGPA-客户端信息
        @apiName tgpa_get_client_info
        @apiGroup TGPA
        @apiDescription 根据 openid 获取客户端累计数量与指定时间范围内的数量统计
        @apiParam {Int} bk_biz_id 业务ID
        @apiParam {String} openid openid
        @apiParam {Int} start_time 开始时间（毫秒时间戳）
        @apiParam {Int} end_time 结束时间（毫秒时间戳）
        @apiSuccessExample {json} 成功返回:
        {
            "message": "",
            "code": 0,
            "data": {
                "total_count": 20,
                "range_count": 5
            },
            "result": true
        }
        """
        params = self.params_valid(GetClientInfoSerializer)
        return Response(TGPASearchHandler.get_client_info(params))


class TGPATaskViewSet(APIViewSet):
    """日志拉取任务"""

    def get_permissions(self):
        if self.action == "create":
            return [BusinessActionPermission([ActionEnum.CREATE_CLIENT_LOG_TASK])]
        if self.action in ("get_download_url", "download_file"):
            return [BusinessActionPermission([ActionEnum.DOWNLOAD_CLIENT_LOG])]
        return [BusinessActionPermission([ActionEnum.VIEW_CLIENT_LOG])]

    def list(self, request, *args, **kwargs):
        """
        获取日志拉取任务列表
        """
        params = self.params_valid(GetTGPATaskListSerializer)
        return Response(TGPATaskHandler.get_task_page(params))

    def create(self, request, *args, **kwargs):
        """
        创建日志拉取任务

        审计身份：创建人使用真实用户名（外部PO用户走代理时为 external_user 本人，
        内部用户为 request.user），不写成内部授权人(authorizer)，与身份三分离原则一致。
        """
        params = self.params_valid(CreateTGPATaskSerializer)
        params["cc_id"] = params.pop("bk_biz_id")
        params["logpath"] = params.pop("log_path")
        params["taskName"] = params.pop("task_name")
        params["username"] = get_request_external_username() or request.user.username
        TGPATaskApi.create_single_user_log_task_v2(params)
        return Response()

    @list_route(methods=["GET"], url_path="download_url")
    def get_download_url(self, request, *args, **kwargs):
        """
        获取文件下载链接
        """
        params = self.params_valid(GetDownloadUrlSerializer)
        task_handler = TGPATaskHandler(bk_biz_id=params["bk_biz_id"], inst_id=params["id"])
        url = task_handler.task_info.get("download_url", "")
        return Response({"url": url})

    @list_route(methods=["GET"], url_path="index_set_id")
    def get_index_set_id(self, request, *args, **kwargs):
        """
        获取客户端日志索引集ID
        """
        params = self.params_valid(GetIndexSetIdSerializer)
        res = {
            "index_set_id": None,
            "collector_config_id": None,
        }
        if FeatureToggleObject.switch(FEATURE_TOGGLE_TGPA_TASK, params["bk_biz_id"]):
            collector_config = TGPACollectorConfigHandler.get_or_create_collector_config(bk_biz_id=params["bk_biz_id"])
            res["index_set_id"] = collector_config.index_set_id
            res["collector_config_id"] = collector_config.collector_config_id
        return Response(res)

    @list_route(methods=["GET"], url_path="download_file")
    def download_file(self, request, *args, **kwargs):
        """
        下载客户端日志文件（下载、解压、解密、重新打包后流式返回）
        """
        params = self.params_valid(DownloadFileSerializer)
        file_iterator, file_name, file_size = TGPATaskHandler.stream_download_file(
            bk_biz_id=params["bk_biz_id"],
            file_name=params["file_name"],
        )

        response = StreamingHttpResponse(
            file_iterator,
            content_type="application/zip",
        )
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        response["Content-Length"] = file_size
        return response

    @list_route(methods=["GET"], url_path="username_list")
    def get_username_list(self, request, *args, **kwargs):
        """
        获取用户名列表
        """
        params = self.params_valid(GetUsernameListSerializer)
        return Response(TGPATaskHandler.get_username_list(params["bk_biz_id"]))

    @list_route(methods=["POST"], url_path="status")
    def get_task_status(self, request, *args, **kwargs):
        """
        获取任务处理状态
        """
        params = self.params_valid(GetTaskStatusSerializer)
        return Response(TGPATaskHandler.get_task_status(params["bk_biz_id"], params["task_id_list"]))

    @list_route(methods=["POST"], url_path="sync")
    def sync_task(self, request, *args, **kwargs):
        """
        手动触发同步并处理指定的客户端日志捞取任务
        """
        params = self.params_valid(SyncTaskSerializer)
        bk_biz_id = params["bk_biz_id"]
        if not FeatureToggleObject.switch(FEATURE_TOGGLE_TGPA_TASK, bk_biz_id):
            return Response()

        sync_and_process_tgpa_tasks.delay(bk_biz_id, params["task_id_list"])
        return Response()


class TGPAReportViewSet(APIViewSet):
    """客户端日志上报"""

    def get_permissions(self):
        return [BusinessActionPermission([ActionEnum.VIEW_CLIENT_LOG])]

    def list(self, request, *args, **kwargs):
        """
        获取客户端日志上报列表
        """
        params = self.params_valid(GetReportListSerializer)
        return Response(TGPAReportHandler.get_report_list(params))

    @list_route(methods=["POST"], url_path="sync")
    def sync_report(self, request, *args, **kwargs):
        """
        同步客户端日志上报文件

        审计身份：created_by 使用真实用户名（外部PO用户走代理时为 external_user 本人，
        内部用户为 request.user），不写成内部授权人(authorizer)，与身份三分离原则一致。
        """
        params = self.params_valid(SyncReportSerializer)
        bk_biz_id = params["bk_biz_id"]
        if not FeatureToggleObject.switch(FEATURE_TOGGLE_TGPA_TASK, bk_biz_id):
            return Response({"record_id": None})

        sync_record_obj = TGPAReportSyncRecord.objects.create(
            bk_biz_id=bk_biz_id,
            openid_list=params.get("openid_list"),
            file_name_list=params.get("file_name_list"),
            created_by=get_request_external_username() or request.user.username,
        )
        fetch_and_process_tgpa_reports.delay(sync_record_obj.id, params)

        return Response({"record_id": sync_record_obj.id})

    @list_route(methods=["POST"], url_path="file_status")
    def get_file_status(self, request, *args, **kwargs):
        """
        获取文件处理状态
        """
        params = self.params_valid(GetFileStatusSerializer)
        return Response(TGPAReportHandler.get_file_status(params["file_name_list"]))

    @list_route(methods=["GET"], url_path="sync_record")
    def retrieve_sync_record(self, request, *args, **kwargs):
        """
        获取同步记录信息
        """
        params = self.params_valid(RetrieveSyncRecordSerializer)
        record_info = (
            TGPAReportSyncRecord.objects.filter(id=params["record_id"])
            .values("id", "status", "openid_list", "file_name_list")
            .get()
        )
        return Response(record_info)
