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


import logging
import time

from django.conf import settings

from constants.dataflow import ConsumingMode
from core.drf_resource import api
from core.errors.bkmonitor.dataflow import DataFlowNotExists, DataFlowStartFailed

logger = logging.getLogger("bkmonitor.dataflow")


class DataFlow(object):
    """
    对应计算平台的dataflow
    """

    class Status(object):
        NoStart = "no-start"
        Running = "running"
        Starting = "starting"
        Failure = "failure"
        Stopping = "stopping"
        Warning = "warning"

    def __init__(self, flow_id, project_id=None, flow_name=None):
        """
        根据flow_id，从计算平台请求flow中的节点信息，并初始化自身(懒加载模式)
        :param flow_id:
        """
        self.flow_id = flow_id

        self.flow_name = flow_name
        self.project_id = project_id or settings.BK_DATA_PROJECT_ID

        self._flow_info = None
        self._flow_graph_info = None

        self.is_modified = False
        self.sql_changed = False

    @property
    def flow_info(self):
        """
        获取dataflow的状态信息
        """
        self._flow_info = api.bkdata.get_data_flow(flow_id=self.flow_id)
        return self._flow_info

    @property
    def flow_deploy_info(self):
        """
        获取dataflow的最近一次部署信息
        1. 如果self.flow_deploy_info为空，说明是no-start状态，需要start
        2. 如果self.flow_deploy_inf["status"]为scuccess则该flow运行正常
        3. 如果self.flow_deploy_inf["status"]为failure则该flow运行异常
        """
        return api.bkdata.get_latest_deploy_data_flow(flow_id=self.flow_id)

    @property
    def flow_graph_info(self):
        if self._flow_graph_info is None:
            result = api.bkdata.get_data_flow_graph(flow_id=self.flow_id)
            self._flow_graph_info = result.get("nodes", [])
        return self._flow_graph_info

    @property
    def flow_status(self):
        return self.flow_info.get("status")

    @classmethod
    def from_bkdata_by_flow_id(cls, flow_id):
        """
        从bkdata接口查询到flow相关信息，然后初始化一个DataFlow对象返回
        :param flow_id:
        """
        result = api.bkdata.get_data_flow(flow_id=flow_id)
        if result:
            return cls(flow_id, project_id=result["project_id"], flow_name=result["flow_name"])
        raise DataFlowNotExists(flow_id=flow_id)

    @classmethod
    def from_bkdata_by_flow_name(cls, flow_name, project_id=None):
        """
        从bkdata接口查询到flow相关信息，根据flow_name，然后初始化一个DataFlow对象返回
        :param flow_name:
        :param project_id dataflow 项目id
        """
        params = {}
        if project_id:
            params["project_id"] = project_id
        else:
            params["project_id"] = settings.BK_DATA_PROJECT_ID

        result = api.bkdata.get_data_flow_list(**params)
        if not result:
            raise DataFlowNotExists()

        for flow in result:
            name = flow.get("flow_name", "")
            if flow_name == name:
                return cls(flow["flow_id"], project_id=flow["project_id"], flow_name=flow_name)

        raise DataFlowNotExists()

    @classmethod
    def create_flow(cls, flow_name, project_id=None):
        params = {"flow_name": flow_name}
        if project_id:
            params["project_id"] = project_id
        else:
            params["project_id"] = settings.BK_DATA_PROJECT_ID

        result = api.bkdata.create_data_flow(**params)
        return cls(flow_id=result["flow_id"], project_id=result["project_id"], flow_name=result["flow_name"])

    @classmethod
    def ensure_data_flow_exists(cls, flow_name, rebuild=False, project_id=None):
        try:
            flow = DataFlow.from_bkdata_by_flow_name(flow_name, project_id)
            if rebuild:
                return flow.rebuild()
            return flow
        except DataFlowNotExists:
            return DataFlow.create_flow(flow_name, project_id)

    def start_or_restart_flow(self, is_start=True, consuming_mode=None):
        try:
            if is_start:
                # 新启动，从尾部开始处理
                consuming_mode = consuming_mode or ConsumingMode.Tail
                result = api.bkdata.start_data_flow(
                    flow_id=self.flow_id,
                    consuming_mode=consuming_mode,
                    cluster_group=settings.BK_DATA_FLOW_CLUSTER_GROUP,
                )
            else:
                # 重启，从上次停止位置开始处理
                consuming_mode = consuming_mode or ConsumingMode.Current
                result = api.bkdata.restart_data_flow(
                    flow_id=self.flow_id,
                    consuming_mode=consuming_mode,
                    cluster_group=settings.BK_DATA_FLOW_CLUSTER_GROUP,
                )
            logger.info(
                "start/restart dataflow({}({})) success, result:({})".format(self.flow_name, self.flow_id, result)
            )
            return result
        except Exception as e:  # noqa
            logger.exception("start/restart dataflow({}({})) failed".format(self.flow_name, self.flow_id))
            raise DataFlowStartFailed(flow_id=self.flow_id, flow_name=self.flow_name, err=e)

    def start(self, consuming_mode=None):
        flow_status = self.flow_status
        flow_deploy_info = self.flow_deploy_info
        if flow_status == self.Status.NoStart:
            # 该flow的状态为no-start，需要start这个flow
            # 如果是之前没有部署过的则需要传入从头启动消费模式，如果已有部署信息，则传入参数消费模式
            return self.start_or_restart_flow(consuming_mode=consuming_mode if flow_deploy_info else ConsumingMode.Tail)
        elif flow_status == self.Status.Running:
            # 该flow的状态正常启动，需要去判断是否更新如果节点有更新则重启
            if not self.is_modified:
                logger.info("dataflow({}({})) has not changed.".format(self.flow_name, self.flow_id))
                return {}
            return self.start_or_restart_flow(False, consuming_mode)
        else:
            # 其余状态则全部重启
            return self.start_or_restart_flow(False, consuming_mode)

    def stop(self):
        api.bkdata.stop_data_flow(flow_id=self.flow_id)

    def add_node(self, node):
        for graph_node in self.flow_graph_info:
            node_config = graph_node.get("node_config", {})
            # 判断是否为同样的节点(只判断关键信息，比如输入和输出表ID等信息)
            if node.get_node_type() == graph_node["node_type"] and node == node_config:
                node_id = graph_node.get("node_id")
                # 如果部分信息不一样，则做一遍更新
                if node.need_update(node_config):
                    node.update(self.flow_id, node_id)
                    self.is_modified = True
                    self.sql_changed = self.sql_changed or node.need_restart_from_tail(node_config)
                node.node_id = node_id
                return

        node.create(self.flow_id)
        self.is_modified = True
        self.sql_changed = node.need_restart_from_tail()

    def delete(self):
        logger.info("delete dataflow({}({})) start".format(self.flow_name, self.flow_id))

        flow_info = api.bkdata.get_data_flow(flow_id=self.flow_id)

        if flow_info["status"] != self.Status.NoStart:
            # 停用flow
            logger.info(
                "dataflow({}({})) in status({}), stop first".format(self.flow_name, self.flow_id, flow_info["status"])
            )

            self.stop()

        # 轮询flow状态，直到 flow 为"no-start" 状态
        max_retries = 300
        while max_retries > 0:
            if flow_info["status"] == self.Status.NoStart:
                break
            time.sleep(1)
            flow_info = api.bkdata.get_data_flow(flow_id=self.flow_id)
            max_retries -= 1

        logger.info("dataflow({}({})) stop success, begin to delete".format(self.flow_name, self.flow_id))

        api.bkdata.delete_data_flow(flow_id=self.flow_id)

    def rebuild(self):
        """
        重建flow
        """
        logger.info("rebuild dataflow({}({}))".format(self.flow_name, self.flow_id))

        # 删除flow
        self.delete()
        logger.info("delete old dataflow({}({})) success".format(self.flow_name, self.flow_id))

        flow = self.create_flow(flow_name=self.flow_name)
        logger.info(
            "rebuild dataflow({}({})) success, new dataflow({}({}))".format(
                self.flow_name, self.flow_id, flow.flow_name, flow.flow_id
            )
        )
        return flow
