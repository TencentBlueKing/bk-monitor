"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import datetime
import json
import logging
from typing import Any

import yaml
from django.conf import settings
from django.db import models
from django.utils.timezone import now as tz_now

from bkmonitor.dataflow.auth import batch_add_permission
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.time_format import parse_duration
from constants.dataflow import ConsumingMode
from core.drf_resource import api
from core.errors.api import BKAPIError
from metadata.models.common import BaseModelWithTime
from metadata.models.record_rule import utils
from metadata.models.record_rule.constants import (
    DEFAULT_EVALUATION_INTERVAL,
    DEFAULT_RULE_TYPE,
    BkDataFlowStatus,
)
from metadata.models.space.ds_rt import get_space_table_id_data_id

logger = logging.getLogger("metadata")


class RecordRule(BaseModelWithTime):
    space_type = models.CharField("空间类型", max_length=64)
    space_id = models.CharField("空间ID", max_length=128)
    table_id = models.CharField("结果表名", max_length=128)
    record_name = models.CharField("预计算名称", max_length=128)
    rule_type = models.CharField("规则类型", max_length=32, default=DEFAULT_RULE_TYPE)
    rule_config = JsonField("原始规则配置", null=True, blank=True)
    bk_sql_config = JsonField("转换后的SQL配置", null=True, blank=True)
    rule_metrics = JsonField("指标转换信息", default={})
    src_vm_table_ids = JsonField("源数据VM结果表列表", default=[])
    vm_cluster_id = models.IntegerField("集群ID", null=True, blank=True)
    dst_vm_table_id = models.CharField("VM 结果表rt", max_length=64, help_text="VM 结果表rt")
    status = models.CharField("状态", max_length=32, default="created")
    count_freq = models.IntegerField("计算频率(秒)", default=60)

    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system")

    class Meta:
        verbose_name = "预计算规则"
        verbose_name_plural = "预计算规则"

    @classmethod
    def transform_bk_sql_and_metrics(cls, rule_config: str) -> dict[str, Any]:
        """转换原始规则配置到计算平台语句"""
        rule_dict = yaml.safe_load(rule_config)
        rules = rule_dict.get("rules", [])
        # 如果规则为空，则直接返回
        if not rules:
            return {}
        # 获取所有的record
        all_rule_record = [rule["record"] for rule in rules]
        # 如果没有设置interval，则使用默认值
        interval = rule_dict.get("interval") or DEFAULT_EVALUATION_INTERVAL
        bksql_list, metrics, rule_metrics = [], set(), {}
        for rule in rules:
            expr = rule.get("expr")
            if not expr:
                continue

            sql_and_metrics = utils.refine_bk_sql_and_metrics(expr, all_rule_record)
            rule_metric = utils.transform_record_to_metric_name(rule["record"])
            rule_metrics.update({rule["record"]: rule_metric})

            sql = {
                "name": rule_metric,
                "count_freq": parse_duration(interval),
                "sql": sql_and_metrics["promql"],
                "metric_name": rule_metric,
            }
            # 如果label存在追加label信息
            if rule.get("labels"):
                label = rule["labels"]
                # 如果label是字典，则转换为列表
                if isinstance(label, dict):
                    label = [{"label_name": k, "label_value": v} for k, v in rule["labels"].items()]
                sql["label"] = label
            bksql_list.append(sql)
            metrics.update(sql_and_metrics["metrics"])
        return {"bksql": bksql_list, "metrics": metrics, "rule_metrics": rule_metrics}

    @classmethod
    def get_src_table_ids(cls, space_type: str, space_id: str, metrics: list | set) -> list:
        """获取源结果表列表"""
        # 通过指标和所属空间，查询需要预计算的结果表
        # 获取空间所在记录的ID
        from metadata.models import (
            AccessVMRecord,
            ResultTableField,
            TimeSeriesGroup,
            TimeSeriesMetric,
        )

        tid_data_ids = get_space_table_id_data_id(space_type=space_type, space_id=space_id)
        # 过滤指标
        # 项目下可用结果表不会太多
        table_ids = set(
            ResultTableField.objects.filter(table_id__in=list(tid_data_ids.keys()), field_name__in=metrics).values_list(
                "table_id", flat=True
            )
        )
        # 如果没有对应的结果表，则返回空
        if not table_ids:
            logger.error(
                "table_ids not found, space_type: %s, space_id: %s, metrics: %s", space_type, space_id, metrics
            )
            return []
        # 再过滤一遍数据，减少结果表数量
        tid_group_id = {
            ts["table_id"]: ts["time_series_group_id"]
            for ts in TimeSeriesGroup.objects.filter(table_id__in=table_ids).values("table_id", "time_series_group_id")
        }
        begin_time = tz_now() - datetime.timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
        group_ids = set(
            TimeSeriesMetric.objects.filter(
                last_modify_time__gte=begin_time, group_id__in=tid_group_id.values(), field_name__in=metrics
            ).values_list("group_id", flat=True)
        )
        # 拼装结果表
        tids = []
        for tid in table_ids:
            if tid in tid_group_id:
                if tid_group_id[tid] in group_ids:
                    tids.append(tid)
            else:
                tids.append(tid)

        if not tids:
            logger.error(
                "tids not found or metric expired, space_type: %s, space_id: %s, metrics: %s",
                space_type,
                space_id,
                metrics,
            )
            return []
        # 过滤到对应的 vm 结构表
        return list(
            AccessVMRecord.objects.filter(result_table_id__in=tids).values_list("vm_result_table_id", flat=True)
        )

    @classmethod
    def get_dst_table_id(cls, table_id: str) -> str:
        """获取要写入的结果表"""
        return f"{settings.DEFAULT_BKDATA_BIZ_ID}_{utils.compose_rule_table_id(table_id)}"


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
    def compose_flow_name(cls, table_id: str) -> str:
        """组装计算流程名称"""
        return utils.compose_rule_table_id(table_id)

    @classmethod
    def compose_source_node(cls, vm_table_ids: list) -> list:
        """
        组装计算配置
        :param vm_table_ids: VM 结果表列表
        :return: 源节点配置
        """
        nodes = []
        # 组装源节点
        for index, tid in enumerate(vm_table_ids):
            nodes.append(
                {
                    "id": index + 1,
                    "node_type": "stream_source",
                    "bk_biz_name": f"{settings.DEFAULT_BKDATA_BIZ_ID}",
                    "bk_biz_id": settings.BK_DATA_BK_BIZ_ID,
                    "result_table_id": tid,
                    "name": tid,
                    "from_result_table_ids": [tid],
                    "from_nodes": [],
                }
            )

        return nodes

    @classmethod
    def compose_process_node(cls, bk_tenant_id: str, table_id: str, vm_table_ids: list, waiting_time: int = 30) -> dict:
        """
        组装计算节点配置
        :param table_id: 结果表ID
        :param vm_table_ids: VM 结果表列表
        :param waiting_time: 等待时间(秒)
        :return: 计算节点配置
        """
        from_result_table_ids, from_nodes = [], []
        for index, tid in enumerate(vm_table_ids):
            from_result_table_ids.append(tid)
            from_nodes.append({"id": index + 1, "from_result_table_ids": [tid]})
        # 获取bksql计算配置
        try:
            rule_record = RecordRule.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        except RecordRule.DoesNotExist:
            logger.error("table_id: %s not found record rule", table_id)
            return {}
        dedicated_config = {
            "waiting_time": waiting_time,
            # "count_freq": rule_record.count_freq,
            "sql_list": rule_record.bk_sql_config,
        }
        name = utils.compose_rule_table_id(table_id)
        return {
            "id": len(from_result_table_ids) + 1,
            "name": name,
            "node_type": "promql_v2",
            "outputs": [
                {"bk_biz_id": settings.DEFAULT_BKDATA_BIZ_ID, "fields": [], "output_name": name, "table_name": name}
            ],
            "bk_biz_id": settings.BK_DATA_BK_BIZ_ID,
            "from_result_table_ids": from_result_table_ids,
            "dedicated_config": dedicated_config,
            "from_nodes": from_nodes,
            "serving_mode": "realtime",
        }

    @classmethod
    def compose_vm_storage(
        cls, bk_tenant_id: str, table_id: str, process_id: int, expires: int = 30, schemaless: bool = True
    ) -> dict:
        """
        组装存储配置
        :param table_id: 结果表ID
        :param process_id: 计算节点ID
        :param expires: 过期时间（天）
        :param schemaless: 是否是标准四元祖数据
        :return: 存储配置
        """
        from metadata.models.vm import utils as vm_utils

        rt_name = RecordRule.get_dst_table_id(table_id)
        rt_obj = RecordRule.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        vm_info = vm_utils.get_vm_cluster_id_name(
            bk_tenant_id=bk_tenant_id, space_type=rt_obj.space_type, space_id=rt_obj.space_id
        )
        return {
            "id": process_id + 1,
            "node_type": "vm_storage",
            "result_table_ids": [rt_name],
            "name": "vm",
            "bk_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,
            "cluster": vm_info["cluster_name"],
            "from_result_table_ids": [rt_name],
            "expires": expires,
            "schemaless": schemaless,
            "from_nodes": [{"id": process_id, "from_result_table_ids": [rt_name]}],
        }

    @classmethod
    def create_flow(
        cls, bk_tenant_id: str, table_id: str, waiting_time: int = 30, expires: int = 30, schemaless: bool = True
    ) -> bool:
        """
        创建计算平台flow
        :param table_id: 结果表ID
        :param waiting_time: 等待时间（秒）
        :param expires: 过期时间（天）
        :param schemaless: 是否是标准四元祖数据
        :return: bool 是否接入成功
        """
        # 获取预计算结果表数据
        try:
            rule_obj = RecordRule.objects.get(bk_tenant_id=bk_tenant_id, table_id=table_id)
        except RecordRule.DoesNotExist:
            logger.error("create_flow：table_id->[%s] not found record rule", table_id)
            return False

        # 组装参数
        req_data = {
            "project_id": settings.BK_DATA_RECORD_RULE_PROJECT_ID,
            "flow_name": cls.compose_flow_name(table_id),
        }

        # 检测并授权结果表
        if not batch_add_permission(
            settings.BK_DATA_RECORD_RULE_PROJECT_ID, settings.BK_DATA_BK_BIZ_ID, rule_obj.src_vm_table_ids
        ):
            logger.error("create_flow: batch add permission error, vm_table_id->[%s]", rule_obj.src_vm_table_ids)
            return False
        nodes = cls.compose_source_node(rule_obj.src_vm_table_ids)
        # 添加预计算节点
        nodes.append(
            cls.compose_process_node(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                vm_table_ids=rule_obj.src_vm_table_ids,
                waiting_time=waiting_time,
            )
        )
        node_len = len(nodes)
        # 添加存储节点
        nodes.append(
            cls.compose_vm_storage(
                bk_tenant_id=bk_tenant_id,
                table_id=table_id,
                process_id=node_len,
                expires=expires,
                schemaless=schemaless,
            )
        )
        req_data["nodes"] = nodes
        logger.info("create_flow: try to create flow for table_id->[%s] with params->[%s]", table_id, req_data)
        # 调用接口，然后保存数据
        try:
            data = api.bkdata.apply_data_flow(bk_tenant_id=bk_tenant_id, **req_data)
            logger.info("create_flow: create flow for table_id->[%s] successfully", table_id)
        except BKAPIError as e:
            logger.error("create_flow: create data flow for table_id->[%s] failed,error->[%s]", table_id, e)
            return False

        # 获取 flow_id
        flow_id = data.get("flow_id")
        if not flow_id:
            logger.error("create_flow: create data flow error, response not found flow id: %s", json.dumps(data))
            return False
        # 保存记录
        cls.objects.create(
            table_id=table_id,
            flow_id=flow_id,
            config=req_data,
            status=BkDataFlowStatus.NO_START.value,
        )
        logger.info("create_flow: create flow for table_id->[%s] successfully,flow_", table_id)
        return True

    @classmethod
    def start_flow(cls, bk_tenant_id: str, flow_id: int, consuming_mode: str | None = ConsumingMode.Current) -> bool:
        """启动 flow

        NOTE:
        - 如果要初始启动，则可以把数据设置为尾部模式，避免历史数据，影响新数据处理的延迟
        - 如果要重启，则可以把数据处理模式设置为继续

        """
        # 组装请求参数
        req_data = {
            "consuming_mode": consuming_mode,
            "cluster_group": settings.BK_DATA_FLOW_CLUSTER_GROUP,
            "flow_id": flow_id,
        }
        try:
            api.bkdata.start_data_flow(bk_tenant_id=bk_tenant_id, **req_data)
            return True
        except BKAPIError as e:
            logger.error("start data flow error, flow_id: %s, error: %s", flow_id, e)
            return False

    @classmethod
    def stop_flow(cls, bk_tenant_id: str, flow_id: int):
        """停止 flow"""
        try:
            api.bkdata.stop_data_flow(bk_tenant_id=bk_tenant_id, flow_id=flow_id)
            return True
        except BKAPIError as e:
            logger.error("stop data flow error, flow_id: %s, error: %s", flow_id, e)
            return False

    @classmethod
    def delete_flow(cls, bk_tenant_id: str, flow_id: int) -> bool:
        """删除 flow"""
        try:
            api.bkdata.delete_data_flow(bk_tenant_id=bk_tenant_id, flow_id=flow_id)
            return True
        except BKAPIError as e:
            logger.error("delete data flow error, flow_id: %s, error: %s", flow_id, e)
            return False
