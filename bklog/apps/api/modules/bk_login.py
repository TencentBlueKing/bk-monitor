"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from urllib.parse import quote

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.api.base import DataAPI
from apps.api.modules.utils import add_esb_info_before_request
from config.domains import USER_MANAGE_APIGATEWAY_ROOT


def get_all_user_before(params):
    params = add_esb_info_before_request(params)
    params["no_page"] = True
    params["fields"] = "username,display_name,time_zone,language"
    return params


def get_all_user_after(response_result):
    for _user in response_result.get("data", []):
        _user["chname"] = _user.pop("display_name", _user["username"])

    return response_result


def get_user_before(params):
    params = add_esb_info_before_request(params)
    params["id"] = params["bk_username"]
    return params


def get_user_after(response_result):
    if "data" in response_result:
        response_result["data"]["chname"] = response_result["data"]["display_name"]
    return response_result


class TenantUserAPI(DataAPI):
    EXCLUDE_URL_KEYS = True

    def __init__(self, **kwargs):
        super().__init__(after_request=self.check_business_code, **kwargs)

    @staticmethod
    def check_business_code(response):
        # 部分网关错误仅返回 code，DataAPI 默认把没有 result 的 HTTP 200 当作成功。
        if response.get("code", 0) != 0:
            response["result"] = False
        return response


class _BKLoginApi:
    MODULE = _("PaaS平台登录模块")

    @property
    def use_apigw(self):
        return settings.USE_APIGW

    def _build_url(self, new_path, old_path):
        return f"{settings.PAAS_API_HOST}{new_path}" if self.use_apigw else f"{USER_MANAGE_APIGATEWAY_ROOT}{old_path}"

    def __init__(self):
        user_root = f"{settings.PAAS_API_HOST}/api/bk-user/prod/api/v3/open/tenant/users/"
        if settings.ESB_DISABLED:
            self.lookup_users = TenantUserAPI(
                method="GET", url=user_root + "-/lookup/", module=self.MODULE, description="按账号查询用户"
            )
            self.list_users = TenantUserAPI(method="GET", url=user_root, module=self.MODULE, description="分页查询用户")
            self.search_users = TenantUserAPI(
                method="GET",
                url=f"{settings.PAAS_API_HOST}/api/bk-user-web/prod/api/v3/open-web/tenant/users/-/search/",
                module=self.MODULE,
                description="搜索用户",
            )
            self.user_departments = TenantUserAPI(
                method="GET",
                url=user_root + "{bk_username}/departments/",
                url_keys=["bk_username"],
                module=self.MODULE,
                description="查询用户所属部门",
            )
            self.user_detail = TenantUserAPI(
                method="GET",
                url=user_root + "{bk_username}/",
                url_keys=["bk_username"],
                module=self.MODULE,
                description="查询用户详情",
            )
        self.get_user = (
            self.get_gateway_user
            if settings.ESB_DISABLED
            else DataAPI(
                method="GET",
                url=self._build_url("/api/bk-login/prod/login/api/v3/open/bk-tokens/userinfo/", "retrieve_user/"),
                module=self.MODULE,
                description="获取单个用户",
                before_request=get_user_before,
                after_request=get_user_after,
            )
        )

        if settings.ENABLE_MULTI_TENANT_MODE:
            self.list_tenant = DataAPI(
                method="GET",
                url=settings.PAAS_API_HOST + "/api/bk-user/prod/api/v3/open/tenants/",
                module=self.MODULE,
                description="获取租户列表",
            )
        else:
            # 没有开启多租户的，返回固定内容
            self.list_tenant = lambda *args, **kwargs: [{"id": "system", "name": "Blueking", "status": "enabled"}]

        self.batch_lookup_virtual_user = DataAPI(
            method="GET",
            url=settings.PAAS_API_HOST + "/api/bk-user/prod/api/v3/open/tenant/virtual-users/-/lookup/",
            module=self.MODULE,
            description="获取虚拟用户",
            use_implicit_user_auth=False,
        )

        self.list_department_profiles = (
            self.get_gateway_departments
            if settings.ESB_DISABLED
            else DataAPI(
                method="GET",
                url=USER_MANAGE_APIGATEWAY_ROOT + "list_profile_departments/",
                module=self.MODULE,
                description="查询用户的部门信息 (v2)",
            )
        )

    def gateway_username(self, username):
        if settings.ENABLE_MULTI_TENANT_MODE:
            return username
        users = self.lookup_users({"lookup_field": "login_name", "lookups": username})
        return users[0]["bk_username"] if users else None

    def get_gateway_user(self, params):
        if settings.ENABLE_MULTI_TENANT_MODE:
            user = self.user_detail({"bk_username": quote(params["username"], safe="")})
        else:
            users = self.lookup_users({"lookup_field": "login_name", "lookups": params["username"]})
            if not users:
                return {}
            user = users[0]
        return {**user, "username": params["username"], "chname": user["display_name"]}

    def get_gateway_departments(self, params):
        username = self.gateway_username(params["id"])
        if not username:
            return []
        departments = self.user_departments(
            {"bk_username": quote(username, safe=""), "with_ancestors": str(params.get("with_family", True)).lower()}
        )
        return [{**department, "family": department.get("ancestors", [])} for department in departments]


BKLoginApi = _BKLoginApi()
