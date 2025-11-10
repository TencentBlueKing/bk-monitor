"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from rest_framework.status import HTTP_401_UNAUTHORIZED

from bkmonitor.models import ApiAuthToken, AuthType
from bkmonitor.views.renderers import MonitorJSONRenderer
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from metadata import resources as resource


RENDER_CLASSES = (MonitorJSONRenderer,)


class EntityViewSet(ResourceViewSet):
    renderer_classes = RENDER_CLASSES

    def check_permissions(self, request):
        # 中间件已经判断了 token 的有效性，为避免调用方通过非 token 的方式访问，此处只需校验 token 是否存在
        token_obj = None
        token = getattr(request._request, "token", None)
        if token:
            token_obj = ApiAuthToken.objects.filter(token=token, type=AuthType.Entity).first()
        if not token_obj:
            self.permission_denied(
                request,
                message=f"API Token is required, please use your browser to access the address {settings.BK_MONITOR_HOST}/rest/v2/commons/token_manager/get_api_token/?type=entity&bk_biz_id={{your_biz_id}} to get your API Token",
                code=HTTP_401_UNAUTHORIZED,
            )

    resource_routes = [
        ResourceRoute("POST", resource.ApplyEntityResource, endpoint="apply"),
        # ResourceRoute("GET", resource.GetEntityResource, endpoint="get"),
        ResourceRoute("GET", resource.ListEntityResource, endpoint="query"),
        ResourceRoute("POST", resource.DeleteEntityResource, endpoint="delete"),
    ]
