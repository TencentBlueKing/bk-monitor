# -*- coding: utf-8 -*-
import logging
import typing
from collections import defaultdict
from copy import deepcopy

from django.core.cache import cache

from bkm_ipchooser import constants, types
from bkm_ipchooser.api import BkApi
from bkm_ipchooser.constants import InstanceType
from bkm_ipchooser.query import resource
from bkm_ipchooser.tools import batch_request

logger = logging.getLogger("bkm_ipchooser")


class TopoTool:
    CACHE_5MIN = 5 * 60

    @staticmethod
    def build_inst_key(object_id: str, instance_id: typing.Any) -> str:
        return f"{object_id}-{instance_id}"

    @classmethod
    def find_topo_node_paths(
        cls, bk_biz_id: int, node_list: typing.List[types.TreeNode], count_instance_type: str = InstanceType.HOST.value
    ):
        def _find_topo_node_paths(
            _cur_node: types.TreeNode, _cur_path: typing.List[types.TreeNode], _hit_inst_ids: typing.Set
        ):
            inst_key = cls.build_inst_key(_cur_node["bk_obj_id"], _cur_node["bk_inst_id"])
            if inst_key in inst_id__node_map:
                inst_id__node_map[inst_key]["bk_path"] = deepcopy(_cur_path)
                _hit_inst_ids.add(inst_key)
                # 全部命中后提前返回
                if len(_hit_inst_ids) == len(inst_id__node_map.keys()):
                    return

            for _child_node in _cur_node.get("child") or []:
                _cur_path.append(_child_node)
                _find_topo_node_paths(_child_node, _cur_path, _hit_inst_ids)
                # 以 del 代替 [:-1]，防止后者产生 list 对象导致路径重复压栈
                del _cur_path[-1]

        topo_tree = cls.get_topo_tree_with_count(bk_biz_id=bk_biz_id, count_instance_type=count_instance_type)
        inst_id__node_map: typing.Dict[str, types.TreeNode] = {
            cls.build_inst_key(bk_node["bk_obj_id"], bk_node["bk_inst_id"]): bk_node for bk_node in node_list
        }
        _find_topo_node_paths(topo_tree, [topo_tree], set())
        return node_list

    @classmethod
    def fill_host_count_to_tree(
        cls, nodes: typing.List[types.TreeNode], host_ids_gby_module_id: typing.Dict[int, typing.List[int]]
    ) -> typing.Set[int]:
        total_host_ids: typing.Set[int] = set()
        for node in nodes:
            bk_host_ids: typing.Set[int] = set()
            if node.get("bk_obj_id") == constants.ObjectType.MODULE.value:
                bk_host_ids = bk_host_ids | set(host_ids_gby_module_id.get(node["bk_inst_id"], set()))
            else:
                bk_host_ids = cls.fill_host_count_to_tree(node.get("child", []), host_ids_gby_module_id)
            node["count"] = len(bk_host_ids)
            total_host_ids = bk_host_ids | total_host_ids
        return total_host_ids

    @classmethod
    def get_topo_tree_with_count(
        cls,
        bk_biz_id: int,
        return_all: bool = True,
        topo_tree: types.TreeNode = None,
        count_instance_type: str = constants.InstanceType.HOST.value,
    ) -> types.TreeNode:
        topo_tree: types.TreeNode = topo_tree or resource.ResourceQueryHelper.get_topo_tree(
            bk_biz_id, return_all=return_all
        )

        # 判断需要统计的实例类型
        ids_gby_module_id: typing.Dict[int, typing.List[int]] = defaultdict(list)
        if count_instance_type == constants.InstanceType.HOST.value:
            # 查询业务下全部主机与模块的关系
            cache_key = f"host_topo_relations:{bk_biz_id}"
            host_topo_relations: typing.List[typing.Dict] = cache.get(cache_key)
            if not host_topo_relations:
                host_topo_relations = resource.ResourceQueryHelper.fetch_host_topo_relations(bk_biz_id)
                cache.set(cache_key, host_topo_relations, cls.CACHE_5MIN)

            for host_topo_relation in host_topo_relations:
                bk_host_id: int = host_topo_relation["bk_host_id"]
                # 暂不统计非缓存数据，遇到不一致的情况需要触发缓存更新
                ids_gby_module_id[host_topo_relation["bk_module_id"]].append(bk_host_id)
        else:
            # 查询业务下所有服务实例（缓存5分钟）
            cache_key = f"all_service_instance_detail:{bk_biz_id}"
            service_instances: typing.List[typing.Dict] = cache.get(cache_key)
            if not service_instances:
                service_instances = batch_request.batch_request(
                    BkApi.list_service_instance_detail, params={"bk_biz_id": bk_biz_id}, limit=200
                )
                cache.set(cache_key, service_instances, 300)
            for service_instance in service_instances:
                ids_gby_module_id[service_instance["bk_module_id"]].append(service_instance["id"])

        # 统计拓扑树上的实例数量
        cls.fill_host_count_to_tree([topo_tree], ids_gby_module_id)

        return topo_tree

    @classmethod
    def format_topo_node(cls, node: typing.Dict) -> typing.Dict:
        """
        格式化节点
        """
        return {
            "object_id": node["bk_obj_id"],
            "object_name": constants.ObjectType.get_member_value__alias_map().get(node["bk_obj_id"], ""),
            "instance_id": node["bk_inst_id"],
            "instance_name": node["bk_inst_name"],
        }

    @classmethod
    def get_module_ids_by_nodes(
        cls,
        bk_biz_id,
        nodes: typing.Set[typing.Tuple[str, int]],
        topo_tree: typing.Dict = None,
        match_all: bool = False,
    ) -> typing.Dict[typing.Tuple[str, int], typing.Set[int]]:
        """
        获取节点下的子模块ID
        """
        # 如果没有传入拓扑树，则查询拓扑树
        if not topo_tree:
            topo_tree: types.TreeNode = resource.ResourceQueryHelper.get_topo_tree(bk_biz_id, return_all=True)

        # 遍历子节点，递归获取模块ID
        bk_module_ids = defaultdict(set)
        for child_node in topo_tree.get("child", []):
            if child_node["bk_obj_id"] == constants.ObjectType.MODULE.value:
                # 如果模块存在于nodes中或父节点已匹配，则添加模块ID
                if match_all or (child_node["bk_obj_id"], child_node["bk_inst_id"]) in nodes:
                    bk_module_ids[(child_node["bk_obj_id"], child_node["bk_inst_id"])].add(child_node["bk_inst_id"])
            else:
                # 如果当前节点存在于nodes中，则其全部子节点都需要匹配
                match_all = (child_node["bk_obj_id"], child_node["bk_inst_id"]) in nodes
                sub_bk_module_ids = cls.get_module_ids_by_nodes(bk_biz_id, nodes, child_node, match_all=match_all)
                if match_all and sub_bk_module_ids:
                    bk_module_ids[(child_node["bk_obj_id"], child_node["bk_inst_id"])] = set.union(
                        *sub_bk_module_ids.values()
                    )
                bk_module_ids.update(sub_bk_module_ids)
        return bk_module_ids
