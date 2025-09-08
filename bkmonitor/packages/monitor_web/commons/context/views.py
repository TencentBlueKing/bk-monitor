# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Any, Dict

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from common.context_processors import get_default_biz_id
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.commons.context.resources import ContextType


class ContextViewSet(GenericViewSet):

    # context 无需鉴权
    permission_classes = []

    @action(methods=["GET"], detail=False)
    def enhanced(self, request):
        params: Dict[str, Any] = request.query_params.copy()
        params["bk_biz_id"] = get_default_biz_id(request)
        # resource 感知不到 response，此处复用 resource.request，并在 response 设置 cookie
        get_context_result: Dict[str, Any] = resource.commons.enhanced_get_context.request(params)
        response = Response(get_context_result["context"])
        if get_context_result["context_type"] == ContextType.BASIC.value:
            response.set_cookie("bk_biz_id", str(get_context_result["context"]["BK_BIZ_ID"]))
        return response


class GetContextViewSet(ResourceViewSet):
    """
    获取结果表列表，包括是否需要接入的信息
    """

    permission_classes = []
    resource_routes = [ResourceRoute("GET", resource.commons.get_context)]
