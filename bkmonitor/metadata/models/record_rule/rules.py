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
import re
from typing import Dict, List, Optional, Set

import yaml
from django.conf import settings
from django.db import models

from bkmonitor.utils.db import JsonField
from bkmonitor.utils.time_format import parse_duration
from metadata.models.common import BaseModelWithTime
from metadata.models.record_rule import utils
from metadata.models.record_rule.constants import (
    DEFAULT_EVALUATION_INTERVAL,
    BkDataFlowStatus,
)

logger = logging.getLogger("metadata")


class RecordRule(BaseModelWithTime):
    table_id = models.CharField("结果表名", max_length=128)
    record_name = models.CharField("预计算名称", max_length=128)
    rule_type = models.CharField("规则类型", max_length=32, default="prometheus")
    rule_config = JsonField("原始规则配置", null=True, blank=True)
    bk_sql_config = JsonField("转换后的SQL配置", null=True, blank=True)

    class Meta:
        verbose_name = "预计算规则"
        verbose_name_plural = "预计算规则"

    @classmethod
    def transform_bk_sql_and_metrics(cls, rule_config: str) -> Dict:
        """转换原始规则配置到计算平台语句"""
        rule_dict = yaml.safe_load(rule_config)
        rules = rule_dict.get("rules", [])
        # 如果规则为空，则直接返回
        if not rules:
            return {}
        # 获取所有的record
        all_rule_record = [rule["record"] for rule in rules]
        # 如果没有设置interval，则使用默认值
        interval = rules.get("interval") or DEFAULT_EVALUATION_INTERVAL
        bksql_list, metrics = [], set()
        for rule in rules:
            expr = rule.get("expr")
            if not expr:
                continue

            _expr = re.sub(r"#.*", "", expr)
            sql_and_metrics = utils.refine_bk_sql_and_metrics(_expr, all_rule_record)
            bksql_list.append(
                {
                    "count_freq": parse_duration(interval),
                    "sql": sql_and_metrics["bksql"],
                    "metric_name": utils.transform_record_to_metric_name(rule["record"]),
                }
            )
            metrics.update(sql_and_metrics["metrics"])
        return {"bksql": bksql_list, "metrics": metrics}

    @classmethod
    def get_src_table_ids(cls, space_type: str, space_id: str, metrics: Optional[List, Set]) -> List:
        """获取源结果表列表"""
        # 通过指标和所属空间，查询需要预计算的结果表
        # 获取空间所在记录的ID
        from metadata.models import AccessVMRecord, ResultTable, ResultTableField, Space

        id = Space.objects.get_biz_id_by_space(space_type, space_id)
        # 获取空间下的结果表列表
        table_ids = list(
            ResultTable.objects.filter(
                bk_biz_id=id, default_storage_type="influxdb", is_enable=True, is_deleted=False
            ).values_list("table_id", flat=True)
        )
        # 过滤指标
        # 项目下可用结果表不会太多
        table_ids = list(
            ResultTableField.objects.filter(table_id__in=table_ids, field_name__in=metrics).values_list(
                "table_id", flat=True
            )
        )
        # 过滤到对应的 vm 结构表
        return list(
            AccessVMRecord.objects.filter(result_table_id__in=table_ids).values_list("vm_result_table_id", flat=True)
        )

    @classmethod
    def get_dst_table_id(cls) -> str:
        """获取要写入的结果表"""
        pass


class ResultTableFlow(BaseModelWithTime):
    """结果表计算流程记录"""

    table_id = models.CharField("结果表名", max_length=128)
    flow_id = models.IntegerField("计算流程ID", default=-1)
    config = JsonField("计算配置", null=True, blank=True)
    status = models.CharField("计算状态", max_length=32, default=BkDataFlowStatus.NO_START.value)

    class Meta:
        verbose_name = "结果表计算流程记录"
        verbose_name_plural = "结果表计算流程记录"

    @classmethod
    def compose_config(cls, table_id: str, vm_table_ids: List) -> Dict:
        """组装计算配置"""
        nodes = []
        # 组装源节点
        for index, tid in enumerate(vm_table_ids):
            nodes.append(
                {
                    "id": index + 1,
                    "node_type": "stream_source",
                    "bk_biz_name": "2005000727",
                    "bk_biz_id": settings.BK_DATA_BK_BIZ_ID,
                    "result_table_id": tid,
                    "name": tid,
                    "from_result_table_ids": ["2005000727_bkbase_trace1110"],
                }
            )
