"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# ResourceCallbackView — IAM v4 资源实例回调接口
#
# POST 接收 method=list_instance / fetch_instance_info
# GET  连通性探测
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import IamCallbackAuthentication
from . import services

logger = logging.getLogger(__name__)


class ResourceCallbackView(APIView):
    """IAM v4 资源回调接口。"""

    authentication_classes = [IamCallbackAuthentication]
    permission_classes = []

    @classmethod
    def as_view(cls, **initkwargs):
        view = super().as_view(**initkwargs)
        view.login_exempt = True
        return view

    def get(self, request: Request) -> Response:
        """连通性探测。"""
        return Response({"data": {"status": "ok"}})

    def post(self, request: Request) -> Response:
        method = request.data.get("method", "")
        resource_type = request.data.get("type", "")
        filter_data = request.data.get("filter", {})
        page = request.data.get("page", {})

        logger.info(
            "[iam_v4:callback] method=%s type=%s page=%s",
            method,
            resource_type,
            page,
        )

        if method == "list_instance":
            result = services.list_instance(resource_type, filter_data, page)
            return Response({"data": result})
        elif method == "fetch_instance_info":
            requires = request.data.get("requires", [])
            result = services.fetch_instance_info(resource_type, filter_data.get("ids", []), requires)
            return Response({"data": result})
        else:
            logger.warning("[iam_v4:callback] unknown method=%s", method)
            return Response({"data": {"results": []}})
