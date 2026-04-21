"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings

from core.drf_resource.contrib.nested_api import KernelAPIResource


class RumAPIGWResource(KernelAPIResource):
    TIMEOUT = 300
    base_url_statement = None
    base_url = (
        settings.NEW_MONITOR_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/bk-monitor/{settings.APIGW_STAGE}/"
    )

    # 模块名
    module_name = "rum_api"

    @property
    def label(self):
        return self.__doc__


class CreateApplicationResource(RumAPIGWResource):
    """创建 RUM 应用"""

    action = "/app/rum/create_rum_application/"
    method = "POST"


class DeleteApplicationResource(RumAPIGWResource):
    """删除 RUM 应用"""

    action = "/app/rum/delete_rum_application/"
    method = "POST"


class ListApplicationResource(RumAPIGWResource):
    """获取 RUM 应用列表"""

    action = "/app/rum/list_rum_application/"
    method = "GET"


class DetailApplicationResource(RumAPIGWResource):
    """获取 RUM 应用详情"""

    action = "/app/rum/detail_rum_application/"
    method = "GET"


class StartApplicationResource(RumAPIGWResource):
    """启动 RUM 应用"""

    action = "/app/rum/start_rum_application/"
    method = "GET"


class StopApplicationResource(RumAPIGWResource):
    """停止 RUM 应用"""

    action = "/app/rum/stop_rum_application/"
    method = "GET"


class ApplyDatasourceResource(RumAPIGWResource):
    """创建或更新 RUM 数据源"""

    action = "/app/rum/apply_rum_datasource/"
    method = "POST"


class QueryBkDataTokenInfoResource(RumAPIGWResource):
    """查询 RUM 数据上报 Token"""

    action = "/app/rum/query_rum_bk_data_token/"
    method = "GET"


class GetApplicationConfigResource(RumAPIGWResource):
    """获取 RUM 应用配置"""

    action = "/app/rum/query_rum_application_config/"
    method = "GET"


class ReleaseAppConfigResource(RumAPIGWResource):
    """发布 RUM 应用配置"""

    action = "/app/rum/release_rum_app_config/"
    method = "POST"


class DeleteAppConfigResource(RumAPIGWResource):
    """删除 RUM 应用配置"""

    action = "/app/rum/delete_rum_app_config/"
    method = "POST"
