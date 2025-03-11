"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings

from core.drf_resource import APIResource


class BkUserAPIGWResource(APIResource):
    base_url = settings.BK_USER_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/bk-user/prod/"
    module_name = "bk-user"

    @property
    def label(self):
        return self.__doc__


class ListTenantResource(BkUserAPIGWResource):
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
