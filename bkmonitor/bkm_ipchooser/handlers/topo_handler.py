# -*- coding: utf-8 -*-
import itertools
import logging
import typing
from collections import defaultdict

from django.core.cache import cache

from bkm_ipchooser import constants, types
from bkm_ipchooser.api import BkApi
from bkm_ipchooser.handlers.base import BaseHandler
from bkm_ipchooser.query import resource
from bkm_ipchooser.tools import batch_request, topo_tool
from bkm_ipchooser.tools.gse_tool import fill_agent_status

logger = logging.getLogger("bkm_ipchooser")


class TopoHandler:
    @staticmethod
    def format2tree_node(bk_biz_id: int, node: types.ReadableTreeNode) -> types.TreeNode:
        return {
            "bk_obj_id": node["object_id"],
            "bk_inst_id": node["instance_id"],
            "bk_biz_id": bk_biz_id,
        }

    @staticmethod
    def format_tree(topo_tree: types.TreeNode) -> types.ReadableTreeNode:
        bk_biz_id: int = topo_tree["bk_inst_id"]
        topo_tree_stack: typing.List[types.TreeNode] = [topo_tree]
        # 定义一个通过校验的配置根节点及栈结构，同步 topo_tree_stack 进行遍历写入
        formatted_topo_tree: types.ReadableTreeNode = {}
        formatted_topo_tree_stack: typing.List[types.ReadableTreeNode] = [formatted_topo_tree]

        # 空间换时间，迭代模拟递归
        while topo_tree_stack:
            # 校验节点
            node = topo_tree_stack.pop()
            # 与 topo_tree_stack 保持相同的遍历顺序，保证构建拓扑树与给定的一致
            formatted_node = formatted_topo_tree_stack.pop()
            formatted_node.update(
                {
                    "instance_id": node["bk_inst_id"],
                    "instance_name": node["bk_inst_name"],
                    "object_id": node["bk_obj_id"],
                    "object_name": node["bk_obj_name"],
                    "meta": BaseHandler.get_meta_data(bk_biz_id),
                    "count": node.get("count", 0),
                    "child": [],
                    "expanded": True,
                }
            )
            child_nodes = node.get("child", [])
            topo_tree_stack.extend(child_nodes)
            formatted_node["child"] = [{} for __ in range(len(child_nodes))]
            formatted_topo_tree_stack.extend(formatted_node["child"])

        return formatted_topo_tree

    @classmethod
    def trees(
        cls, scope_list: types.ScopeList, count_instance_type: str = constants.InstanceType.HOST.value
    ) -> typing.List[typing.Dict]:
        if len(scope_list) == 0:
            return []

        return [
            cls.format_tree(
                topo_tool.TopoTool.get_topo_tree_with_count(
                    bk_biz_id=scope_list[0]["bk_biz_id"], count_instance_type=count_instance_type
                )
            )
        ]

    @staticmethod
    def query_path(
        scope_list: types.ScopeList,
        node_list: typing.List[types.TreeNode],
        count_instance_type: str = constants.InstanceType.HOST.value,
    ) -> typing.List[typing.List[types.TreeNode]]:
        if not node_list:
            return []
        bk_biz_id = scope_list[0]["bk_biz_id"]
        node_with_paths = topo_tool.TopoTool.find_topo_node_paths(
            bk_biz_id=bk_biz_id,
            node_list=[{"bk_inst_id": node["instance_id"], "bk_obj_id": node["object_id"]} for node in node_list],
            count_instance_type=count_instance_type,
        )

        inst_id__path_map: typing.Dict[str, typing.List[types.TreeNode]] = {}
        for node_with_path in node_with_paths:
            inst_id__path_map[
                topo_tool.TopoTool.build_inst_key(
                    object_id=node_with_path["bk_obj_id"], instance_id=node_with_path["bk_inst_id"]
                )
            ] = node_with_path.get("bk_path", [])

        node_paths_list: typing.List[typing.List[types.TreeNode]] = []
        for node in node_list:
            inst_key = topo_tool.TopoTool.build_inst_key(object_id=node["object_id"], instance_id=node["instance_id"])
            if not inst_id__path_map.get(inst_key):
                continue

            node_paths_list.append(
                [
                    {
                        "meta": BaseHandler.get_meta_data(bk_biz_id),
                        "object_id": path_node["bk_obj_id"],
                        "object_name": path_node["bk_obj_name"],
                        "instance_id": path_node["bk_inst_id"],
                        "instance_name": path_node["bk_inst_name"],
                        "count": path_node.get("count", 0),
                    }
                    for path_node in inst_id__path_map[inst_key]
                ]
            )
        return node_paths_list

    @classmethod
    def query_hosts(
        cls,
        scope_list: types.ScopeList,
        readable_node_list: typing.List[types.ReadableTreeNode],
        conditions: typing.List[types.Condition],
        start: int,
        page_size: int,
        fields: typing.List[str] = constants.CommonEnum.DEFAULT_HOST_FIELDS.value,
    ) -> typing.Dict:
        """
        查询主机
        :param scope_list
        :param readable_node_list: 拓扑节点
        :param conditions: 查询条件，TODO: 暂不支持
        :param fields: 字段
        :param start: 数据起始位置
        :param page_size: 拉取数据数量
        :return:
        """
        if not readable_node_list:
            # 不存在查询节点提前返回，减少非必要 IO
            return {"total": 0, "data": []}
        bk_biz_id = scope_list[0]["bk_biz_id"]

        # TODO: 支持全量查询
        page_size = page_size if page_size > 0 else 1000

        # 获取主机信息
        resp = cls.query_cc_hosts(
            bk_biz_id, readable_node_list, conditions, start, page_size, fields, return_status=True
        )

        return {"total": resp["count"], "data": BaseHandler.format_hosts(resp["info"], bk_biz_id)}

    @classmethod
    def query_host_id_infos(
        cls,
        scope_list: types.ScopeList,
        readable_node_list: typing.List[types.ReadableTreeNode],
        conditions: typing.List[types.Condition],
        start: int,
        page_size: int,
    ) -> typing.Dict:
        """
        查询主机 ID 信息
        :param readable_node_list: 拓扑节点
        :param conditions: 查询条件
        :param start: 数据起始位置
        :param page_size: 拉取数据数量
        :return:
        """
        if not readable_node_list:
            # 不存在查询节点提前返回，减少非必要 IO
            return {"total": 0, "data": []}

        bk_biz_id = scope_list[0]["bk_biz_id"]
        tree_node: types.TreeNode = cls.format2tree_node(bk_biz_id, readable_node_list[0])

        # TODO: 支持全量查询
        page_size = page_size if page_size > 0 else 1000

        # 获取主机信息
        resp = cls.query_cc_hosts(
            bk_biz_id,
            readable_node_list,
            conditions,
            start,
            page_size,
            ["bk_host_id", "bk_host_innerip", "bk_host_innerip_v6", "bk_cloud_id"],
        )

        return {"total": resp["count"], "data": BaseHandler.format_host_id_infos(resp["info"], tree_node["bk_biz_id"])}

    @classmethod
    def fill_agent_status(cls, cc_hosts, bk_biz_id):
        fill_agent_status(cc_hosts, bk_biz_id)

    @classmethod
    def count_agent_status(cls, cc_hosts) -> typing.Dict:
        # fill_agent_status 之后，统计主机状态
        result = {"agent_statistics": {"total_count": 0, "alive_count": 0, "not_alive_count": 0}}
        if not cc_hosts:
            return result

        result["agent_statistics"]["total_count"] = len(cc_hosts)
        for cc_host in cc_hosts:
            if cc_host.get("status", constants.AgentStatusType.NO_ALIVE.value) == constants.AgentStatusType.ALIVE.value:
                result["agent_statistics"]["alive_count"] += 1
            else:
                result["agent_statistics"]["not_alive_count"] += 1
        return result

    @classmethod
    def fill_cloud_name(cls, cc_hosts):
        if not cc_hosts:
            return

        # 补充云区域名称
        resp = BkApi.search_cloud_area({"page": {"start": 0, "limit": 1000}})

        cloud_map = (
            {cloud_info["bk_cloud_id"]: cloud_info["bk_cloud_name"] for cloud_info in resp["info"]}
            if resp.get("info")
            else {}
        )

        for host in cc_hosts:
            host["bk_cloud_name"] = cloud_map.get(host["bk_cloud_id"], host["bk_cloud_id"])

    @classmethod
    def search_cc_hosts(cls, bk_biz_id, role_host_ids, keyword):
        """搜索主机"""

        if not role_host_ids:
            return []

        # 生成主机过滤条件
        rules = [{"field": "bk_host_id", "operator": "in", "value": role_host_ids}]
        limit = len(role_host_ids)

        if keyword:
            rules.append(
                {
                    "condition": "OR",
                    "rules": [
                        {"field": field, "operator": "contains", "value": key}
                        for key in keyword.split()
                        for field in ["bk_host_name", "bk_host_innerip"]
                    ],
                }
            )

        # 获取主机信息
        resp = BkApi.list_biz_hosts(
            {
                "bk_biz_id": bk_biz_id,
                "fields": constants.CommonEnum.DEFAULT_HOST_FIELDS.value,
                "page": {"start": 0, "limit": limit, "sort": "bk_host_innerip"},
                "host_property_filter": {"condition": "AND", "rules": rules},
            },
        )
        hosts = resp["info"]

        # TODO: 抽取常用cc查询接口到一个单独的文件，目前components下很多文件都没用，比如：components/cc,cmdb,itsm等
        TopoHandler.fill_agent_status(hosts, bk_biz_id)
        TopoHandler.fill_cloud_name(hosts)

        return hosts

    @classmethod
    def query_service_instance(
        cls,
        scope_list: types.ScopeList,
        readable_node_list: typing.List[types.ReadableTreeNode] = None,
        service_instance_ids: typing.List[int] = None,
        start: int = None,
        page_size: int = None,
        search_content: str = None,
    ) -> typing.Dict:
        """
        查询服务实例
        :param scope_list: 业务范围
        :param readable_node_list: 拓扑节点
        :param service_instance_ids: 服务实例ID列表
        :param start: 数据起始位置
        :param page_size: 拉取数据数量
        :param search_content: 搜索内容
        """
        bk_biz_id = scope_list[0]["bk_biz_id"]

        # 如果没有按服务实例ID列表过滤，则查询所有服务实例
        if not service_instance_ids and not search_content:
            # 查询业务下所有服务实例（缓存5分钟）
            cache_key = f"all_service_instance_detail:{bk_biz_id}"
            service_instances: typing.List[typing.Dict] = cache.get(cache_key)
            if not service_instances:
                service_instances = batch_request.batch_request(
                    func=BkApi.list_service_instance_detail, params={"bk_biz_id": bk_biz_id}, limit=200
                )
                cache.set(cache_key, service_instances, 300)
        else:
            params = {"bk_biz_id": bk_biz_id, "service_instance_ids": service_instance_ids}
            service_instances = batch_request.batch_request(
                func=BkApi.list_service_instance_detail,
                params=params,
                limit=200,
            )

        # 将节点信息转换为模块ID
        node_set = {(node["object_id"], node["instance_id"]) for node in readable_node_list}
        if (constants.ObjectType.BIZ.value, bk_biz_id) in node_set or not node_set:
            bk_module_ids = None
        else:
            bk_module_ids = set(
                itertools.chain(*topo_tool.TopoTool.get_module_ids_by_nodes(bk_biz_id, node_set).values())
            )

        # 按模块ID过滤服务实例
        if bk_module_ids is not None:
            service_instances = [
                instance for instance in service_instances if instance["bk_module_id"] in bk_module_ids
            ]

        # 按搜索内容过滤服务实例
        if search_content:
            service_instances = [instance for instance in service_instances if search_content in instance["name"]]

        # 统计数量并分页
        total = len(service_instances)
        if start is not None and page_size > 0:
            service_instances = service_instances[start : start + page_size]

        return {
            "data": [
                {
                    "meta": BaseHandler.get_meta_data(bk_biz_id),
                    "name": service_instance["name"],
                    "id": service_instance["id"],
                    "service_instance_id": service_instance["id"],
                    "bk_module_id": service_instance["bk_module_id"],
                    "bk_host_id": service_instance["bk_host_id"],
                    "labels": service_instance["labels"],
                    "service_template_id": service_instance["service_template_id"],
                    "process_count": len(service_instance["process_instances"]),
                }
                for service_instance in service_instances
            ],
            "total": total,
        }

    @classmethod
    def query_cc_hosts(
        cls,
        bk_biz_id: int,
        readable_node_list: typing.List[types.ReadableTreeNode],
        conditions: typing.List[types.Condition],
        start: int,
        page_size: int,
        fields: typing.List[str] = constants.CommonEnum.DEFAULT_HOST_FIELDS.value,
        return_status: bool = False,
    ) -> typing.Dict:
        """
        查询主机
        :param readable_node_list: 拓扑节点
        :param conditions: 查询条件
        :param fields: 字段
        :param start: 数据起始位置
        :param page_size: 拉取数据数量
        :param return_status: 返回agent状态
        :return:
        """
        if not readable_node_list:
            return {"count": 0, "info": []}

        bk_module_ids = []
        bk_set_ids = []

        for node in readable_node_list:
            if node["object_id"] == "module":
                bk_module_ids.append(node["instance_id"])
            elif node["object_id"] == "set":
                bk_set_ids.append(node["instance_id"])

        params = {
            "bk_biz_id": bk_biz_id,
            "fields": fields,
            "page": {"start": start, "limit": page_size, "sort": "bk_host_innerip"},
        }

        # rules不能为空
        if conditions:
            params.update({"host_property_filter": {"condition": "OR", "rules": conditions}})

        if bk_module_ids:
            params.update(bk_module_ids=bk_module_ids)

        if bk_set_ids:
            params.update(bk_set_ids=bk_set_ids)

        # 获取主机信息
        resp = BkApi.list_biz_hosts(params)

        if resp["info"] and return_status:
            cls.fill_agent_status(resp["info"], bk_biz_id)

        return resp

    @classmethod
    def agent_statistics(
        cls, scope_list: types.ScopeList, node_list: typing.List[types.ReadableTreeNode]
    ) -> typing.List[typing.Dict]:
        """
        获取多个拓扑节点的主机 Agent 状态统计信息
        :param node_list: 节点信息列表
        :return:
        """
        bk_biz_id = scope_list[0]["bk_biz_id"]
        params_list = [{"bk_biz_id": bk_biz_id, "node": node} for node in node_list]
        return batch_request.request_multi_thread(
            func=cls.node_agent_statistics, params_list=params_list, get_data=lambda x: x
        )

    @classmethod
    def node_agent_statistics(cls, bk_biz_id: int, node: types.ReadableTreeNode) -> typing.Dict:
        """
        获取单个拓扑节点的主机 Agent 状态统计信息
        :param node: 节点信息
        :return:
        """
        result = {
            "node": node,
            "agent_statistics": {"total_count": 0, "alive_count": 0, "not_alive_count": 0},
        }
        object_id = node["object_id"]
        params = {"bk_biz_id": bk_biz_id, "fields": constants.CommonEnum.SIMPLE_HOST_FIELDS.value, "no_request": True}
        if object_id == constants.ObjectType.SET.value:
            params["bk_set_ids"] = [node["instance_id"]]
        if object_id == constants.ObjectType.MODULE.value:
            params["bk_module_ids"] = [node["instance_id"]]
        hosts = batch_request.batch_request(func=BkApi.list_biz_hosts, params=params)
        if not hosts:
            return result
        cls.fill_agent_status(hosts, bk_biz_id)
        result.update(cls.count_agent_status(hosts))

        return result

    @classmethod
    def node_service_instances(
        cls, scope_list: types.ScopeList, node_list: [types.ReadableTreeNode]
    ) -> typing.List[typing.Dict]:
        """
        获取服务实例数量
        """
        bk_biz_id = scope_list[0]["bk_biz_id"]

        # 服务实例信息
        nodes = {(node["object_id"], node["instance_id"]): node for node in node_list}

        # 模块ID与节点的映射关系
        topo_tree: types.TreeNode = resource.ResourceQueryHelper.get_topo_tree(bk_biz_id, return_all=True)
        node_module_ids = topo_tool.TopoTool.get_module_ids_by_nodes(
            bk_biz_id=bk_biz_id,
            topo_tree=topo_tree,
            nodes=set(nodes.keys()),
        )
        module_id_nodes = defaultdict(set)
        for node, module_ids in node_module_ids.items():
            for module_id in module_ids:
                module_id_nodes[module_id].add(node)

        # 查询服务实例
        service_instances = cls.query_service_instance(
            scope_list=[{"bk_biz_id": bk_biz_id}],
            readable_node_list=node_list,
        )["data"]

        # 统计节点服务实例数量
        node_service_instance_count = defaultdict(lambda: {"count": 0})
        for service_instance in service_instances:
            module_id = service_instance["bk_module_id"]
            for node in module_id_nodes[module_id]:
                if node not in nodes:
                    continue
                node_service_instance_count[node]["node"] = nodes[node]
                node_service_instance_count[node]["count"] += 1

        return list(node_service_instance_count.values())
