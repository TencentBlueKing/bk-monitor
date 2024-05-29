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

import abc

import six
from django.conf import settings
from gevent.monkey import saved

from bkm_space.errors import NoRelatedResourceError
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.user import get_backend_username
from core.drf_resource.contrib.api import APIResource

__all__ = [
    "search_module",
    "search_set",
    "search_cloud_area",
    "get_biz_internal_module",
    "search_biz_inst_topo",
    "get_mainline_object_topo",
    "list_service_instance_detail",
    "search_object_attribute",
    "search_business",
    "list_service_category",
    "list_biz_hosts",
    "list_biz_hosts_topo",
    "find_host_topo_relation",
]


gevent_active = "time" in saved


class CMDBBaseResource(six.with_metaclass(abc.ABCMeta, APIResource)):
    # 这里为啥不用https？
    # 因为python3.6 + gevent模式下，ssl库会出现如下异常
    # RecursionError: maximum recursion depth exceeded
    if gevent_active:
        base_url = "%s/api/c/compapi/v2/cc/" % settings.BK_COMPONENT_API_URL.replace("https://", "http://")
    else:
        base_url = "%s/api/c/compapi/v2/cc/" % settings.BK_COMPONENT_API_URL

    module_name = "cmdb"

    return_type = list

    def full_request_data(self, validated_request_data):
        setattr(self, "bk_username", get_backend_username())
        validated_request_data = super(CMDBBaseResource, self).full_request_data(validated_request_data)
        validated_request_data.update(bk_supplier_account=settings.BK_SUPPLIER_ACCOUNT)
        # 业务id判定
        if "bk_biz_id" not in validated_request_data:
            return validated_request_data
        # 业务id关联
        bk_biz_id = int(validated_request_data["bk_biz_id"])
        validated_request_data["bk_biz_id"] = validate_bk_biz_id(bk_biz_id)
        return validated_request_data

    def perform_request(self, validated_request_data):
        # 非cmdb空间兼容，无关联资源捕获异常返回空数据
        try:
            return super(CMDBBaseResource, self).perform_request(validated_request_data)
        except NoRelatedResourceError as err:
            self.report_api_failure_metric(
                error_code=getattr(err, 'code', 0), exception_type=NoRelatedResourceError.__name__
            )
            return self.return_type()


class SearchSet(CMDBBaseResource):
    """
    集群查询接口
    """

    cache_type = CacheType.CC_BACKEND
    action = "search_set"
    method = "POST"


class SearchModule(CMDBBaseResource):
    """
    模块查询接口
    """

    cache_type = CacheType.CC_BACKEND
    action = "search_module"
    method = "POST"


class GetBizInternalModule(CMDBBaseResource):
    """
    查询空闲模块及集群接口
    """

    cache_type = CacheType.CC_CACHE_ALWAYS
    action = "get_biz_internal_module"
    method = "GET"
    # 接口返回字典
    return_type = dict


class SearchBizInstTopo(CMDBBaseResource):
    """
    查询业务拓扑接口
    """

    cache_type = CacheType.CC_CACHE_ALWAYS
    action = "search_biz_inst_topo"
    method = "GET"


class GetMainlineObjectTopo(CMDBBaseResource):
    """
    查询主线模型
    """

    cache_type = CacheType.CC_BACKEND
    action = "get_mainline_object_topo"
    method = "GET"


class ListServiceInstanceDetail(CMDBBaseResource):
    """
    查询服务实例详情
    """

    # 分页接口，上层缓存封装，因此这里实时获取
    action = "list_service_instance_detail"
    method = "POST"


class ListServiceInstanceBySetTemplate(CMDBBaseResource):
    """
    查询集群模板下的服务实例
    """

    # 分页接口，上层缓存封装，因此这里实时获取
    action = "list_service_instance_by_set_template"
    method = "POST"


class SearchObjectAttribute(CMDBBaseResource):
    """
    查询对象属性
    """

    cache_type = CacheType.CC_BACKEND
    action = "search_object_attribute"
    method = "POST"


class SearchBusiness(CMDBBaseResource):
    """
    查询对象属性
    """

    cache_type = CacheType.CC_CACHE_ALWAYS
    action = "search_business"
    method = "POST"


def return_info_with_list(*args):
    return {"info": []}


class ListServiceCategory(CMDBBaseResource):
    """
    查询服务分类列表
    """

    cache_type = CacheType.CC_CACHE_ALWAYS
    action = "list_service_category"
    method = "POST"

    return_type = return_info_with_list


class ListBizHostsTopo(CMDBBaseResource):
    """
    查询业务主机及关联拓扑
    """

    action = "list_biz_hosts_topo"
    method = "POST"


class ListBizHosts(CMDBBaseResource):
    """
    查询业务主机
    """

    action = "list_biz_hosts"
    method = "POST"


# will be removed in version 3.8.x
class FindHostTopoRelation(CMDBBaseResource):
    """
    查询业务主机
    """

    action = "find_host_topo_relation"
    method = "POST"


class FindHostBizRelation(CMDBBaseResource):
    """
    查询主机业务关系信息
    """

    action = "find_host_biz_relations"
    method = "POST"


class SearchCloudArea(CMDBBaseResource):
    """
    查询云区域
    """

    action = "search_cloud_area"
    method = "POST"


class ListServiceTemplate(CMDBBaseResource):
    """
    查询服务模板列表
    """

    action = "list_service_template"
    method = "POST"


class ListSetTemplate(CMDBBaseResource):
    """
    查询集群模板列表
    """

    action = "list_set_template"
    method = "POST"


class FindHostByServiceTemplate(CMDBBaseResource):
    """
    获取服务模板下的主机
    """

    action = "find_host_by_service_template"
    method = "POST"


# will be removed in version 3.8.x
class FindHostBySetTemplate(CMDBBaseResource):
    """
    获取集群模板下的主机
    """

    action = "find_host_by_set_template"
    method = "POST"


class ListHostsWithoutBiz(CMDBBaseResource):
    """
    跨业务主机查询
    """

    action = "list_hosts_without_biz"
    method = "POST"


class FindTopoNodePaths(CMDBBaseResource):
    """
    查询拓扑节点所在的拓扑路径
    """

    action = "find_topo_node_paths"
    method = "POST"


search_set = SearchSet()
search_module = SearchModule()
list_biz_hosts_topo = ListBizHostsTopo()
list_biz_hosts = ListBizHosts()
find_host_topo_relation = FindHostTopoRelation()
get_biz_internal_module = GetBizInternalModule()
get_mainline_object_topo = GetMainlineObjectTopo()
search_biz_inst_topo = SearchBizInstTopo()
list_service_instance_detail = ListServiceInstanceDetail()
list_service_instance_by_set_template = ListServiceInstanceBySetTemplate()
search_object_attribute = SearchObjectAttribute()
search_business = SearchBusiness()
list_service_category = ListServiceCategory()
search_cloud_area = SearchCloudArea()
list_service_template = ListServiceTemplate()
list_set_template = ListSetTemplate()
find_host_by_set_template = FindHostBySetTemplate()
find_host_by_service_template = FindHostByServiceTemplate()
list_hosts_without_biz = ListHostsWithoutBiz()
find_host_biz_relation = FindHostBizRelation()
find_topo_node_paths = FindTopoNodePaths()
