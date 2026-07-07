"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

import logging
from typing import Any

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.admin.common import get_bk_tenant_id
from kernel_api.rpc.functions.admin.kafka_sample import kafka_sample as _admin_kafka_sample

logger = logging.getLogger("kernel_api")

# bkm-cli 服务桥出口默认上限（比 admin 的 50 更保守——排障二分只需少量样本即可判「有数/无数」）。
BKM_CLI_KAFKA_SAMPLE_MAX_SIZE = 20
BKM_CLI_KAFKA_SAMPLE_DEFAULT_SIZE = 5


def kafka_sample(params: dict[str, Any]) -> dict[str, Any]:
    """bkm-cli 服务桥：按 bk_data_id 拉取 Kafka topic 最近 N 条消息样本（消费后立即断开）。

    复用 admin.datasource.kafka_sample 的核心逻辑（已覆盖全部链路类型：confluent-SASL /
    V4-bkbase tail_kafka_data / V3-AccessVMRecord→bkdata / GSE 路由 / 纯 kafka-python），
    只在 bkm-cli 出口做两件事：
      1. size 上限收敛到 BKM_CLI_KAFKA_SAMPLE_MAX_SIZE（排障二分只需判「有数/无数」，
         不需要大批量；避免服务桥拉过多数据进 agent 上下文）；
      2. 返回体在 admin 数据基础上补 `has_data` 布尔——这是「查空≠源头无数据」二分节点的
         直接判据：has_data=True ⇒ 采集侧在报、断点在下游链路；has_data=False ⇒ 采集/上报侧问题。

    只读语义：admin 侧消费用随机 group.id + auto.offset.reset=latest + 消费后立即 close，
    不提交 offset、不影响任何生产消费组。
    """
    bk_tenant_id = get_bk_tenant_id(params)

    bk_data_id = params.get("bk_data_id")
    if bk_data_id in (None, ""):
        raise CustomException(message="bk_data_id 为必填项")

    # size 上限在 bkm-cli 出口收敛（admin 侧 min(size, 50)，这里进一步压到 20）。
    size = params.get("size", BKM_CLI_KAFKA_SAMPLE_DEFAULT_SIZE)
    if size in (None, ""):
        size = BKM_CLI_KAFKA_SAMPLE_DEFAULT_SIZE
    try:
        size = int(size)
    except (TypeError, ValueError) as error:
        raise CustomException(message="size 必须是整数") from error
    if size < 1:
        raise CustomException(message="size 必须大于等于 1")
    size = min(size, BKM_CLI_KAFKA_SAMPLE_MAX_SIZE)

    admin_params: dict[str, Any] = {"bk_tenant_id": bk_tenant_id, "bk_data_id": bk_data_id, "size": size}
    if params.get("namespace"):
        admin_params["namespace"] = params["namespace"]

    admin_response = _admin_kafka_sample(admin_params)
    data = admin_response.get("data", {}) if isinstance(admin_response, dict) else {}

    items = data.get("items", []) or []
    count = data.get("count", len(items))

    return {
        "bk_data_id": data.get("bk_data_id"),
        "topic": data.get("topic"),
        "count": count,
        # 二分判据：Kafka 有数 ⇒ 采集/上报健康、断点在下游（入库/路由/查询）；
        # Kafka 空 ⇒ 采集或上报侧问题。别把「空」直接当业务事实——先确认 dataid/topic 解析正确、
        # 该链路当前确有流量（低频 dataid 短时窗可能天然为空）。
        "has_data": count > 0,
        "items": items,
    }


KernelRPCRegistry.register_function(
    func_name="bkm_cli.kafka_sample",
    summary="按 bk_data_id 拉取 Kafka topic 最近 N 条消息样本（只读，消费后立即断开）",
    description=(
        "复用 admin kafka_sample 核心：解析 DataSource→topic（含 GSE route 覆盖），"
        "覆盖 confluent-SASL / V4-bkbase / V3-AccessVMRecord→bkdata / GSE / 纯 kafka-python 全链路类型；"
        "随机 group.id + latest + 消费后 close，不提交 offset。返回 has_data 作为「采集 vs 链路」二分判据。"
    ),
    handler=kafka_sample,
    params_schema={
        "bk_tenant_id": "可选，租户 ID（默认 system）",
        "bk_data_id": "必填，数据源 ID（DataSource.bk_data_id）",
        "size": f"可选，拉取条数，默认 {BKM_CLI_KAFKA_SAMPLE_DEFAULT_SIZE}，最大 {BKM_CLI_KAFKA_SAMPLE_MAX_SIZE}",
        "namespace": "可选，V3-VM 链路 bkbase tail 的 namespace（默认 bkmonitor）",
    },
    example_params={"bk_tenant_id": "system", "bk_data_id": 624459, "size": 5},
)

BkmCliOpRegistry.register(
    op_id="kafka-sample",
    func_name="bkm_cli.kafka_sample",
    summary="按 dataid 取 Kafka topic 消息样本（采集 vs 链路 二分节点）",
    description=(
        "排障二分：拿到 DataSource 的 bk_data_id 后，直接看 Kafka topic 有没有数据。"
        "has_data=True ⇒ 主机/采集侧在报、断点在下游（入库/metadata 路由/unify-query 查询）；"
        "has_data=False ⇒ 采集或上报侧问题（先确认 dataid/topic 解析对、该链路当前确有流量再下结论）。"
        "配合「查空≠源头无数据」护栏：把原本靠用户手报『Kafka 有没有数』的一步收进只读 op。"
    ),
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["kafka", "readonly", "datasource", "bisect"],
    params_schema={
        "bk_tenant_id": "string",
        "bk_data_id": "integer",
        "size": "integer",
        "namespace": "string",
    },
    example_params={"bk_tenant_id": "system", "bk_data_id": 624459, "size": 5},
)
