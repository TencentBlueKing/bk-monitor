# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import os
from typing import Any, Dict, List, Optional

from django.utils.translation import gettext as _

from apps.log_commons.job import JobHelper
from apps.log_databus.constants import (
    GSE_PATH,
    IPC_PATH,
    CheckStatusEnum,
    TargetNodeTypeEnum,
)
from apps.log_databus.handlers.check_collector.base import CheckCollectorRecord
from apps.log_databus.handlers.check_collector.checker.agent_checker import AgentChecker
from apps.log_databus.handlers.check_collector.checker.bkunifylogbeat_checker import (
    BkunifylogbeatChecker,
)
from apps.log_databus.handlers.check_collector.checker.es_checker import EsChecker
from apps.log_databus.handlers.check_collector.checker.kafka_checker import KafkaChecker
from apps.log_databus.handlers.check_collector.checker.metadata_checker import (
    MetaDataChecker,
)
from apps.log_databus.handlers.check_collector.checker.route_checker import RouteChecker
from apps.log_databus.handlers.check_collector.checker.transfer_checker import (
    TransferChecker,
)
from apps.log_databus.models import CollectorConfig
from apps.utils.task import high_priority_task


class CheckCollectorHandler:
    HANDLER_NAME = _("启动入口")

    def __init__(
        self, collector_config_id: int, hosts: List[Dict[str, Any]] = None, gse_path: str = None, ipc_path: str = None
    ):
        self.collector_config_id = collector_config_id
        self.hosts = hosts

        # 先定义字段
        self.subscription_id = None
        self.table_id = None
        self.bk_data_name = None
        self.bk_data_id = None
        self.bk_biz_id = None
        self.target_server: Dict[str, Any] = {}
        self.collector_config: Optional[CollectorConfig]
        self.gse_path = gse_path or os.environ.get("GSE_ROOT_PATH", GSE_PATH)
        self.ipc_path = ipc_path or os.environ.get("GSE_IPC_PATH", IPC_PATH)

        self.story_report = []
        self.kafka = []
        self.latest_log = []
        cache_key = CheckCollectorRecord.generate_check_record_id(collector_config_id, hosts)

        self.record = CheckCollectorRecord(cache_key)

        if not self.record.is_exist() or self.record.get_check_status() == CheckStatusEnum.FINISH.value:
            self.record.new_record()

    def pre_run(self):
        try:
            self.collector_config = CollectorConfig.objects.get(collector_config_id=self.collector_config_id)
        except CollectorConfig.DoesNotExist:
            self.record.append_error_info(_("采集项ID查找失败"), "pre-run")
            return

        # 快速脚本执行的参数target_server
        self.target_server = {}
        self.bk_biz_id = self.collector_config.bk_biz_id
        self.bk_data_id = self.collector_config.bk_data_id
        self.bk_data_name = self.collector_config.bk_data_name
        self.table_id = self.collector_config.table_id
        self.subscription_id = self.collector_config.subscription_id or 0

        # 如果有输入host, 则覆盖, 否则使用collector_config.target_nodes
        if self.hosts:
            try:
                self.target_server = JobHelper.adapt_hosts_target_server(bk_biz_id=self.bk_biz_id, hosts=self.hosts)
            except Exception as e:  # pylint: disable=broad-except
                self.record.append_error_info(
                    _("输入合法的hosts, err: {e}, 参考: [{'bk_host_id': 0, 'ip': 'ip', 'bk_cloud_id': 0}]").format(e=e),
                    self.HANDLER_NAME,
                )
                return
        else:
            # 不同的target_node_type
            target_node_type = self.collector_config.target_node_type
            if target_node_type == TargetNodeTypeEnum.TOPO.value:
                self.target_server = {
                    "topo_node_list": [
                        {"id": i["bk_inst_id"], "node_type": i["bk_obj_id"]} for i in self.collector_config.target_nodes
                    ]
                }
            elif target_node_type == TargetNodeTypeEnum.INSTANCE.value:
                self.target_server = JobHelper.adapt_hosts_target_server(
                    bk_biz_id=self.bk_biz_id, hosts=self.collector_config.target_nodes
                )
            elif target_node_type == TargetNodeTypeEnum.DYNAMIC_GROUP.value:
                self.target_server = {"dynamic_group_list": self.collector_config.target_nodes}
            else:
                # 不支持集群模板和服务模板, 因为转换成主机可能会碰到巨大数量的主机, 所以暂不支持
                self.record.append_error_info(
                    _("暂不支持该target_node_type: {target_node_type}").format(target_node_type=target_node_type),
                    self.HANDLER_NAME,
                )
        if not self.story_report:
            self.record.append_normal_info(_("初始化检查成功"), self.HANDLER_NAME)

    def run(self):
        self.pre_run()
        if not self.record.have_error:
            self.execute_check()

    def execute_check(self):
        # 只有通过容器下发的采集项才会检查
        if self.collector_config.is_container_environment:
            bkunifylogbeat_checker = BkunifylogbeatChecker(
                collector_config=self.collector_config, check_collector_record=self.record
            )
            bkunifylogbeat_checker.run()
            # 采集下发的容器日志的target_server为Node的节点
            self.target_server = bkunifylogbeat_checker.target_server

        # 容器自定义采集项不检查agent, target_server为空时也跳过检查
        if not self.collector_config.is_custom_container or not self.target_server:
            agent_checker = AgentChecker(
                bk_biz_id=self.bk_biz_id,
                target_server=self.target_server,
                subscription_id=self.subscription_id,
                gse_path=self.gse_path,
                ipc_path=self.ipc_path,
                check_collector_record=self.record,
            )
            agent_checker.run()

        router_checker = RouteChecker(self.bk_data_id, check_collector_record=self.record)
        router_checker.run()
        self.kafka = router_checker.kafka

        kafka_checker = KafkaChecker(self.kafka, check_collector_record=self.record)
        kafka_checker.run()
        self.latest_log = kafka_checker.latest_log

        transfer_checker = TransferChecker(
            collector_config=self.collector_config, latest_log=self.latest_log, check_collector_record=self.record
        )
        transfer_checker.run()

        es_checker = EsChecker(
            table_id=self.table_id, bk_data_name=self.bk_data_name, check_collector_record=self.record
        )
        es_checker.run()

        meta_data_checker = MetaDataChecker(check_collector_record=self.record)
        meta_data_checker.run()

    def get_record_infos(self) -> str:
        return self.record.get_infos()


@high_priority_task(ignore_result=True)
def async_run_check(collector_config_id: int, hosts: List[Dict[str, Any]] = None):
    handler = CheckCollectorHandler(collector_config_id=collector_config_id, hosts=hosts)
    handler.record.append_normal_info("check start", handler.HANDLER_NAME)
    handler.record.change_status(CheckStatusEnum.STARTED.value)
    handler.run()
    handler.record.append_normal_info("check finish", handler.HANDLER_NAME)
    handler.record.change_status(CheckStatusEnum.FINISH.value)
