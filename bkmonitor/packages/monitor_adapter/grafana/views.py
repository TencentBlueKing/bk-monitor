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
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from monitor_web.grafana.utils import patch_home_panels

from bk_dataview.views import ProxyView, StaticView, SwitchOrgView
from core.drf_resource import api

__all__ = ["ProxyView", "StaticView", "SwitchOrgView"]

logger = logging.getLogger(__name__)


class RedirectDashboardView(ProxyView):
    """
    仪表盘跳转
    """

    @method_decorator(escape_exempt)
    def dispatch(self, request, *args, **kwargs):
        org_name = request.GET.get("bizId")
        if not org_name:
            logger.error("get_org_name from bizId fail, bizId not exists")
            raise Http404

        request.org_name = org_name
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
        redirect_url = "/?bizId={bk_biz_id}{route_path}"
        return redirect(redirect_url.format(bk_biz_id=request.org_name, route_path=route_path))


class GrafanaProxyView(ProxyView):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
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
