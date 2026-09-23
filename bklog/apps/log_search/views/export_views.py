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

"""分片异步导出的 Web 接口；既有 AsyncTask 导出路由保持原契约。"""

from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.drf import PlatformAwareIndexSearchPermission, ViewBusinessPermission
from apps.log_search.export import api, state
from apps.log_search.export.models import ExportJob
from apps.log_search.export.serializers import (
    ExportCreateSerializer,
    ExportLinkSerializer,
    ExportListSerializer,
    ExportScopeSerializer,
)
from apps.utils.drf import detail_route
from apps.utils.local import get_request_app_code, get_request_external_username


class ExportJobViewSet(APIViewSet):
    serializer_class = ExportScopeSerializer
    lookup_value_regex = "[0-9]+"

    def get_permissions(self):
        if self.action == "create":
            # 创建任务需要索引集级检索权限，实例ID由请求体传入；非法入参交给序列化器报错
            try:
                int(self.request.data.get("index_set_id"))
            except (TypeError, ValueError):
                return []
            return [
                PlatformAwareIndexSearchPermission(
                    [ActionEnum.SEARCH_LOG], ResourceEnum.INDICES, iam_instance_id_key="index_set_id"
                )
            ]
        return [ViewBusinessPermission()]

    def get_queryset(self):
        """任务可见范围：请求空间 + 来源应用；外部用户只看自己创建的任务。"""
        space_uid = self.request.data.get("space_uid") or self.request.query_params.get("space_uid")
        queryset = ExportJob.objects.filter(space_uid=space_uid, source_app_code=get_request_app_code())
        external_username = get_request_external_username()
        if external_username:
            queryset = queryset.filter(created_by=external_username)
        return queryset

    def list(self, request):
        data = self.valid_serializer(ExportListSerializer).validated_data
        queryset = self.get_queryset().annotate(**state.leaf_counts_annotation()).order_by("-created_at", "-pk")
        offset = (data["page"] - 1) * data["limit"]
        results = [api.job_detail(job) for job in queryset[offset : offset + data["limit"]]]
        return Response({"page": data["page"], "limit": data["limit"], "results": results})

    def create(self, request):
        data = self.valid_serializer(ExportCreateSerializer).validated_data
        return Response(api.job_detail(api.create_export_job(data)))

    def retrieve(self, request, pk=None):
        self.valid_serializer(ExportScopeSerializer)
        return Response(api.job_detail(self.get_object()))

    @detail_route(methods=["GET"])
    def results(self, request, pk=None):
        self.valid_serializer(ExportScopeSerializer)
        return Response(api.job_results(self.get_object()))

    @detail_route(methods=["GET"])
    def download_link(self, request, pk=None):
        data = self.valid_serializer(ExportLinkSerializer).validated_data
        return Response(api.download_link(self.get_object(), data["artifact_id"]))

    @detail_route(methods=["POST"])
    def cancel(self, request, pk=None):
        self.valid_serializer(ExportScopeSerializer)
        job = self.get_object()
        if job.created_by != api.current_username():
            raise PermissionDenied("只有任务创建者可以操作该任务")
        return Response(api.cancel_job(job.pk))
