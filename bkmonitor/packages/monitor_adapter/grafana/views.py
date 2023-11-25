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
import json
import logging

from blueapps.middleware.xss.decorators import escape_exempt
from django.conf import settings
from django.contrib import auth
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import urlencode
from django.views.decorators.csrf import csrf_exempt
from rest_framework.exceptions import ValidationError

from bk_dataview.api import get_or_create_org
from bk_dataview.views import ProxyView, StaticView, SwitchOrgView
from bkm_space.api import SpaceApi
from bkmonitor.models.external_iam import ExternalPermission
from core.drf_resource import api
from core.errors.api import BKAPIError
from monitor.models import GlobalConfig
from monitor_web.grafana.utils import patch_home_panels

__all__ = ["ProxyView", "StaticView", "SwitchOrgView", "RedirectDashboardView"]

logger = logging.getLogger(__name__)


class RedirectDashboardView(ProxyView):
    """
    仪表盘跳转
    """

    @method_decorator(escape_exempt)
    def dispatch(self, request, *args, **kwargs):
        org_name = request.GET.get("bizId")
        if not org_name:
            # 兼容 space_uid 模式
            space_uid = request.GET.get("spaceUid")
            try:
                space = SpaceApi.get_space_detail(space_uid)
                org_name = str(space.bk_biz_id)
            except (ValidationError, BKAPIError, AttributeError):
                logger.error(f"get_org_name from request fail. {request.GET}")
                raise Http404

        request.org_name = org_name
        self.org = get_or_create_org(org_name)
        try:
            self.initial(request, *args, **kwargs)
        except Exception as err:
            logger.exception("initial request error, %s", err)
            raise Http404

        dash_name = request.GET.get("dashName")
        folder_name = request.GET.get("folderName")
        org_id = self.org["id"]
        db_query = dict(type="dash-db", org_id=org_id, query=dash_name)
        if folder_name:
            if folder_name == "General":
                folder_filter = {"folderIds": [0]}
            else:
                folder_list = api.grafana.search_folder_or_dashboard(
                    type="dash-folder", org_id=org_id, query=folder_name
                )["data"]
                folder_filter = {"folderIds": [fold["id"]] for fold in folder_list if fold["title"] == folder_name}

            db_query.update(folder_filter)
        dashboards = api.grafana.search_folder_or_dashboard(**db_query)["data"]
        logger.info(f"db_query: {db_query}")
        logger.info(f"dashboards: {len(dashboards)}")
        if not dashboards:
            raise Http404
        dashboard_info = dashboards[0]
        uid = dashboard_info["uid"]
        route_path = f"#/grafana/d/{uid}"
        # 透传仪表盘参数
        params = {k: v for k, v in request.GET.items() if k.startswith("var-")}
        params["bizId"] = org_name
        redirect_url = "/?{params}{route_path}"
        return redirect(redirect_url.format(params=urlencode(params), route_path=route_path))


class GrafanaSwitchOrgView(SwitchOrgView):
    @staticmethod
    def is_allowed_external_request(request):
        if not request.org_name:
            return True

        filter_resources = ["home"]
        for external_permission in ExternalPermission.objects.filter(
            authorized_user=request.external_user,
            bk_biz_id=int(request.org_name),
            action_id="view_grafana",
            expire_time__gt=timezone.now(),
        ):
            filter_resources.extend(external_permission.resources)

        if "d/" in request.path or "dashboards/" in request.path:
            for resource in filter_resources:
                if resource in request.path:
                    return True
            return False
        else:
            return True

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        org_name = self.get_org_name(request, *args, **kwargs)
        request.org_name = org_name

        # 外部用户访问grafana，使用内部用户权限绕过角色校验
        if getattr(request, "external_user", None) and org_name:
            authorizer_map, _ = GlobalConfig.objects.get_or_create(
                key="EXTERNAL_AUTHORIZER_MAP", defaults={"value": {}}
            )
            authorizer = authorizer_map.value[org_name]
            user = auth.authenticate(username=authorizer)
            setattr(request, "user", user)

            # 过滤外部用户仪表盘
            if not self.is_allowed_external_request(request):
                return HttpResponseForbidden(f"外部用户{request.external_user}无该仪表盘访问或操作权限")

        return super(GrafanaSwitchOrgView, self).dispatch(request, *args, **kwargs)


class GrafanaProxyView(ProxyView):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        org_name = self.get_org_name(request, *args, **kwargs)
        request.org_name = org_name

        # 外部用户访问grafana，使用内部用户权限绕过角色校验
        if getattr(request, "external_user", None) and org_name:
            authorizer_map, _ = GlobalConfig.objects.get_or_create(
                key="EXTERNAL_AUTHORIZER_MAP", defaults={"value": {}}
            )
            authorizer = authorizer_map.value[org_name]
            user = auth.authenticate(username=authorizer)
            setattr(request, "user", user)

        response = super(GrafanaProxyView, self).dispatch(request, *args, **kwargs)

        # 这里对 Home 仪表盘进行 patch，替换为指定的面板
        if request.method == "GET" and request.path.rstrip("/").endswith("/api/dashboards/home"):
            try:
                origin_content = json.loads(response.content)
                origin_content["dashboard"]["panels"] = patch_home_panels()
                patched_content = json.dumps(origin_content)
                return HttpResponse(patched_content, status=response.status_code)
            except Exception as e:
                logger.exception("[patch home panels] error: {}".format(e))
                # 异常则不替换了
                return response

        # 禁用access control api
        if not request.user.is_superuser and request.method == "POST" and "/api/access-control" in request.path:
            return HttpResponseForbidden("permission change is forbidden")

        return response

    def get_request_headers(self, request):
        headers = super(GrafanaProxyView, self).get_request_headers(request)
        # 单仪表盘权限适配
        if "/api/annotations" in request.path:
            headers["X-WEBAUTH-USER"] = "admin"
        return headers

    def update_response(self, response, content):
        content = super(GrafanaProxyView, self).update_response(response, content)
        if isinstance(content, bytes):
            content = content.decode("utf-8")
        return content.replace(
            "<script>", f"<script>\nvar graphWatermark={'true' if settings.GRAPH_WATERMARK else 'false'};"
        )


class ApiProxyView(GrafanaProxyView):
    permission_classes = ()

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        response = super(ApiProxyView, self).dispatch(request, *args, **kwargs)

        # 过滤外部用户仪表盘
        if "api/search" in request.path:
            try:
                self.filter_external_resource(request, response)
            except Exception:
                pass
        return response

    def filter_external_resource(self, request, response):
        filter_resources = []
        org_name = self.get_org_name(request)
        if request and getattr(request, "external_user", None) and org_name:
            for external_permission in ExternalPermission.objects.filter(
                authorized_user=request.external_user,
                bk_biz_id=int(org_name),
                action_id="view_grafana",
                expire_time__gt=timezone.now(),
            ):
                filter_resources.extend(external_permission.resources)
            result = json.loads(response.content)
            result = [
                record
                for record in result
                if record.get("type", "") == "dash-db" and record.get("uid", "") in filter_resources
            ]
            response.content = json.dumps(result)
