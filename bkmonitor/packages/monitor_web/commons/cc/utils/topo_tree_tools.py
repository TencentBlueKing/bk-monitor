# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


import copy

from core.drf_resource import resource
from bkmonitor.utils.thread_backend import InheritParentThread


def foreach_topo_tree(topo, func=None, topo_link=None, order="asc", *args, **kwargs):
    """
    遍历处理拓扑树方法
    :param topo: 传入需要处理的topo树
    :param func: 具体处理方法，方法接收参数：node（当前节点），node_link（节点的路径），*args，**kwargs
    :param topo_link: 不需传此参数
    :param order: 处理节点的顺序，asc: 从根节点开始处理，desc：从叶子节点开始处理
    :param args:
    :param kwargs:
    :return:
    """
    # 从上到下遍历topo树
    if isinstance(topo, dict):
        # 记录层级
        try:
            inst_key = "{}|{}".format(topo["bk_obj_id"], topo["bk_inst_id"])
        except KeyError:
            if topo.get("ip"):
                inst_key = "{}|{}".format(topo.get("ip"), topo.get("bk_cloud_id"))
            elif topo.get("service_instance_id"):
                inst_key = "service|{}".format(topo.get("service_instance_id"))
            else:
                inst_key = ""
        topo_link = topo_link or []
        c_topo_link = copy.deepcopy(topo_link)
        c_topo_link.append(inst_key)
        # 执行操作
        if func and order == "asc":
            func(topo, c_topo_link, *args, **kwargs)

        child = topo.get("child")
        if child:
            foreach_topo_tree(child, func, c_topo_link, order, *args, **kwargs)

        if func and order == "desc":
            func(topo, c_topo_link, *args, **kwargs)

    if isinstance(topo, list):
        for item in topo:
            c_topo_link = copy.deepcopy(topo_link)
            foreach_topo_tree(item, func, c_topo_link, order, *args, **kwargs)


def get_node_mapping(topo_tree):
    """
    获取所有节点的映射
    """
    node_mapping = {}

    def mapping(node, node_link, node_mapping):
        node.update(node_link=node_link)
        node_mapping[node_link[-1]] = node

    foreach_topo_tree(topo_tree, mapping, node_mapping=node_mapping)
    return node_mapping


def get_inst_key(node):
    """
    获取节点的键名
    """
    try:
        return "{}|{}".format(node["bk_obj_id"], node["bk_inst_id"])
    except KeyError:
        return None


def get_node_path(inst_key, node_mapping):
    """
    获取节点的全路径
    """
    node_link = node_mapping.get(inst_key, {}).get("node_link", [])
    return " / ".join([node_mapping.get(key).get("bk_inst_name") for key in node_link])


def get_module_by_node(node):
    """
    获取节点下的模块id集合
    """
    if not node:
        return set()

    if node["bk_obj_id"] == "module":
        return {node["bk_inst_id"]}

    module_ids = set()

    def search_module(node, node_link, module_ids):
        if node["bk_obj_id"] == "module":
            module_ids.add(node["bk_inst_id"])

    foreach_topo_tree(node, search_module, module_ids=module_ids)
    return module_ids


def get_module_by_node_list(node_list, topo_tree):
    """
    获取节点列表锁包含的module集合
    """
    node_mapping = get_node_mapping(topo_tree)
    contained_module_ids = set()
    for node in node_list:
        inst_key = get_inst_key(node)
        if inst_key in node_mapping:
            module_ids = get_module_by_node(node_mapping[inst_key])
            contained_module_ids = contained_module_ids | module_ids

    return contained_module_ids


def get_module_mapping(topo_tree):
    """
    获取所有节点下面的模块的映射
    """
    module_mapping = {}

    def mapping(node, node_link, module_mapping):
        if node.get("bk_obj_id") == "module":
            module_mapping[node_link[-1]] = node

    foreach_topo_tree(topo_tree, mapping, module_mapping=module_mapping)
    return module_mapping


def get_module(bk_obj_id, bk_inst_id, topo):
    """
    获取节点下的所有模块(弃用)
    """
    module_id_list = []

    def _find_module(node, node_link, module_id_list):
        if node["bk_obj_id"] != "set":
            return False
        inst_key = "{}|{}".format(bk_obj_id, bk_inst_id)
        children = node.get("child")
        if children:
            for item in children:
                if inst_key in node_link or (bk_obj_id == "module" and bk_inst_id == item["bk_inst_id"]):
                    module_id_list.append({"bk_set_id": node["bk_inst_id"], "bk_module_id": item["bk_inst_id"]})

    foreach_topo_tree(topo, _find_module, module_id_list=module_id_list)
    return module_id_list


def get_biz_topo_tree(biz_id_list):
    """
    拉取业务列表下的拓扑树
    """
    topo_tree_result_dict = {}

    def get_single_data(bk_biz_id):
        topo_tree_in_biz = resource.cc.topo_tree(bk_biz_id)
        topo_tree_result_dict[bk_biz_id] = topo_tree_in_biz

    th_list = [InheritParentThread(target=get_single_data, args=(bk_biz_id,)) for bk_biz_id in biz_id_list]
    list([t.start() for t in th_list])
    list([t.join() for t in th_list])
    return topo_tree_result_dict
