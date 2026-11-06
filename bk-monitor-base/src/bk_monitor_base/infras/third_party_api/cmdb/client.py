from abc import ABC
from typing import Any, ClassVar

from typing_extensions import override

from bk_monitor_base.infras.third_party_api.api_client import BkApiClient


class CmdbClient(BkApiClient, ABC):
    abstract_class: ClassVar[bool] = True

    # 类级别的常量
    module_name: ClassVar[str] = "cmdb"
    esb_base_url: ClassVar[str] = "api/c/compapi/v2/cc"
    apigw_base_url: ClassVar[str] = "api/bk-cmdb/prod"

    @override
    def handle_params(self, params: dict[str, Any]) -> dict[str, Any]:
        params = super().handle_params(params)
        # TODO: 可能会影响到接口的请求结果，后续需要去除这段逻辑
        # cmdb部分接口需要bk_supplier_account， 统一加上该参数
        params["bk_supplier_account"] = "0"
        return params


class SearchBusiness(CmdbClient):
    action: ClassVar[str] = "search_business"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_business"
    apigw_path: ClassVar[str] = "api/v3/biz/search/{bk_supplier_account}"


class ListBizHosts(CmdbClient):
    action: ClassVar[str] = "list_biz_hosts"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "list_biz_hosts"
    apigw_path: ClassVar[str] = "api/v3/hosts/app/{bk_biz_id}/list_hosts"


class SearchModule(CmdbClient):
    action: ClassVar[str] = "search_module"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_module"
    apigw_path: ClassVar[str] = "api/v3/module/search/{bk_supplier_account}/{bk_biz_id}/{bk_set_id}"


class SearchSet(CmdbClient):
    action: ClassVar[str] = "search_set"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_set"
    apigw_path: ClassVar[str] = "api/v3/set/search/{bk_supplier_account}/{bk_biz_id}"


class SearchObjects(CmdbClient):
    action: ClassVar[str] = "search_objects"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_objects"
    apigw_path: ClassVar[str] = "api/v3/find/object"


class SearchObjectAttribute(CmdbClient):
    action: ClassVar[str] = "search_object_attribute"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_object_attribute"
    apigw_path: ClassVar[str] = "api/v3/find/objectattr"


class ListHostsWithoutBiz(CmdbClient):
    action: ClassVar[str] = "list_hosts_without_biz"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "list_hosts_without_biz"
    apigw_path: ClassVar[str] = "api/v3/hosts/list_hosts_without_app"


class ListServiceInstance(CmdbClient):
    action: ClassVar[str] = "list_service_instance"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "list_service_instance"
    apigw_path: ClassVar[str] = "api/v3/findmany/proc/service_instance"


class SearchDynamicGroup(CmdbClient):
    action: ClassVar[str] = "search_dynamic_group"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_dynamic_group"
    apigw_path: ClassVar[str] = "api/v3/dynamicgroup/search/{bk_biz_id}"


class ExecuteDynamicGroup(CmdbClient):
    """执行动态分组

    Example:
        request:
        {
            "bk_biz_id": 1,
            "disable_counter": true,
            "id": "XXXXXXXX",
            "fields": [
                "bk_host_id",
                "bk_cloud_id",
                "bk_host_innerip",
                "bk_host_name"
            ],
            "page":{
                "start": 0,
                "limit": 10
            }
        }

        response:
        {
            "count": 1,
            "info": [
                {
                    "bk_cloud_id": 0,
                    "bk_host_id": 2,
                    "bk_host_innerip": "127.0.0.1",
                    "bk_host_name": "host12"
                },
                {
                    "bk_cloud_id": 0,
                    "bk_host_id": 9,
                    "bk_host_innerip": "127.0.0.2",
                    "bk_host_name": "host111"
                }
            ]
        }
    """

    action: ClassVar[str] = "execute_dynamic_group"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "execute_dynamic_group"
    apigw_path: ClassVar[str] = "api/v3/dynamicgroup/data/{bk_biz_id}/{id}"


class GetDynamicGroup(CmdbClient):
    """获取动态分组

    Example:
        request:
        {
            "bk_biz_id": 1,
            "id": "XXXXXXXX"
        }

        response:
        {
            "bk_biz_id": 1,
            "name": "my-dynamic-group",
            "id": "XXXXXXXX",
            "bk_obj_id": "host",
            "info": {
                "condition":[]
            },
            "create_user": "admin",
            "create_time": "2018-03-27T16:22:43.271+08:00",
            "modify_user": "admin",
            "last_time": "2018-03-27T16:29:26.428+08:00"
        }
    """

    action: ClassVar[str] = "get_dynamic_group"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "get_dynamic_group"
    apigw_path: ClassVar[str] = "api/v3/dynamicgroup/{bk_biz_id}/{id}"


class SearchBizInstTopo(CmdbClient):
    action: ClassVar[str] = "search_biz_inst_topo"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_biz_inst_topo"
    apigw_path: ClassVar[str] = "api/v3/find/topoinst/biz/{bk_biz_id}"


class GetMainlineObjectTopo(CmdbClient):
    action: ClassVar[str] = "get_mainline_object_topo"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "get_mainline_object_topo"
    apigw_path: ClassVar[str] = "api/v3/find/topomodelmainline"


class ResourceWatch(CmdbClient):
    action: ClassVar[str] = "resource_watch"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "resource_watch"
    apigw_path: ClassVar[str] = "api/v3/event/watch/resource/{bk_resource}"


class SearchInst(CmdbClient):
    action: ClassVar[str] = "search_inst"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_inst"
    apigw_path: ClassVar[str] = "api/v3/find/instassociation/object/{bk_obj_id}"


class ListBizHostsTopo(CmdbClient):
    action: ClassVar[str] = "list_biz_hosts_topo"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "list_biz_hosts_topo"
    apigw_path: ClassVar[str] = "api/v3/hosts/app/{bk_biz_id}/list_hosts_topo"


class FindTopoNodePath(CmdbClient):
    action: ClassVar[str] = "find_topo_node_path"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "find_topo_node_path"
    apigw_path: ClassVar[str] = "api/v3/cache/find/cache/topo/node_path/biz/{bk_biz_id}"


class ListServiceTemplate(CmdbClient):
    """获取服务模板列表

    Example:
        request:
        {
            "bk_biz_id": 1,
            "service_category_id": 1,
            "service_template_ids":[5,6],
            "search": "test2",
            "is_exact": true,
            "page": {
                "start": 0,
                "limit": 10,
                "sort": "-name"
            }
        }
        response:
        {
            "count": 1,
            "info": [
                {
                    "bk_biz_id": 1,
                    "id": 50,
                    "name": "test2",
                    "service_category_id": 1,
                    "creator": "admin",
                    "modifier": "admin",
                    "create_time": "2019-09-18T20:31:29.607+08:00",
                    "last_time": "2019-09-18T20:31:29.607+08:00",
                    "bk_supplier_account": "0",
                    "host_apply_enabled": false
                }
            ]
        }
    """

    action: ClassVar[str] = "list_service_template"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "list_service_template"
    apigw_path: ClassVar[str] = "api/v3/findmany/proc/service_template"


class ListSetTemplate(CmdbClient):
    """获取集群模板列表

    Example:
        request:
        {
            "bk_biz_id": 10,
            "set_template_ids":[1, 11],
            "page": {
                "start": 0,
                "limit": 10,
                "sort": "-name"
            }
        }
        response:
        {
            "count": 2,
            "info": [
                {
                    "id": 1,
                    "name": "zk1",
                    "bk_biz_id": 10,
                    "creator": "admin",
                    "modifier": "admin",
                    "create_time": "2020-03-16T15:09:23.859+08:00",
                    "last_time": "2020-03-25T18:59:00.167+08:00",
                    "bk_supplier_account": "0"
                },
                {
                    "id": 11,
                    "name": "q",
                    "bk_biz_id": 10,
                    "creator": "admin",
                    "modifier": "admin",
                    "create_time": "2020-03-16T15:10:05.176+08:00",
                    "last_time": "2020-03-16T15:10:05.176+08:00",
                    "bk_supplier_account": "0"
                }
            ]
        }
    """

    action: ClassVar[str] = "list_set_template"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "list_set_template"
    apigw_path: ClassVar[str] = "api/v3/findmany/proc/set_template"


class SearchCloudArea(CmdbClient):
    """
    查询云区域
    """

    action: ClassVar[str] = "search_cloud_area"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_cloud_area"
    apigw_path: ClassVar[str] = "/api/v3/findmany/cloudarea"


class FindHostBizRelation(CmdbClient):
    """
    查询主机业务关系信息
    """

    action: ClassVar[str] = "find_host_biz_relation_client"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "find_host_biz_relations"
    apigw_path: ClassVar[str] = "api/v3/hosts/modules/read"


class FindObjectAssociation(CmdbClient):
    """
    查询对象关联关系
    """

    action: ClassVar[str] = "find_object_association"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "find_object_association"
    apigw_path: ClassVar[str] = "api/v3/find/objectassociation"


class CountInstanceAssociations(CmdbClient):
    """
    模型实例关系数量查询
    """

    action: ClassVar[str] = "count_instance_associations"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "count_instance_associations"
    apigw_path: ClassVar[str] = "api/v3/count/instance/association"


class SearchInstanceAssociations(CmdbClient):
    """
    通用模型实例关系查询
    """

    action: ClassVar[str] = "search_instance_associations"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "search_instance_associations"
    apigw_path: ClassVar[str] = "api/v3/find/instassociation"


class FindInstanceAssociation(CmdbClient):
    """
    查询模型的实例关联关系
    """

    action: ClassVar[str] = "find_instance_association"
    method: ClassVar[str] = "POST"
    esb_path: ClassVar[str] = "find_instance_association"
    apigw_path: ClassVar[str] = "api/v3/find/instassociation"


# 实例化对象
search_business_client: SearchBusiness = SearchBusiness()
search_set_client: SearchSet = SearchSet()
search_module_client: SearchModule = SearchModule()
list_biz_hosts_client: ListBizHosts = ListBizHosts()
search_objects_client: SearchObjects = SearchObjects()
search_object_attribute_client: SearchObjectAttribute = SearchObjectAttribute()
list_hosts_without_biz_client: ListHostsWithoutBiz = ListHostsWithoutBiz()
list_service_instance_client: ListServiceInstance = ListServiceInstance()
search_dynamic_group_client: SearchDynamicGroup = SearchDynamicGroup()
execute_dynamic_group_client: ExecuteDynamicGroup = ExecuteDynamicGroup()
get_dynamic_group_client: GetDynamicGroup = GetDynamicGroup()
search_biz_inst_topo_client: SearchBizInstTopo = SearchBizInstTopo()
get_mainline_object_topo_client: GetMainlineObjectTopo = GetMainlineObjectTopo()
resource_watch_client: ResourceWatch = ResourceWatch()
search_inst_client: SearchInst = SearchInst()
list_biz_hosts_topo_client: ListBizHostsTopo = ListBizHostsTopo()
find_topo_node_path_client: FindTopoNodePath = FindTopoNodePath()
list_service_template_client: ListServiceTemplate = ListServiceTemplate()
list_set_template_client: ListSetTemplate = ListSetTemplate()
search_cloud_area_client: SearchCloudArea = SearchCloudArea()
find_host_biz_relation_client: FindHostBizRelation = FindHostBizRelation()
find_object_association_client: FindObjectAssociation = FindObjectAssociation()
count_instance_associations_client: CountInstanceAssociations = CountInstanceAssociations()
search_instance_associations_client: SearchInstanceAssociations = SearchInstanceAssociations()
find_instance_association_client: FindInstanceAssociation = FindInstanceAssociation()
