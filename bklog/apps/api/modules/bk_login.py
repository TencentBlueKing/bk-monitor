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

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.api.base import DataAPI
from apps.api.modules.utils import add_esb_info_before_request
from apps.utils.local import set_request_username
from config.domains import USER_MANAGE_APIGATEWAY_ROOT


def get_all_user_before(params):
    params = add_esb_info_before_request(params)
    params["no_page"] = True
    params["fields"] = "username,display_name,time_zone,language"
    return params


def virtual_user_before(params):
    set_request_username("admin")
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


class _BKLoginApi:
    MODULE = _("PaaS平台登录模块")

    @property
    def use_apigw(self):
        return settings.USE_APIGW

    def _build_url(self, new_path, old_path):
        return f"{settings.PAAS_API_HOST}{new_path}" if self.use_apigw else f"{USER_MANAGE_APIGATEWAY_ROOT}{old_path}"

    def __init__(self):
        self.get_user = DataAPI(
            method="GET",
            url=self._build_url("/api/bk-login/prod/login/api/v3/open/bk-tokens/userinfo/", "retrieve_user/"),
            module=self.MODULE,
            description="获取单个用户",
            before_request=get_user_before,
            after_request=get_user_after,
        )

        if self.use_apigw:
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
            before_request=virtual_user_before,
            module=self.MODULE,
            description="获取虚拟用户",
        )

        self.list_department_profiles = DataAPI(
            method="GET",
            url=USER_MANAGE_APIGATEWAY_ROOT + "list_profile_departments/",
            module=self.MODULE,
            description="查询用户的部门信息 (v2)",
        )


BKLoginApi = _BKLoginApi()
