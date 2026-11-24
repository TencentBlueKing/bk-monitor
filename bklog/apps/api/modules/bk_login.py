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
        if settings.ESB_DISABLED:
            user_gateway = settings.BK_API_URL_TMPL.format(api_name="bk-user")
        else:
            user_gateway = f"{settings.PAAS_API_HOST}/api/bk-user"
        open_api = f"{user_gateway}/prod/api/v3/open/"
        if settings.ESB_DISABLED:
            user_root = open_api + "tenant/users/"
            self.lookup_users = TenantUserAPI(
                method="GET", url=user_root + "-/lookup/", module=self.MODULE, description="按账号查询用户"
            )
            self.list_users = TenantUserAPI(method="GET", url=user_root, module=self.MODULE, description="分页查询用户")
            self.user_departments = TenantUserAPI(
                method="GET",
                url=user_root + "{user_id}/departments/",
                url_keys=["user_id"],
                module=self.MODULE,
                description="查询用户所属部门",
            )
            self.user_detail = TenantUserAPI(
                method="GET",
                url=user_root + "{user_id}/",
                url_keys=["user_id"],
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
                url=open_api + "tenants/",
                module=self.MODULE,
                description="获取租户列表",
            )
        else:
            # 没有开启多租户的，返回固定内容
            self.list_tenant = lambda *args, **kwargs: [{"id": "system", "name": "Blueking", "status": "enabled"}]

        self.batch_lookup_virtual_user = DataAPI(
            method="GET",
            url=open_api + "tenant/virtual-users/-/lookup/",
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

    def search_users(self, keyword, page, page_size):
        """通过服务端租户列表查询，只保留旧选择器请求的结果页。"""
        offset = (page - 1) * page_size
        keyword = keyword.casefold()
        results = []
        count = 0
        upstream_page = 1
        while True:
            data = self.list_users({"page": upstream_page, "page_size": 1000})
            for user in data["results"]:
                if any(
                    keyword in (user.get(field) or "").casefold()
                    for field in ("bk_username", "login_name", "full_name", "display_name")
                ):
                    if offset <= count < offset + page_size:
                        results.append(user)
                    count += 1
            if not data["results"] or upstream_page * 1000 >= data["count"]:
                return results, count
            upstream_page += 1

    def get_gateway_user(self, params):
        user = self.user_detail({"user_id": quote(params["username"], safe="")})
        return {**user, "username": user["bk_username"], "chname": user["display_name"]}

    def get_gateway_departments(self, params):
        departments = self.user_departments(
            {"user_id": quote(params["id"], safe=""), "with_ancestors": str(params.get("with_family", True)).lower()}
        )
        return [{**department, "family": department.get("ancestors", [])} for department in departments]


BKLoginApi = _BKLoginApi()
