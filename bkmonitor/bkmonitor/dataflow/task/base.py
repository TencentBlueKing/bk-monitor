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
import logging

from bkmonitor.dataflow.flow import DataFlow
from bkmonitor.dataflow.node.base import Node
from constants.dataflow import ConsumingMode
from core.errors.bkmonitor.dataflow import DataFlowCreateFailed, DataFlowNotExists

logger = logging.getLogger("bkmonitor.dataflow")


class BaseTask(abc.ABC):
    def __init__(self):
        self.data_flow = None
        self.node_list = []
        self.flow_status = None

        self.rt_id = None  # 输入数据源

    @property
    @abc.abstractmethod
    def flow_name(self):
        return ""

    def create_flow(self, rebuild=False, project_id=None):
        """
        尝试创建flow
            如果已经存在，则获取到整个flow的相关信息，包括node的信息
                一个个比对，如果有差异，则进行更新动作
            如果不存在，则直接创建
                对于节点的创建也是同样的逻辑，先看是否存在，存在则更新，不存在则创建之
        :return:
        """
        # 2. 创建任务(data flow)
        self.data_flow = DataFlow.ensure_data_flow_exists(
            flow_name=self.flow_name, rebuild=rebuild, project_id=project_id
        )
        if not self.data_flow:
            raise DataFlowCreateFailed(flow_name=self.flow_name)

        # 3. 创建任务下的节点(node)
        # 需按node_list的顺序来创建
        for node in self.node_list:
            self.data_flow.add_node(node)

    def start_flow(self, consuming_mode=None):
        if self.data_flow:
            if consuming_mode is None and self.data_flow.sql_changed:
                consuming_mode = ConsumingMode.Tail
            self.data_flow.start(consuming_mode)
            self.flow_status = self.data_flow.flow_status

    def check_flow_changed(self):
        """
        检查flow是否被修改
        """
        try:
            data_flow = DataFlow.from_bkdata_by_flow_name(self.flow_name)
        except DataFlowNotExists:
            return True

        for node in self.node_list:
            node_key = Node.build_node_unique_key(node)
            if data_flow.flow_graph_info.get(node_key):
                match_node = data_flow.flow_graph_info.get(node_key)
                node_config = match_node.get("node_config", {})
                if node.need_update(node_config):
                    print(node.config, node_config)
                    return True

            for graph_node in data_flow.flow_graph_info:
                node_config = graph_node.get("node_config", {})
                # 判断是否为同样的节点(只判断关键信息，比如输入和输出表ID等信息)
                if node.get_node_type() == graph_node["node_type"] and node == node_config:
                    # 如果部分信息不一样，则做一遍更新
                    if node.need_update(node_config):
                        print(node.config, node_config)
                        return True
        return False
