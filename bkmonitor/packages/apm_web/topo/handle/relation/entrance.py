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
from typing import List, Tuple

from apm_web.topo.constants import BarChartDataType, RelationResourcePathType
from apm_web.topo.handle.graph_plugin import PluginProvider
from apm_web.topo.handle.relation.define import Node, TreeInfo
from apm_web.topo.handle.relation.endpoint_top import (
    AlertList,
    ApdexList,
    ErrorRateCalleeList,
    ErrorRateCallerList,
    ErrorRateList,
)
from apm_web.topo.handle.relation.path import PathProvider
from apm_web.utils import merge_dicts
from bkmonitor.utils.thread_backend import ThreadPool


class RelationEntrance:
    path_type: RelationResourcePathType = RelationResourcePathType.DEFAULT

    def __init__(self, path_type, paths=None, **kwargs):
        self.path_type = path_type
        self.paths = paths
        self._runtime = kwargs

        # [!] tree_path / trees_info 会在 default 模式下进行更新
        self.tree_paths = paths
        self.trees_info = []
        self.tree_info = None

    @property
    def relation_tree(self):
        # 指定路径获取: 不请求其他路径
        if self.path_type != RelationResourcePathType.DEFAULT.value:
            tree = PathProvider(self.paths, self._runtime).build_tree()
            tree_info = self._get_tree_info(self.paths, tree)
            self.trees_info = [tree_info]
            self.tree_info = tree_info
            self.tree_paths = self.paths
            return tree

        # 默认逻辑: 从所有路径获取最完整的树并且返回所有路径的树信息
        trees = []
        tree_infos = []
        for paths in PathProvider.all_path():
            tree = PathProvider(paths, self._runtime).build_tree()
            trees.append((paths, tree))
            tree_infos.append(self._get_tree_info(paths, tree))

        best_tree, best_paths = self._find_complex(trees)
        self.tree_paths = best_paths
        self.trees_info = tree_infos
        self.tree_info = next(i for i in tree_infos if i.paths == best_paths)
        return best_tree

    def export(self, tree, export_type):
        if export_type == "tree":
            return PathProvider.get_template(self.tree_paths).to_tree_json(tree, self.trees_info)
        if export_type == "layer":
            return PathProvider.get_template(self.tree_paths).to_layers_json(tree, self.tree_info, self.trees_info)
        raise ValueError(f"[RelationTopo] 不支持以 {export_type} 格式导出关联树")

    def _find_complex(self, trees: List[Tuple[str, Node]]):
        """
        从树列表中返回最复杂的那颗
        树的得分：对每层的节点数量进行加权求和 层级越深此层级的节点权重越低
        """
        max_depth = max(PathProvider.get_depth(t[0]) for t in trees)
        the_best = None
        the_best_score = -1
        the_best_paths = None

        for i in trees:
            score = self._score_tree(i[1], 0, max_depth)
            if score > the_best_score:
                the_best_score = score
                the_best = i[1]
                the_best_paths = i[0]

        return the_best, the_best_paths

    def _score_tree(self, node, depth, max_depth):
        if depth > max_depth:
            return 0
        score = 1.0 / (depth + 1)
        for c in node.children:
            score += self._score_tree(c, depth + 1, max_depth)
        return score

    def _get_tree_info(self, paths, tree: Node) -> TreeInfo:
        """获取树的信息"""

        info = TreeInfo(
            root_id=tree.id,
            paths=paths,
            is_complete=Node.get_depth(tree) >= PathProvider.get_depth(paths),
            runtime=self._runtime,
            layers_have_data=[
                bool(Node.list_nodes_by_level(tree, layer_index))
                for layer_index in range(len(PathProvider.get_template(paths).layers))
            ],
        )

        return info


class EndpointListEntrance:
    """拓扑图服务接口"""

    handler_mapping = {
        BarChartDataType.ErrorRate.value: ErrorRateList,
        BarChartDataType.ErrorRateCaller.value: ErrorRateCallerList,
        BarChartDataType.ErrorRateCallee.value: ErrorRateCalleeList,
        BarChartDataType.Apdex.value: ApdexList,
        BarChartDataType.Alert.value: AlertList,
    }

    @classmethod
    def list_top(cls, bk_biz_id, app_name, data_type, service_name, start_time, end_time, size):
        if data_type not in cls.handler_mapping:
            raise ValueError(f"不支持根据 {data_type} 类型获取接口列表")

        handler = cls.handler_mapping[data_type](
            bk_biz_id,
            app_name,
            start_time,
            end_time,
            service_name=service_name,
            size=size,
        )

        endpoints = handler.list()
        if len(endpoints) < size:
            # 补充额外的接口
            endpoints = handler.fill_endpoints(endpoints)

        # 只获取列表中的接口 避免查询全部接口的数据
        endpoint_names = [i["name"] for i in endpoints]

        if not endpoints:
            return {"total": 0, "endpoints": []}

        # 补充指标数据
        plugins = PluginProvider.endpoint_plugins(
            runtime={
                "application": handler.application,
                "start_time": handler.start_time,
                "end_time": handler.end_time,
                "service_name": handler.service_name,
                "endpoint_names": endpoint_names,
            }
        )

        endpoint_metrics = {}
        pool = ThreadPool()
        results = pool.map_ignore_exception(lambda p: p.install(), plugins)
        for r in results:
            endpoint_metrics = merge_dicts(endpoint_metrics, r)

        # 执行 UI 插件
        endpoint_post_plugins = PluginProvider.list_endpoint_post_plugin({})
        for e in endpoints:
            e.update(endpoint_metrics.get((e["name"],), {}))
            for p in endpoint_post_plugins:
                p.process(e)

        return {"total": handler.total, "endpoints": sorted(endpoints, key=lambda i: i.get("size"), reverse=True)}
