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
# IAMV4ResourceCallbackView — IAM v4 资源实例回调接口
#
# IAM v4 平台通过此接口查询我们系统的资源实例列表和详情。
#
# 协议：
#   POST body:
#     {
#       "method": "list_instance" | "fetch_instance_info",
#       "type": "<resource_type>",
#       "filter": {"parent": {"type": "...", "id": "..."}, "keyword": "..."},
#       "page": {"page": 1, "page_size": 100},
#       "requires": ["_bk_iam_path_"]
#     }
#
#   GET: 连通性探测，返回 {"code": 0, "data": {"status": "ok"}}
#
# 使用方式：
#   业务在 URLconf 中自行挂载：
#       path("iam/v4/callback/", IAMV4ResourceCallbackView.as_view())
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ...iam_engine.callback.service import CallbackService
from .auth import IamCallbackAuthentication

logger = logging.getLogger(__name__)


class IAMV4ResourceCallbackView(APIView):
    """IAM v4 资源回调接口。

    Authentication:
        使用 IamCallbackAuthentication（IAM Basic Auth: bk_iam / system_token）。

    协议细节：
        POST method=list_instance:
            查询某个资源类型的实例列表（支持分页、关键词搜索）。
        POST method=fetch_instance_info:
            根据 ID 列表批量获取资源实例详情。
        GET:
            连通性探测。
    """

    authentication_classes = [IamCallbackAuthentication]
    permission_classes = []

    def get(self, request: Request) -> Response:
        """连通性探测。

        Returns:
            Response: {"code": 0, "data": {"status": "ok"}}
        """
        return Response({"code": 0, "data": {"status": "ok"}})

    def post(self, request: Request) -> Response:
        """处理 IAM v4 平台的资源回调请求。

        根据 method 字段分发到 list_instance 或 fetch_instance_info 处理。

        Args:
            request: DRF Request，body 包含 method/type/filter/page/requires 字段。

        Returns:
            Response:
                成功: {"code": 0, "data": {...}}
                未知 method: {"code": 0, "data": {"count": 0, "results": []}}
                异常: {"error": {"code": "INTERNAL_ERROR", "message": "..."}}, status=500
        """
        method = request.data.get("method", "")
        resource_type = request.data.get("type", "")
        filter_data = request.data.get("filter", {})
        page = request.data.get("page", {})

        service = self._get_service()

        logger.info("[iam_v4:callback] method=%s type=%s page=%s", method, resource_type, page)

        try:
            if method == "list_instance":
                result = service.dispatch_list_instance(resource_type, filter_data, page)
                return Response({"code": 0, "data": result})
            elif method == "fetch_instance_info":
                requires = request.data.get("requires", [])
                result = service.dispatch_fetch_instance_info(resource_type, filter_data.get("ids", []), requires)
                return Response({"code": 0, "data": result})
            else:
                logger.warning("[iam_v4:callback] unknown method=%s", method)
                return Response({"code": 0, "data": {"count": 0, "results": []}})
        except Exception as e:
            logger.exception("[iam_v4:callback] error: %s", e)
            return Response(
                {"error": {"code": "INTERNAL_ERROR", "message": str(e)[:200]}},
                status=500,
            )

    @staticmethod
    def _get_service() -> CallbackService:
        """从框架获取 v4 Provider 的 CallbackService 实例。

        Returns:
            CallbackService: v4 Provider 持有的回调分发器。
        """
        from ...iam_engine.django.facade import get_framework
        from ...iam_v4 import PROVIDER_NAME

        provider = get_framework().providers[PROVIDER_NAME]
        return provider.callback_service
