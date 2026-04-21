"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from rum_web.meta.resources import (
    CheckDuplicateAppNameResource,
    CreateApplicationResource,
    DeleteApplicationResource,
    GetApplicationInfoByAppNameResource,
    GetDataSamplingResource,
    GetDataViewConfigResource,
    GetIndicesInfoResource,
    GetMetaConfigInfoResource,
    GetNoDataStrategyInfoResource,
    GetStorageInfoResource,
    ListApplicationAsyncResource,
    ListApplicationResource,
    QueryRumTokenInfoResource,
    SetupApplicationResource,
    StartDataSourceResource,
    StopDataSourceResource,
    StorageFieldInfoResource,
)
from bkmonitor.iam.drf import ViewBusinessPermission
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class MetaInfoViewSet(ResourceViewSet):
    """RUM 元信息接口"""

    def get_permissions(self):
        return [ViewBusinessPermission()]

    resource_routes = [
        ResourceRoute("POST", GetMetaConfigInfoResource, endpoint="meta_config_info"),
    ]


class ApplicationViewSet(ResourceViewSet):
    """RUM 应用管理接口"""

    def get_permissions(self):
        return [ViewBusinessPermission()]

    resource_routes = [
        ResourceRoute("POST", CreateApplicationResource, endpoint="create_application"),
        ResourceRoute("POST", CheckDuplicateAppNameResource, endpoint="check_duplicate_app_name"),
        ResourceRoute("POST", DeleteApplicationResource, endpoint="delete_application"),
        ResourceRoute("POST", StartDataSourceResource, endpoint="start"),
        ResourceRoute("POST", StopDataSourceResource, endpoint="stop"),
        ResourceRoute("POST", GetApplicationInfoByAppNameResource, endpoint="application_info_by_app_name"),
        ResourceRoute("POST", SetupApplicationResource, endpoint="setup"),
        ResourceRoute("POST", GetStorageInfoResource, endpoint="storage_info"),
        ResourceRoute("POST", GetIndicesInfoResource, endpoint="indices_info"),
        ResourceRoute("POST", GetDataSamplingResource, endpoint="data_sampling"),
        ResourceRoute("POST", GetNoDataStrategyInfoResource, endpoint="nodata_strategy_info"),
        ResourceRoute("POST", GetDataViewConfigResource, endpoint="data_view_config"),
        ResourceRoute("POST", ListApplicationResource, endpoint="list_application"),
        ResourceRoute("POST", ListApplicationAsyncResource, endpoint="list_application_async"),
        ResourceRoute("POST", QueryRumTokenInfoResource, endpoint="query_rum_token"),
        ResourceRoute("POST", StorageFieldInfoResource, endpoint="storage_field_info"),
    ]
