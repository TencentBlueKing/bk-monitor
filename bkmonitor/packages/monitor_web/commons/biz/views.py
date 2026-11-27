"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.http import HttpRequest
from django.middleware.gzip import GZipMiddleware
from django.utils.cache import patch_vary_headers
from django.utils.decorators import decorator_from_middleware, method_decorator
from django.utils.text import compress_string
from werkzeug.http import parse_accept_header

from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from monitor_web.permissions import GlobalSettingPermission


class BusinessListOptionViewSet(ResourceViewSet):
    """
    拉去业务列表（select2）
    """

    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.business_list_option),
    ]


class FetchBusinessInfoViewSet(ResourceViewSet):
    """
    拉取业务的详细信息(业务名字, 运维, 权限申请url(权限中心), Demo业务链接)
    """

    # 去除鉴权
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.fetch_business_info),
    ]


class _SpaceDirectoryGZipMiddleware(GZipMiddleware):
    def process_response(self, request, response):
        if request.method != "GET":
            return response
        patch_vary_headers(response, ("Accept-Encoding",))
        encodings = parse_accept_header(request.headers.get("Accept-Encoding"))
        identity_allowed = "identity" not in encodings or encodings["identity"] > 0
        if encodings.best_match(("gzip", "identity")) != "gzip":
            if not identity_allowed:
                response.status_code = 406
                response.content = b""
                response["Content-Length"] = "0"
            return response

        # GZipMiddleware checks for the literal lowercase token rather than negotiating the header.
        gzip_request = HttpRequest()
        gzip_request.META["HTTP_ACCEPT_ENCODING"] = "gzip"
        response = super().process_response(gzip_request, response)
        if not identity_allowed and not response.has_header("Content-Encoding"):
            # Django may skip compression for short bodies or when gzip would increase their size.
            response.content = compress_string(response.content, max_random_bytes=self.max_random_bytes)
            response["Content-Length"] = str(len(response.content))
            response["Content-Encoding"] = "gzip"
            etag = response.get("ETag", "")
            if etag.startswith('"'):
                response["ETag"] = f"W/{etag}"
        return response


class ListSpacesViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute(
            "GET",
            resource.commons.list_spaces,
            decorators=[method_decorator(decorator_from_middleware(_SpaceDirectoryGZipMiddleware))],
        ),
    ]


class SpaceViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.list_sticky_spaces, endpoint="sticky_list"),
        ResourceRoute("POST", resource.commons.stick_space, endpoint="stick"),
        ResourceRoute("POST", resource.commons.create_space, endpoint="new"),
        ResourceRoute("GET", resource.commons.list_devops_spaces, endpoint="devops_list"),
    ]


class SpaceIntroduceViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.space_introduce),
    ]


class CheckClusterHealthViewSet(ResourceViewSet):
    permission_classes = (GlobalSettingPermission,)
    resource_routes = [
        ResourceRoute("GET", resource.commons.check_cluster_health),
    ]


class ListClustersViewSet(ResourceViewSet):
    permission_classes = (GlobalSettingPermission,)
    resource_routes = [
        ResourceRoute("GET", resource.commons.list_clusters),
    ]


class GetStorageClusterDetailViewSet(ResourceViewSet):
    permission_classes = (GlobalSettingPermission,)
    resource_routes = [
        ResourceRoute("GET", resource.commons.get_storage_cluster_detail),
    ]


class RegisterClusterViewSet(ResourceViewSet):
    permission_classes = (GlobalSettingPermission,)
    resource_routes = [
        ResourceRoute("POST", resource.commons.register_cluster),
    ]


class UpdateRegisteredClusterViewSet(ResourceViewSet):
    permission_classes = (GlobalSettingPermission,)
    resource_routes = [
        ResourceRoute("POST", resource.commons.update_registered_cluster),
    ]
