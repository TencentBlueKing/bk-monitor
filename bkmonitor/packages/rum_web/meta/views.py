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
    NoDataStrategyEnableResource,
    NoDataStrategyDisableResource,
    GetStorageInfoResource,
    ListApplicationAsyncResource,
    ListApplicationResource,
    QueryRumTokenInfoResource,
    SetupApplicationResource,
    StartDataSourceResource,
    StopDataSourceResource,
    StorageFieldInfoResource,
    ListEsClusterGroupsResource,
)
from rum_web.models.application import Application
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import InstanceActionForDataPermission, ViewBusinessPermission, insert_permission_field
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class MetaInfoViewSet(ResourceViewSet):
    """RUM 元信息接口"""

    def get_permissions(self):
        return [ViewBusinessPermission()]

    resource_routes = [
        ResourceRoute("POST", GetMetaConfigInfoResource, endpoint="meta_config_info"),
        ResourceRoute("GET", ListEsClusterGroupsResource, endpoint="list_cluster_groups"),
    ]


class ApplicationViewSet(ResourceViewSet):
    """RUM 应用管理接口"""

    INSTANCE_ID = "application_id"

    def get_permissions(self):
        if self.action in [
            "delete_application",
            "start",
            "stop",
            "setup",
            "nodata_strategy_info",
            "query_rum_token",
        ]:
            return [
                InstanceActionForDataPermission(
                    "app_name",
                    [ActionEnum.MANAGE_RUM_APPLICATION],
                    ResourceEnum.RUM_APPLICATION,
                    get_instance_id=Application.get_application_id_by_app_name,
                )
            ]
        if self.action in [
            "application_info_by_app_name",
            "data_sampling",
            "data_view_config",
            "storage_field_info",
        ]:
            return [
                InstanceActionForDataPermission(
                    "app_name",
                    [ActionEnum.VIEW_RUM_APPLICATION],
                    ResourceEnum.RUM_APPLICATION,
                    get_instance_id=Application.get_application_id_by_app_name,
                )
            ]
        if self.action in [
            "nodata_strategy_enable",
            "nodata_strategy_disable",
        ]:
            return [
                InstanceActionForDataPermission(
                    self.INSTANCE_ID, [ActionEnum.MANAGE_RUM_APPLICATION], ResourceEnum.RUM_APPLICATION
                )
            ]
        return [ViewBusinessPermission()]

    resource_routes = [
        ResourceRoute("POST", CreateApplicationResource, endpoint="create_application"),
        ResourceRoute("POST", CheckDuplicateAppNameResource, endpoint="check_duplicate_app_name"),
        ResourceRoute("POST", DeleteApplicationResource, endpoint="delete_application"),
        ResourceRoute("POST", StartDataSourceResource, endpoint="start"),
        ResourceRoute("POST", StopDataSourceResource, endpoint="stop"),
        ResourceRoute(
            "POST",
            GetApplicationInfoByAppNameResource,
            endpoint="application_info_by_app_name",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.MANAGE_RUM_APPLICATION, ActionEnum.VIEW_RUM_APPLICATION],
                    resource_meta=ResourceEnum.RUM_APPLICATION,
                    id_field=lambda d: d["application_id"],
                    many=False,
                )
            ],
        ),
        ResourceRoute("POST", SetupApplicationResource, endpoint="setup"),
        ResourceRoute("POST", GetStorageInfoResource, endpoint="storage_info"),
        ResourceRoute("POST", GetIndicesInfoResource, endpoint="indices_info"),
        ResourceRoute("POST", GetDataSamplingResource, endpoint="data_sampling"),
        ResourceRoute("POST", GetNoDataStrategyInfoResource, endpoint="nodata_strategy_info"),
        ResourceRoute("POST", NoDataStrategyEnableResource, endpoint="nodata_strategy_enable"),
        ResourceRoute("POST", NoDataStrategyDisableResource, endpoint="nodata_strategy_disable"),
        ResourceRoute("POST", GetDataViewConfigResource, endpoint="data_view_config"),
        ResourceRoute(
            "POST",
            ListApplicationResource,
            endpoint="list_application",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.MANAGE_RUM_APPLICATION, ActionEnum.VIEW_RUM_APPLICATION],
                    resource_meta=ResourceEnum.RUM_APPLICATION,
                    id_field=lambda d: d["application_id"],
                    data_field=lambda d: d["data"],
                    batch_create=True,
                )
            ],
        ),
        ResourceRoute("POST", ListApplicationAsyncResource, endpoint="list_application_async"),
        ResourceRoute("POST", QueryRumTokenInfoResource, endpoint="query_rum_token"),
        ResourceRoute("POST", StorageFieldInfoResource, endpoint="storage_field_info"),
    ]
