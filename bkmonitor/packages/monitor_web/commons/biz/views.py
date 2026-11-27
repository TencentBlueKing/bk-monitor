"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import wraps

from django.utils.cache import patch_vary_headers
from django.utils.decorators import method_decorator
from django.utils.http import parse_header_parameters
from django.views.decorators.gzip import gzip_page

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


def _gzip_space_directory(view):
    compressed_view = gzip_page(view)

    @wraps(view)
    def negotiated(request, *args, **kwargs):
        if request.method != "GET":
            return view(request, *args, **kwargs)

        selected_view = view
        # Django's gzip_page checks for a gzip token even when its quality is zero.
        for coding in request.headers.get("Accept-Encoding", "").split(","):
            name, parameters = parse_header_parameters(coding)
            if name != "gzip":
                continue
            try:
                quality = float(parameters.get("q", "1"))
            except ValueError:
                break
            if 0 < quality <= 1:
                selected_view = compressed_view
            break

        response = selected_view(request, *args, **kwargs)
        patch_vary_headers(response, ("Accept-Encoding",))
        return response

    return negotiated


class ListSpacesViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.list_spaces, decorators=[method_decorator(_gzip_space_directory)]),
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
