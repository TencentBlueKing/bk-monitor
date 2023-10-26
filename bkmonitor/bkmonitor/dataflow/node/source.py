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


from abc import ABC

from bkmonitor.dataflow.node.base import Node


class SourceNode(Node, ABC):
    pass


class StreamSourceNode(SourceNode):
    """
    数据源节点
    """

    NODE_TYPE = "stream_source"

    def __init__(self, source_rt_id):
        self.source_rt_id = source_rt_id
        super(StreamSourceNode, self).__init__()

    def __eq__(self, other):
        if isinstance(other, dict):
            config = self.config
            if config.get("from_result_table_ids") == other.get("from_result_table_ids") and config.get(
                "table_name"
            ) == other.get("table_name"):
                return True
        elif isinstance(other, self.__class__):
            return self == other.config
        return False

    @property
    def name(self):
        return "{}({})".format(self.get_node_type(), self.source_rt_id)

    @property
    def output_table_name(self):
        return self.source_rt_id

    @property
    def config(self):
        return {"from_result_table_ids": [self.source_rt_id], "result_table_id": self.source_rt_id, "name": self.name}


class RelationSourceNode(StreamSourceNode):
    """
    关联数据源
    """

    NODE_TYPE = "redis_kv_source"


class OffLineStreamSourceNode(StreamSourceNode):
    """
    离线流水表
    """

    NODE_TYPE = "batch_source"
