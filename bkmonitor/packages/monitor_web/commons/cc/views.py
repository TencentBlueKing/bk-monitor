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


class CountryListViewSet(ResourceViewSet):
    """
    获取国家地区城市列表
    """

    resource_routes = [
        ResourceRoute("GET", resource.commons.country_list),
    ]


class ISPListViewSet(ResourceViewSet):
    """
    获取运营商列表
    """

    resource_routes = [
        ResourceRoute("GET", resource.commons.isp_list),
    ]


class HostRegionISPInfoViewSet(ResourceViewSet):
    """
    获取运营商列表
    """

    resource_routes = [
        ResourceRoute("GET", resource.commons.host_region_isp_info),
    ]


class CCTopoTreeViewSet(ResourceViewSet):
    """
    获取业务拓扑树
    """

    resource_routes = [ResourceRoute("GET", resource.commons.cc_topo_tree)]


class GetTopoTree(ResourceViewSet):
    """
    获取拓扑树
    """

    resource_routes = [ResourceRoute("POST", resource.commons.get_topo_tree)]


class GetHostInstanceByIpViewSet(ResourceViewSet):
    """
    根据IP获取主机状态
    """

    resource_routes = [ResourceRoute("POST", resource.commons.get_host_instance_by_ip)]


class GetHostInstanceByNodeViewSet(ResourceViewSet):
    """
    获取节点下主机状态
    """

    resource_routes = [ResourceRoute("POST", resource.commons.get_host_instance_by_node)]


class GetServiceInstanceByNodeViewSet(ResourceViewSet):
    """
    获取节点服务实例状态
    """

    resource_routes = [ResourceRoute("POST", resource.commons.get_service_instance_by_node)]


class GetServiceCategoryViewSet(ResourceViewSet):
    """
    # 获取服务分类列表
    """

    resource_routes = [ResourceRoute("POST", resource.commons.get_service_category)]


class HostAgentStatusViewSet(ResourceViewSet):
    """
    获取主机状态
    """

    resource_routes = [ResourceRoute("POST", resource.commons.host_agent_status)]


class GetMainlineObjectTopo(ResourceViewSet):
    resource_routes = [ResourceRoute("GET", resource.commons.get_mainline_object_topo)]


class GetTemplateViewSet(ResourceViewSet):
    """
    获取业务下的集群模板/服务模板
    """

    resource_routes = [ResourceRoute("POST", resource.commons.get_template)]


class GetNodesByTemplateViewSet(ResourceViewSet):
    """
    获取模板下的拓扑节点
    """

    resource_routes = [ResourceRoute("POST", resource.commons.get_nodes_by_template)]


class GetBusinessTargetDetailViewSet(ResourceViewSet):
    """
    获取模板下的拓扑节点
    """

    resource_routes = [ResourceRoute("POST", resource.commons.get_business_target_detail)]


class GetTopoListViewSet(ResourceViewSet):
    """
    获取节点信息列表
    """

    resource_routes = [ResourceRoute("POST", resource.commons.get_topo_list)]
