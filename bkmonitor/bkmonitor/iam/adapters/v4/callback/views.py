"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import logging

from django.core.exceptions import ImproperlyConfigured
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from bkmonitor.views.renderers import UJSONRenderer

from .auth import MonitorIamCallbackAuthentication
from .handlers import get_callback_service
from .service import V4CallbackService

logger = logging.getLogger(__name__)


class V4ResourceCallbackView(APIView):
    """项目侧 V4 资源 callback 协议 View。

    子类显式提供 callback_service 和认证方式。本类不读取 IAMFramework、
    V4PermissionProvider 或 Provider 配置。
    """

    authentication_classes = []
    permission_classes = []
    # IAM callback 有独立协议，不能被 Web/API 角色的全局 renderer 再包一层。
    renderer_classes = [UJSONRenderer]
    callback_service: V4CallbackService | None = None

    def get(self, request: Request) -> Response:
        """供 IAM 平台执行 callback 连通性探测。"""
        return Response({"code": 0, "data": {"status": "ok"}})

    def post(self, request: Request) -> Response:
        """处理 IAM 平台的 list_instance / fetch_instance_info 请求。"""
        method = request.data.get("method", "")
        filter_data = request.data.get("filter", {})
        page = request.data.get("page", {})

        service = self.get_callback_service()
        dialect_resource_type = request.data.get("type", "")
        resource_type = service.decode_resource_type(dialect_resource_type)

        logger.info(
            "[iam_v4:callback] method=%s type=%s business_type=%s page=%s",
            method,
            dialect_resource_type,
            resource_type,
            page,
        )

        try:
            if method == "list_instance":
                result = service.dispatch_list_instance(resource_type, filter_data, page)
                return Response({"code": 0, "data": result})
            if method == "fetch_instance_info":
                requires = request.data.get("requires", [])
                result = service.dispatch_fetch_instance_info(resource_type, filter_data.get("ids", []), requires)
                return Response({"code": 0, "data": result})

            logger.warning("[iam_v4:callback] unknown method=%s", method)
            return Response({"code": 0, "data": {"count": 0, "results": []}})
        except Exception as exc:
            logger.exception("[iam_v4:callback] error: %s", exc)
            return Response(
                {"error": {"code": "INTERNAL_ERROR", "message": str(exc)[:200]}},
                status=500,
            )

    def get_callback_service(self) -> V4CallbackService:
        """返回项目注入的 V4 回调服务。"""
        if self.callback_service is None:
            raise ImproperlyConfigured(
                "V4ResourceCallbackView requires a project-provided callback_service; "
                "configure it in the callback project."
            )
        return self.callback_service


class MonitorV4ResourceCallbackView(V4ResourceCallbackView):
    """监控项目的 V4 callback 入口。"""

    authentication_classes = [MonitorIamCallbackAuthentication]
    callback_service = get_callback_service()
