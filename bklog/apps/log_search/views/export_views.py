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

from django.http import Http404
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.generic import APIViewSet
from apps.log_search.export import api
from apps.log_search.export.create import create_export_job
from apps.log_search.export.models import ExportJob
from apps.log_search.export.serializers import (
    ExportCreateSerializer,
    ExportLinkSerializer,
    ExportListSerializer,
    ExportParallelismSerializer,
    ExportScopeSerializer,
)
from apps.utils.drf import detail_route
from apps.utils.local import get_request_app_code


class ExportJobViewSet(APIViewSet):
    serializer_class = ExportScopeSerializer
    lookup_value_regex = "[0-9]+"

    def list(self, request):
        data = self.valid_serializer(ExportListSerializer).validated_data
        queryset = ExportJob.objects.filter(
            space_uid=data["space_uid"], source_app_code=get_request_app_code()
        ).order_by("-created_at", "-pk")
        offset = (data["page"] - 1) * data["limit"]
        results = []
        for job in queryset[offset : offset + data["limit"]]:
            try:
                api.authorized_job(request, job.pk, data["space_uid"])
            except (Http404, PermissionDenied):
                # 无权访问的记录不泄露任何元数据
                continue
            results.append(api.job_detail(job))
        return Response({"page": data["page"], "limit": data["limit"], "results": results})

    def create(self, request):
        data = self.valid_serializer(ExportCreateSerializer).validated_data
        return Response(api.job_detail(create_export_job(data)))

    def retrieve(self, request, pk=None):
        data = self.valid_serializer(ExportScopeSerializer).validated_data
        return Response(api.job_detail(api.authorized_job(request, pk, data["space_uid"])))

    @detail_route(methods=["GET"])
    def results(self, request, pk=None):
        data = self.valid_serializer(ExportScopeSerializer).validated_data
        return Response(api.job_results(api.authorized_job(request, pk, data["space_uid"])))

    @detail_route(methods=["GET"])
    def download_link(self, request, pk=None):
        data = self.valid_serializer(ExportLinkSerializer).validated_data
        job = api.authorized_job(request, pk, data["space_uid"])
        return Response(api.download_link(request, job, data["artifact_id"]))

    @detail_route(methods=["POST"])
    def cancel(self, request, pk=None):
        data = self.valid_serializer(ExportScopeSerializer).validated_data
        job = api.authorized_job(request, pk, data["space_uid"], operate=True)
        return Response(api.cancel_job(job.pk))

    @detail_route(methods=["PATCH"])
    def parallelism(self, request, pk=None):
        data = self.valid_serializer(ExportParallelismSerializer).validated_data
        job = api.authorized_job(request, pk, data["space_uid"], operate=True)
        return Response(api.set_parallelism(job.pk, data["requested_parallelism"]))
