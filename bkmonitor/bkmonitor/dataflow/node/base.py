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


import abc
import logging
import time

import six

from core.drf_resource import api
from core.errors.bkmonitor.dataflow import (
    DataFlowNodeCreateFailed,
    DataFlowNodeUpdateFailed,
)

logger = logging.getLogger("bkmonitor.dataflow")


class Node(six.with_metaclass(abc.ABCMeta, object)):
    """
    Node
    """

    NODE_TYPE = None

    DEFAULT_FRONTEND_INFO = (100, 100)  # 画布里的默认位置信息
    DEFAULT_FRONTEND_OFFSET = 100  # 下一个节点和上一个节点之间的x/y两个方向上的偏移

    def __init__(self, parent=None, *args, **kwargs):
        if isinstance(parent, (list, tuple)):
            self.parent_list = parent
        else:
            self.parent_list = [parent] if parent else []

        self.node_id = None  # node_id, 初始化为None，在创建后才会存在

    def __eq__(self, other):
        if isinstance(other, dict):
            for k, v in self.config.items():
                if v != other.get(k):
                    return False
            return True
        elif isinstance(other, self.__class__):
            return self == other.config
        return False

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def frontend_info(self):
        if self.parent_list:
            first_parent = self.parent_list[0]
            return {
                "x": first_parent.frontend_info["x"] + self.DEFAULT_FRONTEND_OFFSET,
                "y": first_parent.frontend_info["y"] + self.DEFAULT_FRONTEND_OFFSET,
            }
        return {"x": self.DEFAULT_FRONTEND_INFO[0], "y": self.DEFAULT_FRONTEND_INFO[1]}

    @property
    @abc.abstractmethod
    def config(self):
        return {}

    def need_update(self, other_config):
        for k, v in self.config.items():
            if v != other_config.get(k):
                return True
        return False

    def need_restart_from_tail(self, other_config=None):
        # other_config: 存量节点配置
        # 判定flow 重启，是否需要从尾部直接开始
        # 表结构变更后，历史数据里没有这个字段，会导致任务执行异常。上游新增字段后，如果下游任务使用到这个字段，最好重启任务时选择从尾部处理
        if "sql" in self.config:
            if not other_config:
                # 无 other_config表示新增节点
                return True
            return self.config["sql"] != other_config.get("sql")
        return False

    def get_node_type(self):
        return self.NODE_TYPE

    def get_api_params(self, flow_id):
        from_links = []
        if self.parent_list:
            for p in self.parent_list:
                from_links.append(
                    {
                        "source": {"node_id": p.node_id, "id": "ch_{}".format(p.node_id), "arrow": "Right"},
                        "target": {"id": "bk_node_{}".format(int(time.time() * 1000)), "arrow": "Left"},
                    }
                )
        return {
            "flow_id": flow_id,
            "from_links": from_links,
            "node_type": self.get_node_type(),
            "config": self.config,
            "frontend_info": self.frontend_info,
        }

    def update(self, flow_id, node_id):
        params = self.get_api_params(flow_id)
        params["node_id"] = node_id
        try:
            result = api.bkdata.update_data_flow_node(**params)
            self.node_id = node_id
        except Exception as e:  # noqa
            logger.exception("update node({}) to flow({}) failed".format(self.name, flow_id))
            raise DataFlowNodeUpdateFailed(node_name=self.name, err=e)
        logger.info("update node({}) to flow({}) success, result:({})".format(self.name, flow_id, result))

    def create(self, flow_id):
        params = self.get_api_params(flow_id=flow_id)
        try:
            result = api.bkdata.add_data_flow_node(**params)
            self.node_id = result["node_id"]
        except Exception as e:  # noqa
            logger.exception("add node({}) to flow({}) failed".format(self.name, flow_id))
            raise DataFlowNodeCreateFailed(node_name=self.name, err=e)
        logger.info("add node({}) to flow({}) success, result:({})".format(self.name, flow_id, result))
