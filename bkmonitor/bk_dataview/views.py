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
import logging
from typing import Dict, Optional

import requests
from django.http import Http404, HttpRequest, HttpResponse
from django.utils.decorators import method_decorator
from django.utils.encoding import smart_str
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View

from bkm_space.utils import space_uid_to_bk_biz_id
from bkmonitor.utils.request import is_ajax_request

from .api import (
    get_or_create_org,
    get_or_create_user,
    get_org_by_id,
    sync_dashboard_permission,
    sync_user_role,
)
from .permissions import GrafanaPermission, GrafanaRole
from .provisioning import sync_dashboards, sync_data_sources
from .settings import grafana_settings
from .utils import requests_curl_log

rpool = requests.Session()

logger = logging.getLogger("root")


CACHE_HEADERS = ["Cache-Control", "Expires", "Pragma", "Last-Modified"]


class ForbiddenError(Exception):
    pass


class UnauthorizedError(Exception):
    pass


class ProxyBaseView(View):
    authentication_classes = grafana_settings.AUTHENTICATION_CLASSES
    permission_classes = grafana_settings.PERMISSION_CLASSES
    provisioning_classes = ()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user: Optional[dict] = None
        self.org: Optional[dict] = None

    def get_username(self, request):
        if self.user:
            return self.user["login"]
        elif getattr(request, "external_user", None):
            return f"external_{request.external_user}"
        else:
            return request.user.username

    def initial(self, request, *args, **kwargs):
        # 登录校验
        self.perform_authentication(request)

        # 同步用户
        self.user = get_or_create_user(self.get_username(request))

        # 同步权限
        self.sync_permissions(request)

        # 同步默认数据源和仪表盘
        self.perform_provisioning(request)

    def perform_authentication(self, request):
        if len(self.authentication_classes) == 0:
            return

        for authentication_cls in self.authentication_classes:
            authentication = authentication_cls()
            user = authentication.authenticate(request)
            if user:
                return
        else:
            raise UnauthorizedError()

    def sync_permissions(self, request):
        """权限校验"""
        user_role = GrafanaRole.Anonymous
        dashboard_permissions: Dict[str, GrafanaPermission] = {}

        if not self.permission_classes:
            return

        for permission_cls in self.permission_classes:
            ok, role, permissions = permission_cls().has_permission(request, self, self.org["name"])
            if not ok:
                raise ForbiddenError()

            # 合并用户角色
            if role > user_role:
                user_role = role

            # 合并仪表盘权限
            for uid, permission in permissions.items():
                if uid not in dashboard_permissions:
                    dashboard_permissions[uid] = permission
                elif permission > dashboard_permissions[uid]:
                    dashboard_permissions[uid] = permission

        logger.info("user_role: %s, dashboard_permissions: %s", user_role, dashboard_permissions)

        # 同步用户角色
        sync_user_role(self.org["id"], self.user["id"], user_role.name)

        # 如果用户拥有编辑以上权限, 则不需要再同步仪表盘权限
        if user_role >= GrafanaRole.Editor:
            return

        # 如果用户拥有查看权限, 则只同步查看以上权限
        if user_role == GrafanaRole.Viewer:
            dashboard_permissions = {uid: p for uid, p in dashboard_permissions.items() if p > GrafanaPermission.View}
        sync_dashboard_permission(self.org["id"], self.user["id"], user_role.name, dashboard_permissions)

    def perform_provisioning(self, request):
        """默认的数据源, 面板注入"""
        if len(self.provisioning_classes) == 0:
            return

        org_name = request.org_name
        # 默认-1, 和 grafana保持一致
        org_id = self.org["id"]

        for provisioning_cls in self.provisioning_classes:
            provisioning = provisioning_cls()
            # 注入数据源
            ds_list = list(provisioning.datasources(request, org_name, org_id))
            sync_data_sources(org_id, ds_list)

            # 注入仪表盘
            dashboard_list = list(provisioning.dashboards(request, org_name, org_id))
            sync_dashboards(org_id, dashboard_list)

    def get_request_headers(self, request: HttpRequest):
        headers = {}
        for key, value in request.META.items():
            if key.startswith("HTTP_") and key != "HTTP_HOST":
                headers[key[5:].replace("_", "-")] = value
            elif key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
                headers[key.replace("_", "-")] = str(value)

        headers.update(
            {
                "Content-Type": request.META.get("CONTENT_TYPE", "text/html"),
                "X-WEBAUTH-USER": self.get_username(request),
            }
        )

        if is_ajax_request(request):
            headers["X-Requested-With"] = "XMLHttpRequest"

        if self.org and self.org["id"]:
            headers["X-Grafana-Org-Id"] = str(self.org["id"])
            headers["X-GRAFANA-ORG-ID"] = str(self.org["id"])
        return headers

    def get_request_url(self, request):
        """获取后端的grafana url"""
        return grafana_settings.HOST + request.path

    def get_org_name(self, request, *args, **kwargs) -> str:
        """
        获取org_name，取值优先级如下:
        1. 请求头中的x-grafana-org-id
        2. GET请求参数中的org_id
        """
        if self.org:
            return self.org["name"]

        org_name = request.GET.get("orgName")

        # 如果orgName不存在，且请求参数中存在space_uid，则将space_uid转换为org_name
        if not org_name and request.GET.get("space_uid"):
            bk_biz_id = space_uid_to_bk_biz_id(request.GET.get("space_uid"))
            if bk_biz_id:
                org_name = str(bk_biz_id)

        if org_name:
            if not self.org:
                self.org = get_or_create_org(org_name)
            return org_name

        org_id = request.META.get("HTTP_X_GRAFANA_ORG_ID") or request.GET.get("orgId")
        if not org_id:
            logger.error("get_org_name fail, org_id not exists")
            raise Http404
        elif not str(org_id).isdigit():
            logger.error(f"get_org_name fail, org_id({org_id}) must be digit")
            raise Http404

        self.org = get_org_by_id(org_id)
        return self.org["name"]

    def _created_proxy_response(self, request):
        url = self.get_request_url(request)
        headers = self.get_request_headers(request)

        params = request.GET.copy()
        params.pop("orgId", None)
        params.pop("orgName", None)

        try:
            proxy_response = rpool.request(
                request.method,
                url,
                params=params,
                headers=headers,
                data=request.body,
                stream=True,
                hooks={"response": requests_curl_log},
            )
        except Exception as error:
            logger.exception(error)
            raise

        return proxy_response

    def get_django_response(self, proxy_response):
        """ """
        content_type = proxy_response.headers.get("Content-Type", "")

        content = self.update_response(proxy_response, proxy_response.content)

        response = HttpResponse(content, status=proxy_response.status_code, content_type=content_type)
        for header in CACHE_HEADERS:
            value = proxy_response.headers.get(header)
            if value:
                response[header] = value

        return response

    def update_response(self, response, content):
        # 管理员跳过代码注入
        skip_code_injection = (
            not getattr(self.request, "external_user", None)
            and self.request.user.is_superuser
            and "develop" in self.request.GET
            and not getattr(self.request, "external_user", None)
        )

        # 注入控制代码
        if "text/html" in response.headers.get("Content-Type", "") and not skip_code_injection:
            content = smart_str(content)
            for tag, code in grafana_settings.CODE_INJECTIONS.items():
                if getattr(self.request, "external_user", None):
                    code = code.replace("var is_external = false;", "var is_external = true;")
                content = content.replace(tag, code)

        return content

    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        org_name = self.get_org_name(request, *args, **kwargs)
        request.org_name = org_name

        try:
            self.initial(request, *args, **kwargs)
        except Exception as err:
            logger.exception("initial request error, %s", err)
            raise Http404

        try:
            proxy_response = self._created_proxy_response(request)
        except Exception as err:
            logger.exception("proxy request error, %s", err)
            raise Http404

        return self.get_django_response(proxy_response)


class StaticView(ProxyBaseView):
    """静态资源代理, 不做校验和资源注入"""

    authentication_classes = ()
    permission_classes = ()
    provisioning_classes = ()

    def initial(self, request, *args, **kwargs):
        pass

    def get_org_name(self, request, *args, **kwargs) -> str:
        return ""

    def update_response(self, response, content):
        return content


class ProxyView(ProxyBaseView):
    """代理访问"""

    authentication_classes = grafana_settings.AUTHENTICATION_CLASSES
    permission_classes = grafana_settings.PERMISSION_CLASSES
    provisioning_classes = ()


class SwitchOrgView(ProxyBaseView):
    """项目/业务切换"""

    authentication_classes = grafana_settings.AUTHENTICATION_CLASSES
    permission_classes = grafana_settings.PERMISSION_CLASSES
    provisioning_classes = grafana_settings.PROVISIONING_CLASSES

    def get_request_url(self, request):
        return grafana_settings.HOST + grafana_settings.PREFIX
