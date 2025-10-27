"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc

from django.conf import settings

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


class CMDBBaseResource(APIResource, metaclass=abc.ABCMeta):
    module_name = "cmdb"
    return_type = list
    # CMDB API 已在请求头的 x-bkapi-authorization 中包含了 bk_username，不需要在请求参数中重复添加
    INSERT_BK_USERNAME_TO_REQUEST_DATA = False

    def use_apigw(self):
        """
        是否使用apigw
        """
        return settings.ENABLE_MULTI_TENANT_MODE or settings.CMDB_USE_APIGW

    @property
    def base_url(self):
        if self.use_apigw():
            return settings.CMDB_API_BASE_URL or f"{settings.BK_COMPONENT_API_URL}/api/bk-cmdb/prod/"
        return f"{settings.BK_COMPONENT_API_URL}/api/c/compapi/v2/cc/"

    def get_request_url(self, params: dict):
        request_url = super().get_request_url(params)
        params = params.copy()

        if "bk_supplier_account" not in params:
            params["bk_supplier_account"] = settings.BK_SUPPLIER_ACCOUNT
        return request_url.format(**params)

    def full_request_data(self, validated_request_data):
        setattr(self, "bk_username", get_backend_username(bk_tenant_id=self.bk_tenant_id))
        validated_request_data = super().full_request_data(validated_request_data)
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
            return super().perform_request(validated_request_data)
        except NoRelatedResourceError as err:
            self.report_api_failure_metric(
                error_code=getattr(err, "code", 0), exception_type=NoRelatedResourceError.__name__
            )
            return self.return_type()


class SearchSet(CMDBBaseResource):
    """
    集群查询接口
    """

    cache_type = CacheType.CC_BACKEND
    method = "POST"

    @property
    def action(self):
        return "/api/v3/set/search/{bk_supplier_account}/{bk_biz_id}" if self.use_apigw() else "/search_set/"


class SearchModule(CMDBBaseResource):
    """
    模块查询接口
    """

    cache_type = CacheType.CC_BACKEND

    @property
    def action(self):
        return (
            "/api/v3/module/search/{bk_supplier_account}/{bk_biz_id}/{bk_set_id}"
            if self.use_apigw()
            else "/search_module/"
        )

    method = "POST"

    def get_request_url(self, params: dict):
        if "bk_set_id" not in params:
            params = params.copy()
            params["bk_set_id"] = 0
        return super().get_request_url(params)


class GetBizInternalModule(CMDBBaseResource):
    """
    查询空闲模块及集群接口
    """

    cache_type = CacheType.CC_CACHE_ALWAYS

    @property
    def action(self):
        return (
            "/api/v3/topo/internal/{bk_supplier_account}/{bk_biz_id}"
            if self.use_apigw()
            else "/get_biz_internal_module/"
        )

    method = "GET"
    # 接口返回字典
    return_type = dict


class SearchBizInstTopo(CMDBBaseResource):
    """
    查询业务拓扑接口
    """

    cache_type = CacheType.CC_CACHE_ALWAYS

    @property
    def action(self):
        return "/api/v3/find/topoinst/biz/{bk_biz_id}" if self.use_apigw() else "/search_biz_inst_topo/"

    @property
    def method(self):
        return "POST" if self.use_apigw() else "GET"

    @method.setter
    def method(self, value):
        pass


class GetMainlineObjectTopo(CMDBBaseResource):
    """
    查询主线模型
    """

    cache_type = CacheType.CC_BACKEND

    @property
    def action(self):
        return "/api/v3/find/topomodelmainline" if self.use_apigw() else "/get_mainline_object_topo/"

    method = "POST"


class ListServiceInstanceDetail(CMDBBaseResource):
    """
    查询服务实例详情
    """

    # 分页接口，上层缓存封装，因此这里实时获取
    @property
    def action(self):
        return (
            "/api/v3/findmany/proc/service_instance/details" if self.use_apigw() else "/list_service_instance_detail/"
        )

    method = "POST"


class ListServiceInstanceBySetTemplate(CMDBBaseResource):
    """
    查询集群模板下的服务实例
    """

    # 分页接口，上层缓存封装，因此这里实时获取
    @property
    def action(self):
        return (
            "/api/v3/findmany/proc/service/set_template/list_service_instance/biz/{bk_biz_id}"
            if self.use_apigw()
            else "/list_service_instance_by_set_template/"
        )

    method = "POST"


class SearchObjectAttribute(CMDBBaseResource):
    """
    查询对象属性
    """

    cache_type = CacheType.CC_BACKEND

    @property
    def action(self):
        return "/api/v3/find/objectattr" if self.use_apigw() else "/search_object_attribute/"

    method = "POST"

    def full_request_data(self, validated_request_data):
        """
        这个接口传入bk_supplier_account会使用该字段进行过滤，在某些环境数据下会有问题，因此需要移除该字段
        """
        result = super().full_request_data(validated_request_data)
        result.pop("bk_supplier_account", None)
        return result


class SearchBusiness(CMDBBaseResource):
    """
    查询对象属性
    """

    cache_type = CacheType.CC_CACHE_ALWAYS

    @property
    def action(self):
        return "/api/v3/biz/search/{bk_supplier_account}" if self.use_apigw() else "/search_business/"

    method = "POST"


def return_info_with_list(*args):
    return {"info": []}


class ListServiceCategory(CMDBBaseResource):
    """
    查询服务分类列表
    """

    cache_type = CacheType.CC_CACHE_ALWAYS

    @property
    def action(self):
        return "/api/v3/findmany/proc/service_category" if self.use_apigw() else "/list_service_category/"

    method = "POST"

    return_type = return_info_with_list


class ListBizHostsTopo(CMDBBaseResource):
    """
    查询业务主机及关联拓扑
    """

    @property
    def action(self):
        return "/api/v3/hosts/app/{bk_biz_id}/list_hosts_topo" if self.use_apigw() else "/list_biz_hosts_topo/"

    method = "POST"


class ListBizHosts(CMDBBaseResource):
    """
    查询业务主机
    """

    @property
    def action(self):
        return "/api/v3/hosts/app/{bk_biz_id}/list_hosts" if self.use_apigw() else "/list_biz_hosts/"

    method = "POST"


# will be removed in version 3.8.x
class FindHostTopoRelation(CMDBBaseResource):
    """
    查询业务主机
    """

    @property
    def action(self):
        return "/api/v3/host/topo/relation/read" if self.use_apigw() else "/find_host_topo_relation/"

    method = "POST"


class FindHostBizRelation(CMDBBaseResource):
    """
    查询主机业务关系信息
    """

    @property
    def action(self):
        return "/api/v3/hosts/modules/read" if self.use_apigw() else "/find_host_biz_relations/"

    method = "POST"


class SearchCloudArea(CMDBBaseResource):
    """
    查询云区域
    """

    @property
    def action(self):
        return "/api/v3/findmany/cloudarea" if self.use_apigw() else "/search_cloud_area/"

    method = "POST"


class ListServiceTemplate(CMDBBaseResource):
    """
    查询服务模板列表
    """

    @property
    def action(self):
        return "/api/v3/findmany/proc/service_template" if self.use_apigw() else "/list_service_template/"

    method = "POST"


class ListSetTemplate(CMDBBaseResource):
    """
    查询集群模板列表
    """

    @property
    def action(self):
        return "/api/v3/findmany/topo/set_template/bk_biz_id/{bk_biz_id}" if self.use_apigw() else "/list_set_template/"

    method = "POST"


class FindHostByServiceTemplate(CMDBBaseResource):
    """
    获取服务模板下的主机
    """

    @property
    def action(self):
        return (
            "/api/v3/findmany/hosts/by_service_templates/biz/{bk_biz_id}"
            if self.use_apigw()
            else "/find_host_by_service_template/"
        )

    method = "POST"


# will be removed in version 3.8.x
class FindHostBySetTemplate(CMDBBaseResource):
    """
    获取集群模板下的主机
    """

    @property
    def action(self):
        return (
            "/api/v3/findmany/hosts/by_set_templates/biz/{bk_biz_id}"
            if self.use_apigw()
            else "/find_host_by_set_template/"
        )

    method = "POST"


class ListHostsWithoutBiz(CMDBBaseResource):
    """
    跨业务主机查询
    """

    @property
    def action(self):
        return "/api/v3/hosts/list_hosts_without_app" if self.use_apigw() else "/list_hosts_without_biz/"

    method = "POST"


class FindTopoNodePaths(CMDBBaseResource):
    """
    查询拓扑节点所在的拓扑路径
    """

    @property
    def action(self):
        return (
            "/api/v3/cache/find/cache/topo/node_path/biz/{bk_biz_id}" if self.use_apigw() else "/find_topo_node_paths/"
        )

    method = "POST"


class SearchDynamicGroup(CMDBBaseResource):
    """
    查询动态分组列表
    """

    @property
    def action(self):
        return "/api/v3/dynamicgroup/search/{bk_biz_id}" if self.use_apigw() else "/search_dynamic_group/"

    method = "POST"


class ExecuteDynamicGroup(CMDBBaseResource):
    """
    执行动态分组
    """

    @property
    def action(self):
        return "/api/v3/dynamicgroup/data/{bk_biz_id}/{id}" if self.use_apigw() else "/execute_dynamic_group/"

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
search_dynamic_group = SearchDynamicGroup()
execute_dynamic_group = ExecuteDynamicGroup()
