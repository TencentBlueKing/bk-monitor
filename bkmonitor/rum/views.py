"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from rum.resources import (
    AppConfigResource,
    ApplicationInfoResource,
    ApplyDatasourceResource,
    CreateApplicationResource,
    DeleteAppConfigResource,
    DeleteApplicationResource,
    ListApplicationResources,
    QueryBkDataTokenInfoResource,
    ReleaseAppConfigResource,
    StartApplicationResource,
    StopApplicationResource,
)


class RumApplicationViewSet(ResourceViewSet):
    resource_routes = [
        # 应用生命周期
        ResourceRoute("POST", CreateApplicationResource, endpoint="create_application"),
        ResourceRoute("POST", DeleteApplicationResource, endpoint="delete_application"),
        ResourceRoute("GET", ListApplicationResources, endpoint="list_application"),
        ResourceRoute("GET", ApplicationInfoResource, endpoint="detail_application"),
        # 应用启停（整体，无 type 参数）
        ResourceRoute("GET", StartApplicationResource, endpoint="start_application"),
        ResourceRoute("GET", StopApplicationResource, endpoint="stop_application"),
        # 数据源
        ResourceRoute("POST", ApplyDatasourceResource, endpoint="apply_datasource"),
        ResourceRoute("GET", QueryBkDataTokenInfoResource, endpoint="query_bk_data_token_info"),
        # 配置管理
        ResourceRoute("GET", AppConfigResource, endpoint="application_config"),
        ResourceRoute("POST", ReleaseAppConfigResource, endpoint="release_app_config"),
        ResourceRoute("POST", DeleteAppConfigResource, endpoint="delete_app_config"),
    ]
