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
from apps.iam.handlers.drf import ViewBusinessPermission
from apps.log_databus.handlers.grok import GrokHandler
from apps.log_databus.models import GrokInfo
from apps.log_databus.serializers import (
    GrokCreateSerializer,
    GrokDebugSerializer,
    GrokListSerializer,
    GrokUpdateSerializer,
    GrokUpdatedByListSerializer,
)
from apps.utils.drf import list_route


class GrokViewSet(APIViewSet):
    """
    Grok模式管理
    """

    lookup_field = "grok_info_id"

    def get_permissions(self):
        return [ViewBusinessPermission()]

    def list(self, request, *args, **kwargs):
        params = self.params_valid(GrokListSerializer)
        return Response(GrokHandler.list_grok_info(params))

    def create(self, request, *args, **kwargs):
        params = self.params_valid(GrokCreateSerializer)
        return Response(GrokHandler.create_grok_info(params))

    def update(self, request, grok_info_id):
        params = self.params_valid(GrokUpdateSerializer)
        params["id"] = grok_info_id
        return Response(GrokHandler.update_grok_info(params))

    def destroy(self, request, grok_info_id):
        return Response(GrokHandler.delete_grok_info(grok_info_id))

    @list_route(methods=["GET"], url_path="updated_by_list")
    def get_updated_by_list(self, request, *args, **kwargs):
        params = self.params_valid(GrokUpdatedByListSerializer)
        updated_by_list = (
            GrokInfo.objects.filter(bk_biz_id=params["bk_biz_id"]).values_list("updated_by", flat=True).distinct()
        )
        return Response(updated_by_list)

    @list_route(methods=["POST"], url_path="debug")
    def debug(self, request, *args, **kwargs):
        params = self.params_valid(GrokDebugSerializer)
        return Response(GrokHandler.debug(params))
