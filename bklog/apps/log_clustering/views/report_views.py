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
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF  OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from rest_framework import serializers
from rest_framework.response import Response

from apps.api import MonitorApi
from apps.generic import APIViewSet
from apps.log_clustering.serializers import (
    CreateOrUpdateReportSerializer,
    GetExistReportsSerlaizer,
    GetReportVariablesSerlaizer,
    SendReportSerializer,
)
from apps.utils.drf import list_route


class ReportViewSet(APIViewSet):
    serializer_class = serializers.Serializer

    def get_permissions(self):
        return []

    @list_route(methods=["GET"], url_path="get_reports")
    def get_reports(self, request):
        """
        @api {post} /report/get_reports/ 日志聚类-获取已存在订阅列表
        @apiName get_reports
        @apiGroup log_clustering
        """
        params = self.params_valid(GetExistReportsSerlaizer)
        result = MonitorApi.get_reports(params)
        return Response(result)

    @list_route(methods=["GET"], url_path="get_variables")
    def get_variables(self, request):
        """
        @api {post} /report/get_variables/ 日志聚类-获取订阅报表的变量列表
        @apiName get_variables
        @apiGroup log_clustering
        """
        params = self.params_valid(GetReportVariablesSerlaizer)
        result = MonitorApi.get_report_variables(params)
        return Response(result)

    @list_route(methods=["POST"], url_path="create_or_update")
    def create_or_update(self, request):
        """
        @api {post} /report/create_or_update/ 日志聚类-创建或更新订阅报表
        @apiName create_or_update
        @apiGroup log_clustering
        """
        params = self.params_valid(CreateOrUpdateReportSerializer)
        result = MonitorApi.create_or_update_report(params)
        return Response(result)

    @list_route(methods=["POST"], url_path="send")
    def send(self, request):
        """
        @api {post} /report/send/ 日志聚类-测试发送订阅报表
        @apiName send
        @apiGroup log_clustering
        """
        params = self.params_valid(SendReportSerializer)
        result = MonitorApi.send_report(params)
        return Response(result)
