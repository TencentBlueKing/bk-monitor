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
"""
# 清理计算平台dataflow中，冗余的存储节点
"""
import time

from django.conf import settings
from django.core.management import BaseCommand

from bkmonitor.dataflow.node.storage import TSpiderStorageNode
from constants.dataflow import ConsumingMode
from core.drf_resource import api


class Command(BaseCommand):
    def handle(self, **kwargs):
        self.migrate_cmdb_level_dataflow()

    def migrate_cmdb_level_dataflow(self):
        # 1. 获取当前cmdb level 的所有dataflow。
        params = {"project_id": settings.BK_DATA_PROJECT_ID}
        flows = api.bkdata.get_data_flow_list(**params)
        target_flows = [f for f in flows if "CMDB预聚合" in f["flow_name"]]
        # 2. 处理flow中的节点，删除中间tspider节点
        for flow in target_flows:
            flow_id = flow["flow_id"]
            # 2.1 获取节点列表
            nodes = api.bkdata.get_data_flow_graph(flow_id=flow_id).get("nodes", [])
            print(f"flow({flow_id}): get flow nodes: {len(nodes)}")
            if not nodes:
                continue
            # 2.2 获取tspider节点并判定需要删除的中间节点
            tspider_nodes = [node for node in nodes if node["node_type"] == TSpiderStorageNode.NODE_TYPE]
            for tn in tspider_nodes:
                print(f"flow({flow_id}): get tspider flow node: {tn['node_name']}({tn['node_id']})")
                # 找到中间存储节点并删除
                if tn["node_name"].endswith("_full)"):
                    print(f"flow({flow_id}): will clean tspider flow node: {tn['node_name']}({tn['node_id']})")
                    node_id = tn["node_id"]
                    ret = api.bkdata.delete_data_flow_node(flow_id=flow_id, node_id=node_id)
                    print(f"flow({flow_id}): deleted tspider flow node({tn['node_id']}): {ret}")
                    break
            else:
                # 2.3 没有需要删除的节点，则跳过重启
                continue
            if flow["status"] == "running":
                # 3. flow状态为 running的, 重启
                print(f"flow({flow_id}): restart flow")
                try:
                    # 3.1 重启，从上次停止位置开始处理
                    result = api.bkdata.restart_data_flow(
                        flow_id=flow_id,
                        consuming_mode=ConsumingMode.Current,
                        cluster_group=settings.BK_DATA_FLOW_CLUSTER_GROUP,
                    )
                    print(f"flow({flow_id}): start/restart success, result:({result})")
                except Exception as e:  # noqa
                    print(f"flow({flow_id}): start/restart failed: {e}")
                time.sleep(300)
