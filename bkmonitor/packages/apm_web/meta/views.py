# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from apm_web.meta.resources import (
    ApplicationInfoByAppNameResource,
    ApplicationInfoResource,
    CheckDuplicateNameResource,
    CreateApplicationResource,
    CustomServiceConfigResource,
    CustomServiceDataSourceResource,
    CustomServiceDataViewResource,
    CustomServiceListResource,
    CustomServiceMatchListResource,
    DataSamplingResource,
    DataViewConfigResource,
    DeleteApplicationResource,
    DeleteCustomSeriviceResource,
    DimensionDataResource,
    EndpointDetailResource,
    GETDataEncodingResource,
    IndicesInfoResource,
    InstanceDiscoverKeysResource,
    ListApplicationAsyncResource,
    ListApplicationInfoResource,
    ListApplicationResource,
    ListEsClusterGroupsResource,
    MetaConfigInfoResource,
    MetricInfoResource,
    ModifyMetricResource,
    NoDataStrategyDisableResource,
    NoDataStrategyEnableResource,
    NoDataStrategyInfoResource,
    PushUrlResource,
    QueryBkDataToken,
    QueryEndpointStatisticsResource,
    QueryExceptionDetailEventResource,
    QueryExceptionEndpointResource,
    QueryExceptionEventResource,
    QueryExceptionTypeGraphResource,
    SamplingOptionsResource,
    ServiceDetailResource,
    ServiceListResource,
    SetupResource,
    SimpleServiceList,
    StartResource,
    StopResource,
    StorageFieldInfoResource,
)
from apm_web.models import Application
from bkmonitor.iam import ActionEnum, ResourceEnum
from bkmonitor.iam.drf import (
    InstanceActionForDataPermission,
    InstanceActionPermission,
    ViewBusinessPermission,
    insert_permission_field,
)
from core.drf_resource import api
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class MetaInfoViewSet(ResourceViewSet):
    def get_permissions(self):
        return [ViewBusinessPermission()]

    resource_routes = [
        ResourceRoute("GET", api.apm_api.list_meta_es_cluster_info, endpoint="list_es_cluster_info"),
        ResourceRoute("GET", MetaConfigInfoResource, endpoint="meta_config_info"),
        ResourceRoute("GET", PushUrlResource, endpoint="push_url"),
        ResourceRoute("GET", ListEsClusterGroupsResource, endpoint="list_cluster_groups"),
    ]


class ApplicationViewSet(ResourceViewSet):
    INSTANCE_ID = "application_id"

    def get_permissions(self):
        if self.action in [
            "application_info",
            "metric_info",
            "data_sampling",
            "storage_field_info",
            "data_view_config",
            "dimension_count",
        ]:
            return [
                InstanceActionPermission([ActionEnum.VIEW_APM_APPLICATION], ResourceEnum.APM_APPLICATION),
            ]
        if self.action in [
            "setup",
            "start",
            "stop",
            "query_bk_data_token",
            "nodata_strategy_info",
            "nodata_strategy_enable",
            "nodata_strategy_disable",
        ]:
            return [
                InstanceActionForDataPermission(
                    self.INSTANCE_ID, [ActionEnum.MANAGE_APM_APPLICATION], ResourceEnum.APM_APPLICATION
                )
            ]
        if self.action in ["application_info_by_app_name", "service_detail", "simple_service_list"]:
            return [
                InstanceActionForDataPermission(
                    "app_name",
                    [ActionEnum.VIEW_APM_APPLICATION],
                    ResourceEnum.APM_APPLICATION,
                    get_instance_id=Application.get_application_id_by_app_name,
                )
            ]
        return [ViewBusinessPermission()]

    resource_routes = [
        ResourceRoute(
            "GET",
            ListApplicationInfoResource,
            "list_application_info",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.MANAGE_APM_APPLICATION, ActionEnum.VIEW_APM_APPLICATION],
                    resource_meta=ResourceEnum.APM_APPLICATION,
                    id_field=lambda d: d["application_id"],
                    instance_create_func=ResourceEnum.APM_APPLICATION.create_instance_by_info,
                )
            ],
        ),
        ResourceRoute(
            "POST",
            ListApplicationResource,
            endpoint="list_application",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.MANAGE_APM_APPLICATION, ActionEnum.VIEW_APM_APPLICATION],
                    resource_meta=ResourceEnum.APM_APPLICATION,
                    id_field=lambda d: d["application_id"],
                    data_field=lambda d: d["data"],
                    batch_create=True,
                )
            ],
        ),
        ResourceRoute(
            "GET",
            MetricInfoResource,
            endpoint="metric_info",
            pk_field="application_id",
        ),
        ResourceRoute(
            "POST",
            DimensionDataResource,
            endpoint="dimension_data",
            pk_field="application_id",
        ),
        ResourceRoute(
            "POST",
            ModifyMetricResource,
            endpoint="modify_metric",
            pk_field="application_id",
        ),
        ResourceRoute(
            "GET",
            ApplicationInfoResource,
            endpoint="application_info",
            pk_field="application_id",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.MANAGE_APM_APPLICATION, ActionEnum.VIEW_APM_APPLICATION],
                    resource_meta=ResourceEnum.APM_APPLICATION,
                    id_field=lambda d: d["application_id"],
                    many=False,
                )
            ],
        ),
        ResourceRoute(
            "GET",
            ApplicationInfoByAppNameResource,
            endpoint="application_info_by_app_name",
            decorators=[
                insert_permission_field(
                    actions=[ActionEnum.MANAGE_APM_APPLICATION, ActionEnum.VIEW_APM_APPLICATION],
                    resource_meta=ResourceEnum.APM_APPLICATION,
                    id_field=lambda d: d["application_id"],
                    many=False,
                )
            ],
        ),
        ResourceRoute("POST", ListApplicationAsyncResource, endpoint="list_application_async"),
        ResourceRoute("POST", InstanceDiscoverKeysResource, endpoint="instance_discover_keys"),
        ResourceRoute("POST", ServiceDetailResource, endpoint="service_detail"),
        ResourceRoute("POST", EndpointDetailResource, endpoint="endpoint_detail"),
        ResourceRoute("POST", ServiceListResource, endpoint="service_list"),
        ResourceRoute("POST", QueryExceptionEventResource, endpoint="query_exception_event"),
        ResourceRoute("POST", QueryExceptionDetailEventResource, endpoint="query_exception_detail_event"),
        ResourceRoute("POST", QueryExceptionEndpointResource, endpoint="query_exception_endpoint"),
        ResourceRoute("POST", QueryExceptionTypeGraphResource, endpoint="query_exception_type_graph"),
        ResourceRoute("POST", QueryEndpointStatisticsResource, endpoint="query_endpoint_statistics"),
        ResourceRoute("GET", QueryBkDataToken, endpoint="query_bk_data_token", pk_field="application_id"),
        ResourceRoute("GET", CheckDuplicateNameResource, endpoint="check_duplicate_app_name"),
        ResourceRoute("GET", IndicesInfoResource, endpoint="indices_info", pk_field="application_id"),
        ResourceRoute("POST", CreateApplicationResource, endpoint="create_application"),
        ResourceRoute("POST", DeleteApplicationResource, endpoint="delete_application"),
        ResourceRoute("POST", SetupResource, endpoint="setup"),
        ResourceRoute("GET", SamplingOptionsResource, endpoint="sampling_options"),
        ResourceRoute("POST", StartResource, endpoint="start"),
        ResourceRoute("POST", StopResource, endpoint="stop"),
        ResourceRoute("POST", NoDataStrategyInfoResource, endpoint="nodata_strategy_info"),
        ResourceRoute("POST", NoDataStrategyEnableResource, endpoint="nodata_strategy_enable"),
        ResourceRoute("POST", NoDataStrategyDisableResource, endpoint="nodata_strategy_disable"),
        ResourceRoute("POST", DataViewConfigResource, endpoint="data_view_config", pk_field="application_id"),
        ResourceRoute("POST", DataSamplingResource, "data_sampling", pk_field="application_id"),
        ResourceRoute("POST", StorageFieldInfoResource, endpoint="storage_field_info", pk_field="application_id"),
        # --- 自定义远程服务
        ResourceRoute("GET", CustomServiceListResource, endpoint="custom_service_list"),
        ResourceRoute("POST", CustomServiceConfigResource, endpoint="custom_service_config"),
        ResourceRoute("POST", DeleteCustomSeriviceResource, endpoint="delete_custom_service"),
        ResourceRoute("POST", CustomServiceMatchListResource, endpoint="custom_service_match_list"),
        ResourceRoute(
            "POST", CustomServiceDataViewResource, endpoint="custom_service_data_view_config", pk_field="application_id"
        ),
        ResourceRoute("POST", CustomServiceDataSourceResource, endpoint="custom_service_url_list"),
        ResourceRoute("GET", GETDataEncodingResource, endpoint="data_encoding"),
        ResourceRoute("POST", SimpleServiceList, endpoint="simple_service_list"),
    ]
