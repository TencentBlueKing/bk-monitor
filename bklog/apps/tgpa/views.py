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

from rest_framework.response import Response

from apps.api import TGPATaskApi
from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.generic import APIViewSet
from apps.iam import ActionEnum
from apps.iam.handlers.drf import ViewBusinessPermission, BusinessActionPermission
from apps.tgpa.constants import FEATURE_TOGGLE_TGPA_TASK
from apps.tgpa.handlers.base import TGPACollectorConfigHandler
from apps.tgpa.handlers.report import TGPAReportHandler
from apps.tgpa.handlers.task import TGPATaskHandler
from apps.tgpa.models import TGPAReportSyncRecord
from apps.tgpa.serializers import (
    CreateTGPATaskSerializer,
    GetTGPATaskListSerializer,
    GetDownloadUrlSerializer,
    GetIndexSetIdSerializer,
    GetReportListSerializer,
    SyncReportSerializer,
    GetFileStatusSerializer,
    RetrieveSyncRecordSerializer,
    GetCountInfoSerializer,
    GetUsernameListSerializer,
)
from apps.tgpa.tasks import fetch_and_process_tgpa_reports
from bkm_search_module.constants import list_route


class TGPAViewSet(APIViewSet):
    """客户端日志"""

    @list_route(methods=["GET"], url_path="count")
    def get_count_info(self, request, *args, **kwargs):
        """
        获取日志拉取任务列表
        """
        params = self.params_valid(GetCountInfoSerializer)
        return Response(
            {
                "task": TGPATaskHandler.get_task_count(params["bk_biz_id"]),
                "report": TGPAReportHandler.get_report_count(params["bk_biz_id"]),
            }
        )


class TGPATaskViewSet(APIViewSet):
    """日志拉取任务"""

    def get_permissions(self):
        if self.action == "create":
            return [BusinessActionPermission([ActionEnum.CREATE_CLIENT_LOG_TASK])]
        if self.action == "get_download_url":
            return [BusinessActionPermission([ActionEnum.DOWNLOAD_CLIENT_LOG])]
        return [ViewBusinessPermission()]

    def list(self, request, *args, **kwargs):
        """
        获取日志拉取任务列表
        """
        params = self.params_valid(GetTGPATaskListSerializer)
        return Response(TGPATaskHandler.get_task_page(params))

    def create(self, request, *args, **kwargs):
        """
        创建日志拉取任务
        """
        params = self.params_valid(CreateTGPATaskSerializer)
        params["cc_id"] = params.pop("bk_biz_id")
        params["logpath"] = params.pop("log_path")
        params["taskName"] = params.pop("task_name")
        params["username"] = request.user.username
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

    @list_route(methods=["GET"], url_path="username_list")
    def get_username_list(self, request, *args, **kwargs):
        """
        获取用户名列表
        """
        params = self.params_valid(GetUsernameListSerializer)
        return Response(TGPATaskHandler.get_username_list(params["bk_biz_id"]))


class TGPAReportViewSet(APIViewSet):
    """客户端日志上报"""

    def get_permissions(self):
        return [ViewBusinessPermission()]

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
        """
        params = self.params_valid(SyncReportSerializer)
        bk_biz_id = params["bk_biz_id"]
        if not FeatureToggleObject.switch(FEATURE_TOGGLE_TGPA_TASK, bk_biz_id):
            return Response({"record_id": None})

        sync_record_obj = TGPAReportSyncRecord.objects.create(
            bk_biz_id=bk_biz_id,
            openid_list=params.get("openid_list"),
            file_name_list=params.get("file_name_list"),
            created_by=request.user.username,
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
