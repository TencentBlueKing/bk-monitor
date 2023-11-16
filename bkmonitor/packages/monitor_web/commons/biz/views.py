# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet


class BusinessListOptionViewSet(ResourceViewSet):
    """
    拉去业务列表（select2）
    """

    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.business_list_option),
    ]


class ListBusinessOfBizSetViewSet(ResourceViewSet):
    """
    展示业务集下的业务
    """

    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.list_business_of_biz_set),
    ]


class FetchBusinessInfoViewSet(ResourceViewSet):
    """
    拉取业务的详细信息(业务名字, 运维, 权限申请url(权限中心), Demo业务链接)
    """

    # 去除鉴权
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.fetch_business_info),
    ]


class ListSpacesViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.list_spaces),
    ]


class SpaceViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.list_sticky_spaces, endpoint="sticky_list"),
        ResourceRoute("POST", resource.commons.stick_space, endpoint="stick"),
        ResourceRoute("POST", resource.commons.create_space, endpoint="new"),
        ResourceRoute("GET", resource.commons.list_devops_spaces, endpoint="devops_list"),
    ]


class SpaceIntroduceViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.space_introduce),
    ]


class ListDataPipelineViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.list_data_pipeline),
    ]


class ListDataSourceByDataPipelineViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.list_data_source_by_data_pipeline),
    ]


class CreateDataPipelineViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("POST", resource.commons.create_data_pipeline),
    ]


class UpdateDataPipelineViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("POST", resource.commons.update_data_pipeline),
    ]


class GetClusterInfoViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.get_cluster_info),
    ]


class GetEtlConfigViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.get_etl_config),
    ]


class GetTransferListViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.get_transfer_list),
    ]


class CheckClusterHealthViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.check_cluster_health),
    ]


class ListClustersViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.list_clusters),
    ]


class GetStorageClusterDetailViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("GET", resource.commons.get_storage_cluster_detail),
    ]


class RegisterClusterViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("POST", resource.commons.register_cluster),
    ]


class UpdateRegisteredClusterViewSet(ResourceViewSet):
    permission_classes = ()
    resource_routes = [
        ResourceRoute("POST", resource.commons.update_registered_cluster),
    ]
