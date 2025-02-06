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
from typing import Dict, List, Optional

from django.db.transaction import atomic

from constants.dataflow import ConsumingMode
from metadata import config, models
from metadata.models.constants import BULK_CREATE_BATCH_SIZE
from metadata.models.record_rule.constants import DEFAULT_RULE_TYPE, RecordRuleStatus
from metadata.models.record_rule.rules import RecordRule, ResultTableFlow
from metadata.models.record_rule.utils import generate_pre_cal_table_id
from metadata.models.vm import utils as vm_utils

logger = logging.getLogger("metadata")


class RecordRuleService:
    """预计算处理"""

    def __init__(
        self,
        space_type: str,
        space_id: str,
        record_name: str,
        rule_type: Optional[str] = DEFAULT_RULE_TYPE,
        rule_config: Optional[dict] = "",
        count_freq: Optional[int] = 60,
    ) -> None:
        self.space_type = space_type
        self.space_id = space_id
        self.record_name = record_name
        self.rule_type = rule_type
        self.rule_config = rule_config
        self.count_freq = count_freq

    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_record_rule(self):
        """创建预计算规则"""
        bksql_metrics = RecordRule.transform_bk_sql_and_metrics(self.rule_config)
        src_rts = RecordRule.get_src_table_ids(self.space_type, self.space_id, bksql_metrics["metrics"])
        if not src_rts:
            logger.error("no valid table id found for record_name: %s", self.record_name)
            return
        # 转换到监控结果表
        table_id = generate_pre_cal_table_id(self.space_type, self.space_id, self.record_name)
        dst_rt = RecordRule.get_dst_table_id(table_id)
        # 创建预计算配置
        self._create_result_table(space_type=self.space_type, space_id=self.space_id, table_id=table_id)
        self._create_record_rule_record(
            table_id, bksql_metrics["bksql"], bksql_metrics["rule_metrics"], src_rts, dst_rt, count_freq=self.count_freq
        )
        # 创建结果表对应的指标
        self._create_table_id_fields(table_id, list(bksql_metrics["rule_metrics"].values()))
        self._create_vm_storage(table_id, dst_rt)

    def _create_record_rule_record(
        self, table_id: str, bksql: List, rule_metrics: Dict, src_table_ids: List, dst_rt: str, count_freq: int
    ):
        """创建预计算记录"""
        vm_info = vm_utils.get_vm_cluster_id_name(space_type=self.space_type, space_id=self.space_id)
        record = {
            "space_type": self.space_type,
            "space_id": self.space_id,
            "table_id": table_id,
            "record_name": self.record_name,
            "rule_type": self.rule_type,
            "rule_config": self.rule_config,
            "bk_sql_config": bksql,
            "rule_metrics": rule_metrics,
            "src_vm_table_ids": src_table_ids,
            "vm_cluster_id": vm_info["cluster_id"],
            "dst_vm_table_id": dst_rt,
            "status": RecordRuleStatus.CREATED.value,
            "count_freq": count_freq,
        }
        # 创建记录
        try:
            RecordRule.objects.create(**record)
        except Exception as e:
            logger.error("create record rule error: %s", e)
            raise

    def _create_result_table(self, space_type: str, space_id: str, table_id: str):
        """创建结果表"""
        biz_id = models.Space.objects.get_biz_id_by_space(space_type, space_id)
        models.ResultTable.objects.create(
            table_id=table_id,
            table_name_zh=table_id,
            is_custom_table=True,
            default_storage=models.ClusterInfo.TYPE_VM,
            creator="system",
            bk_biz_id=biz_id,
        )

    def _create_table_id_fields(self, table_id: str, metrics: List):
        """创建rt的字段"""
        objs = []
        for metric in metrics:
            objs.append(
                models.ResultTableField(
                    **{
                        "table_id": table_id,
                        "field_name": metric,
                        "field_type": models.ResultTableField.FIELD_TYPE_STRING,
                        "description": metric,
                        "tag": models.ResultTableField.FIELD_TAG_METRIC,
                        "is_config_by_user": True,
                    }
                )
            )
        models.ResultTableField.objects.bulk_create(objs, batch_size=BULK_CREATE_BATCH_SIZE)

    def _create_vm_storage(self, table_id: str, vm_table_id: str):
        """创建 vm 存储"""
        models.AccessVMRecord.objects.create(
            result_table_id=table_id,
            bk_base_data_id=0,  # 没有具体的计算平台ID，设置为 0
            vm_result_table_id=vm_table_id,
        )


class BkDataFlow:
    def __init__(self, space_type: str, space_id: str, table_id: str) -> None:
        self.space_type = space_type
        self.space_id = space_id
        self.table_id = table_id

    def start_flow(self, check_status: bool = True, consuming_mode: Optional[str] = ConsumingMode.Tail) -> bool:
        """启动数据流"""
        # 如果flow已经启动，则不需要再次启动
        if (
            RecordRule.objects.filter(
                space_type=self.space_type,
                space_id=self.space_id,
                table_id=self.table_id,
                status=RecordRuleStatus.RUNNING.value,
            ).exists()
            and check_status
        ):
            logger.error("table_id: %s flow already started", self.table_id)
            return False
        # 创建 flow
        if not ResultTableFlow.create_flow(self.table_id):
            return False
        logger.info("create flow success: %s", self.table_id)

        try:
            obj = ResultTableFlow.objects.get(table_id=self.table_id)
        except ResultTableFlow.DoesNotExist:
            logger.error("ResultTableFlow does not exist: %s", self.table_id)
            return False

        # 启动 flow
        flow_id = obj.flow_id
        # 初次启动，设置数据处理模式为尾部处理
        if not ResultTableFlow.start_flow(flow_id, consuming_mode):
            return False
        # 设置预计算状态为running
        RecordRule.objects.filter(space_type=self.space_type, space_id=self.space_id, table_id=self.table_id).update(
            status=RecordRuleStatus.RUNNING.value
        )

        logger.info("create start flow task success, table_id: %s, flow_id: %s", self.table_id, flow_id)
        return True

    def update_flow(self) -> bool:
        """更新flow
        NOTE: 针对预计算场景，当变动节点时，除了最后的存储节点外，其它节点都需要更新，因此，采用删除flow，重新创建flow的方式处理
        """
        try:
            obj = ResultTableFlow.objects.get(table_id=self.table_id)
        except ResultTableFlow.DoesNotExist:
            logger.error("ResultTableFlow does not exist: %s", self.table_id)
            return False
        flow_id = obj.flow_id
        # 停止flow
        if not ResultTableFlow.stop_flow(flow_id):
            return False
        # NOTE: 等待20s, 待 flow 结束，删除 flow
        # 删除flow
        if not ResultTableFlow.delete_flow(flow_id):
            return False
        # 重新创建flow
        self.start_flow(check_status=False, consuming_mode=ConsumingMode.Current)
        return True
