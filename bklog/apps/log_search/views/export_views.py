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

from apps.generic import APIViewSet
from apps.iam import ActionEnum, ResourceEnum
from apps.iam.handlers.drf import PlatformAwareIndexSearchPermission, ViewBusinessPermission
from apps.log_search.export import api
from apps.log_search.export.models import ExportJob
from apps.log_search.export.serializers import (
    ExportLinkSerializer,
    ExportScopeSerializer,
)
from apps.utils.drf import detail_route
from apps.utils.local import get_request_app_code, get_request_external_username


class ExportIndexSearchPermission(PlatformAwareIndexSearchPermission):
    """逐个校验任务涉及的索引集，保留平台级索引集的额外鉴权规则。"""

    def __init__(self):
        super().__init__([ActionEnum.SEARCH_LOG], ResourceEnum.INDICES)
        self._instance_id = None

    def check_index_sets(self, request, view, index_set_ids):
        for index_set_id in index_set_ids:
            self._instance_id = index_set_id
            super().has_permission(request, view)
        return True

    def get_instance_id(self, request, view):
        return self._instance_id


class ExportJobIndexSearchPermission(ExportIndexSearchPermission):
    """详情类接口的索引集列表取自任务快照，而不是请求参数。"""

    def has_permission(self, request, view):
        # 索引集要拿到任务之后才知道，准入阶段交给空间级校验
        return True

    def has_object_permission(self, request, view, obj):
        return self.check_index_sets(request, view, obj.index_set_ids)


class ExportJobViewSet(APIViewSet):
    serializer_class = ExportScopeSerializer
    lookup_value_regex = "[0-9]+"

    def get_permissions(self):
        return [ViewBusinessPermission(), ExportJobIndexSearchPermission()]

    def get_queryset(self):
        """任务可见范围：请求空间 + 来源应用；外部用户只看自己创建的任务。产物读取另过索引集鉴权。"""
        space_uid = self.request.data.get("space_uid") or self.request.query_params.get("space_uid")
        queryset = ExportJob.objects.filter(space_uid=space_uid, source_app_code=get_request_app_code())
        external_username = get_request_external_username()
        if external_username:
            queryset = queryset.filter(created_by=external_username)
        return queryset

    @detail_route(methods=["GET"])
    def download_link(self, request, pk=None):
        data = self.valid_serializer(ExportLinkSerializer).validated_data
        return Response(api.download_link(self.get_object(), data["artifact_id"]))
