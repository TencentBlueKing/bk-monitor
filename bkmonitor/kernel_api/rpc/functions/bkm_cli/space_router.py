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

import json
import logging
from typing import Any

from django.conf import settings

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.bkm_cli_registry import BkmCliOpRegistry
from kernel_api.rpc.functions.admin.common import get_bk_tenant_id
from metadata.models.space.constants import RESULT_TABLE_DETAIL_KEY, SPACE_TO_RESULT_TABLE_KEY
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("kernel_api")


def _decode(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _hget_with_tenant(redis_key: str, base_field: str, bk_tenant_id: str) -> tuple[Any, str]:
    """按环境 regime 组装 hash field 并读取，返回 (raw, 实际命中的 field)。

    ⚠️ 关键：metadata 写入侧只在 `settings.ENABLE_MULTI_TENANT_MODE` 为真时才给 field 拼 `|{bk_tenant_id}`
    后缀（源：space_table_id_redis.py:102-105 / :260-265；所有 reader 如 bkdata_link.py:397-400 均按此
    flag 分支）。单租户(默认)环境 field 是裸 `{base_field}`。这里必须同样按 flag 分支——否则单租户环境
    查 `{base_field}|system` 恒 miss，把「已正确路由」误报成「未收录/健康」，恰好败坏本 op 的取证目的。
    再加一层兜底：主 field miss 时回退另一种形态，容忍 flag 与实际数据不一致的边缘情况。
    """
    suffixed = f"{base_field}|{bk_tenant_id}"
    primary = suffixed if settings.ENABLE_MULTI_TENANT_MODE else base_field
    raw = RedisTools.hget(redis_key, primary)
    if raw is not None:
        return raw, primary
    fallback = base_field if primary == suffixed else suffixed
    raw = RedisTools.hget(redis_key, fallback)
    if raw is not None:
        return raw, fallback
    return None, primary


def read_space_router(params: dict[str, Any]) -> dict[str, Any]:
    """bkm-cli 服务桥：读 metadata 空间路由 Redis（`bkmonitorv3:spaces`）的最终事实。

    这是「多 RT 跨 VM 集群 / 多租户未对齐致 storage_name 空」类查空的**最末段直证**：
    - operation=result_table_detail：读某结果表的 storage 归属（`storage_name`/`storage_id`/`vm_rt`/
      `storage_type`）——`storage_name` 空串即 unify-query 无从路由到 VM 集群、必查空（b 类元数据陈旧/
      多租户未对齐的坐实证据）。field = `{table_id}`（单租户）或 `{table_id}|{bk_tenant_id}`（多租户）。
    - operation=space_to_result_table：读某空间路由收录了哪些结果表——判「RT 有没有进空间路由」。
      field = `{space_type}__{space_id}`（单租户）或带 `|{bk_tenant_id}`（多租户）。

    hash field 是否带 `|{bk_tenant_id}` 后缀由 `settings.ENABLE_MULTI_TENANT_MODE` 决定（与写入侧一致），
    见 `_hget_with_tenant`；返回体回显实际命中的 `field`。

    只读：仅 RedisTools.hget，无写。这是 metadata 自有 Redis（前缀 `bkmonitorv3:spaces`），
    与 alarm_backends 的 read-cache-key（`alarm_backends/core/cache/key.py` 运行时状态键）不是同一套，
    故独立成 op、不塞进 read-cache-key 白名单。
    """
    bk_tenant_id = get_bk_tenant_id(params)
    operation = str(params.get("operation") or "").strip()

    if operation == "result_table_detail":
        table_id = str(params.get("table_id") or "").strip()
        if not table_id:
            raise CustomException(message="operation=result_table_detail 时 table_id 为必填项")
        raw, field = _hget_with_tenant(RESULT_TABLE_DETAIL_KEY, table_id, bk_tenant_id)
        exists = raw is not None
        detail: Any = None
        if exists:
            try:
                detail = json.loads(_decode(raw))
            except (ValueError, TypeError):
                detail = _decode(raw)
        storage_name = detail.get("storage_name") if isinstance(detail, dict) else None
        return {
            "operation": operation,
            "redis_key": RESULT_TABLE_DETAIL_KEY,
            "field": field,
            "multi_tenant_mode": bool(settings.ENABLE_MULTI_TENANT_MODE),
            "exists": exists,
            # storage_name 为空串/None 是查空的确定性信号：unify-query 拿不到 VM 集群归属。
            # 仅当 detail 解析为 dict 才判定；非 dict（解析失败）不误报 empty。
            "storage_name_empty": exists and isinstance(detail, dict) and not storage_name,
            "detail": detail,
        }

    if operation == "space_to_result_table":
        space_type = str(params.get("space_type") or "").strip()
        space_id = str(params.get("space_id") or "").strip()
        if not space_type or not space_id:
            raise CustomException(message="operation=space_to_result_table 时 space_type 与 space_id 均为必填项")
        raw, field = _hget_with_tenant(SPACE_TO_RESULT_TABLE_KEY, f"{space_type}__{space_id}", bk_tenant_id)
        exists = raw is not None
        table_ids: Any = None
        if exists:
            try:
                table_ids = json.loads(_decode(raw))
            except (ValueError, TypeError):
                table_ids = _decode(raw)
        # table_ids 结构为 {table_id: {filters:[...]}} 或 [table_id,...]，可能很大——
        # 只回 key 列表 + 计数，避免整体灌进 agent 上下文。
        if isinstance(table_ids, dict):
            rt_list = sorted(table_ids.keys())
        elif isinstance(table_ids, list):
            rt_list = table_ids
        else:
            rt_list = []
        return {
            "operation": operation,
            "redis_key": SPACE_TO_RESULT_TABLE_KEY,
            "field": field,
            "multi_tenant_mode": bool(settings.ENABLE_MULTI_TENANT_MODE),
            "exists": exists,
            "result_table_count": len(rt_list),
            "result_table_ids": rt_list,
        }

    raise CustomException(message="operation 必须是 result_table_detail 或 space_to_result_table")


KernelRPCRegistry.register_function(
    func_name="bkm_cli.read_space_router",
    summary="读 metadata 空间路由 Redis（bkmonitorv3:spaces）：结果表 storage 归属 / 空间收录的结果表",
    description=(
        "只读 RedisTools.hget：operation=result_table_detail 读某表的 storage_name/storage_id/vm_rt"
        "（storage_name 空即 unify-query 查空的坐实）；operation=space_to_result_table 读某空间路由收录的 RT 列表。"
        "field 多租户下带 |{bk_tenant_id} 后缀。metadata 自有 Redis，非 alarm_backends read-cache-key。"
    ),
    handler=read_space_router,
    params_schema={
        "bk_tenant_id": "可选，租户 ID（默认 system；多租户环境务必传对，field 带此后缀）",
        "operation": "必填，result_table_detail | space_to_result_table",
        "table_id": "result_table_detail 必填，结果表 ID（如 system_20001_sys.cpu_summary）",
        "space_type": "space_to_result_table 必填，空间类型（如 bkcc）",
        "space_id": "space_to_result_table 必填，空间 ID（如 20001）",
    },
    example_params={
        "bk_tenant_id": "system",
        "operation": "result_table_detail",
        "table_id": "system_20001_sys.cpu_summary",
    },
)

BkmCliOpRegistry.register(
    op_id="read-space-router",
    func_name="bkm_cli.read_space_router",
    summary="读空间路由 Redis：查空最末段（storage_name 空/RT 未进路由）直证",
    description=(
        "多 RT 跨 VM 集群 / 多租户未对齐致 storage_name 空 类查空的最末段直证。"
        "result_table_detail 看某表 storage_name 是否空（空=unify-query 无从路由到 VM→查空）；"
        "space_to_result_table 看某空间路由是否收录了该 RT。多租户务必传对 bk_tenant_id。"
    ),
    capability_level="readonly",
    risk_level="low",
    requires_confirmation=False,
    audit_tags=["metadata", "readonly", "space-router", "unify-query"],
    params_schema={
        "bk_tenant_id": "string",
        "operation": "string",
        "table_id": "string",
        "space_type": "string",
        "space_id": "string",
    },
    example_params={
        "bk_tenant_id": "system",
        "operation": "result_table_detail",
        "table_id": "system_20001_sys.cpu_summary",
    },
)
