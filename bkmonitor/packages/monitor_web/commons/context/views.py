# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from typing import Optional

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkmonitor.utils.common_utils import safe_int
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class ContextViewSet(GenericViewSet):
    @action(methods=["GET"], detail=False)
    def enhanced(self, request):
        params = request.query_params.copy()
        biz_id_or_none: Optional[str] = (
            request.GET.get("bizId") or request.session.get("bk_biz_id") or request.COOKIES.get("bk_biz_id")
        )
        if biz_id_or_none:
            params["bk_biz_id"] = safe_int(str(biz_id_or_none).strip("/"), dft=None)

        get_context_result = resource.commons.enhanced_get_context.request(params)
        response = Response(get_context_result["context"])
        if get_context_result["context_type"] == "basic":
            response.set_cookie("bk_biz_id", str(get_context_result["context"]["BK_BIZ_ID"]))
        return response


class GetContextViewSet(ResourceViewSet):
    """
    获取结果表列表，包括是否需要接入的信息
    """

    permission_classes = []
    resource_routes = [ResourceRoute("GET", resource.commons.get_context)]
