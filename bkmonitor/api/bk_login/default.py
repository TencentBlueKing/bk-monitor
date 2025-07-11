"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from rest_framework import serializers

from bkmonitor.commons.tools import batch_request
from bkmonitor.utils.cache import CacheType
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import APIResource


class BkUserApiResource(APIResource):
    INSERT_BK_USERNAME_TO_REQUEST_DATA = False

    def use_apigw(self):
        """
        是否使用apigw
        """
        return settings.ENABLE_MULTI_TENANT_MODE

    @property
    def base_url(self):
        if self.use_apigw():
            base_url = settings.BK_USER_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/bk-user/prod/"
        else:
            base_url = f"{settings.BK_COMPONENT_API_URL}/api/c/compapi/v2/usermanage/"
        return base_url

    def get_request_url(self, params: dict):
        request_url = super().get_request_url(params)
        return request_url.format(**params)

    module_name = "bk-user"

    @property
    def label(self):
        return self.__doc__


class ListTenantResource(BkUserApiResource):
    """
    获取租户列表
    [
        {
            "id": "system",
            "name": "蓝鲸运营",
            "status": "enabled"
        },
        {
            "id": "test",
            "name": "测试租户",
            "status": "disabled"
        }
    ]
    """

    action = "/api/v3/open/tenants/"
    method = "GET"

    def perform_request(self, params: dict):
        # 如果使用esb，则直接返回默认租户
        if not settings.ENABLE_MULTI_TENANT_MODE:
            return [{"id": "system", "name": "Blueking", "status": "enabled"}]

        result = super().perform_request({"bk_tenant_id": DEFAULT_TENANT_ID})
        result = [item for item in result if item["id"] in settings.INITIALIZED_TENANT_LIST]
        return result


class GetAllUserResource(BkUserApiResource):
    """
    查询用户列表
    """

    action = "/list_users/"
    method = "GET"
    cache_type = CacheType.USER

    def perform_request(self, params):
        # 如果使用apigw，则直接返回空列表，这种情况下要求前端直接请求bk-user的接口获取用户展示信息
        if self.use_apigw():
            return []
        return super().perform_request(params)


class ListDepartmentsResource(BkUserApiResource):
    """
    获取部门列表
    TODO: 后续用户管理apigw将会支持查询第一层部门
    """

    @property
    def action(self):
        return "/api/v3/open/tenant/departments/" if self.use_apigw() else "/list_departments/"

    method = "GET"
    cache_type = CacheType.USER

    class RequestSerializer(serializers.Serializer):
        lookup_field = serializers.CharField(label="查询字段", required=False)
        exact_lookups = serializers.CharField(label="精确查找", required=False)
        no_page = serializers.BooleanField(default=True, label="是否不分页")

    class ResponseSerializer(serializers.Serializer):
        id = serializers.IntegerField(label="部门 ID")
        name = serializers.CharField(label="部门名称")
        parent_id = serializers.IntegerField(label="父部门 ID", default=None, allow_null=True)

    many_response_data = True

    def perform_request(self, params: dict):
        if not self.use_apigw():
            return super().perform_request(params)

        result = batch_request(
            func=super().perform_request,
            params={},
            get_data=lambda x: x["results"],
            get_count=lambda x: x["count"],
            limit=1000,
            app="bk_login",
        )

        for item in result:
            item["parent"] = item.get("parent_id")

        # 如果查询字段为level，且精确查找为1，则只返回顶级部门
        if params.get("lookup_field") == "level" and params.get("exact_lookups") == "1":
            result = [item for item in result if not item["parent"]]

        # 如果查询字段为parent，且精确查找为0，则只返回子部门
        if params.get("lookup_field") == "parent":
            try:
                parent = int(params.get("exact_lookups"))
            except ValueError:
                raise ValueError("parent must be an integer")
            result = [item for item in result if item["parent"] == parent]

        return result


class ListProfileDepartmentsResource(BkUserApiResource):
    """
    获取用户的部门信息
    """

    ignore_error_msg_list = ["could not be found"]

    @property
    def action(self):
        if self.use_apigw():
            return "/api/v3/open/tenant/users/{bk_username}/departments/"
        return "/list_profile_departments/"

    method = "GET"
    cache_type = CacheType.USER

    class RequestSerializer(serializers.Serializer):
        id = serializers.CharField(label="用户名")
        with_family = serializers.BooleanField(label="是否返回部门树", default=True)

    class ResponseSerializer(serializers.Serializer):
        id = serializers.IntegerField(label="部门 ID")
        name = serializers.CharField(label="部门名称")

        class FamilySerializer(serializers.Serializer):
            id = serializers.IntegerField(label="部门 ID")
            name = serializers.CharField(label="部门名称")

        family = serializers.ListField(label="部门树", child=FamilySerializer(), default=[])

    many_response_data = True

    def perform_request(self, params: dict) -> list[dict]:
        """
        apigw
        [
            {
                "id": 3,
                "name": "部门C",
                "ancestors": [
                    {
                        "id": 1,
                        "name": "部门A"
                    },
                    {
                        "id": 2,
                        "name": "部门B"
                    }
                ]
            }
        ]

        esb
        [
            {
                'id': 3,
                'name': '部门C',
                'full_name': '部门A/部门B/部门C',
                'order': 1,
                'family': [
                    {
                        'id': 1,
                        'name': '部门A',
                        'full_name': '部门A',
                        'order': 1
                    },
                    {
                        'id': 2,
                        'name': '部门B',
                        'full_name': '部门A/部门B',
                        'order': 2
                    }
                ]
            }
        ]
        """
        if not self.use_apigw():
            return super().perform_request(params)

        params = {
            "bk_username": params["id"],
            "with_ancestors": params["with_family"],
        }
        result = super().perform_request(params)

        # 数据格式转换
        for item in result:
            item["family"] = item.pop("ancestors", [])

        return result


class UnityUserBaseResource(APIResource):
    base_url = settings.BK_USERINFO_API_BASE_URL
    module_name = "unity-user"


class GetUserSensitiveInfo(UnityUserBaseResource):
    """
    获取用户敏感信息
    """

    action = "/api/v1/open/odc-users/sensitive-info/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        usernames = serializers.CharField(required=True)
        fields = serializers.CharField(required=True)


class BatchLookupVirtualUserResource(BkUserApiResource):
    """
    批量查询虚拟用户
    """

    action = "/api/v3/open/tenant/virtual-users/-/lookup/"
    method = "GET"

    class RequestSerializer(serializers.Serializer):
        lookup_field = serializers.ChoiceField(choices=["bk_username", "login_name"])
        # 精确查询的值（可以为 bk_username、login_name），多个以逗号分隔，限制数量为 100，每个值最大输入长度为 64
        lookups = serializers.CharField()


class ListTenantVariablesResource(BkUserApiResource):
    """
    查询租户变量列表
    """

    action = "/api/v3/open/tenant/common-variables/"
    method = "GET"
