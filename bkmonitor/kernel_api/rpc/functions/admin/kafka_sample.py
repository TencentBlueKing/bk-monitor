"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from datetime import UTC, datetime
from typing import Any

from core.drf_resource import resource
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, get_bk_tenant_id
from kernel_api.rpc.functions.admin.kafka_status import (
    KAFKA_FRESHNESS_THRESHOLD_SECONDS,
    _summarize_payload_timestamps,
)

FUNC_DATASOURCE_KAFKA_SAMPLE = "admin.datasource.kafka_sample"
KAFKA_SAMPLE_MAX_SIZE = 50
KAFKA_SAMPLE_DEFAULT_SIZE = 10


def _normalize_sample_size(value: Any) -> int:
    if value in (None, ""):
        return KAFKA_SAMPLE_DEFAULT_SIZE
    try:
        size = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="size 必须是整数") from error
    if size < 1:
        raise CustomException(message="size 必须大于等于 1")
    return min(size, KAFKA_SAMPLE_MAX_SIZE)


@KernelRPCRegistry.register(
    FUNC_DATASOURCE_KAFKA_SAMPLE,
    summary="Admin Kafka 采样数据",
    description=(
        "inspect：通过 resource.metadata.kafka_tail 拉取指定 DataSource 的 Kafka 尾部样例，并从消息体提取最近业务时间。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID",
        "bk_data_id": "必填，数据源 ID",
        "size": f"可选，返回样例条数，默认 {KAFKA_SAMPLE_DEFAULT_SIZE}，最大 {KAFKA_SAMPLE_MAX_SIZE}",
    },
    example_params={"bk_tenant_id": "system", "bk_data_id": 50010, "size": 10},
)
def kafka_sample(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_data_id = params.get("bk_data_id")
    if bk_data_id in (None, ""):
        raise CustomException(message="bk_data_id 为必填项")
    try:
        bk_data_id = int(bk_data_id)
    except (TypeError, ValueError) as error:
        raise CustomException(message="bk_data_id 必须是整数") from error
    size = _normalize_sample_size(params.get("size"))

    try:
        items = resource.metadata.kafka_tail(
            bk_tenant_id=bk_tenant_id,
            bk_data_id=bk_data_id,
            size=size,
            use_gse_config=True,
        )
    except Exception as error:
        raise CustomException(message=f"Kafka Tail 采样失败: {error}") from error
    if not isinstance(items, list):
        raise CustomException(message="Kafka Tail 返回结构不是数组")

    checked_at = datetime.now(tz=UTC)
    timestamp_summary = _summarize_payload_timestamps(items, checked_at)

    return build_response(
        operation="datasource.kafka_sample",
        func_name=FUNC_DATASOURCE_KAFKA_SAMPLE,
        bk_tenant_id=bk_tenant_id,
        safety_level="inspect",
        data={
            "bk_data_id": bk_data_id,
            "topic": None,
            "topics": [],
            "items": items,
            "count": len(items),
            "checked_at": checked_at.isoformat().replace("+00:00", "Z"),
            "freshness_threshold_seconds": KAFKA_FRESHNESS_THRESHOLD_SECONDS,
            "partitions_checked": 0,
            "warnings": [],
            **timestamp_summary,
        },
    )
