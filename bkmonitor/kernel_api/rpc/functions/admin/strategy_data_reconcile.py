"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry

FUNC_STRATEGY_DATA_RECONCILE_COLLECT = "admin.strategy_data_reconcile.collect"


def _get_bk_tenant_id(params: dict[str, Any]) -> str:
    return str(params.get("bk_tenant_id") or DEFAULT_TENANT_ID).strip() or DEFAULT_TENANT_ID


def _build_response(*, operation: str, func_name: str, bk_tenant_id: str, data: dict[str, Any]) -> dict[str, Any]:
    return {
        "data": data,
        "warnings": [],
        "meta": {
            "operation": operation,
            "func_name": func_name,
            "safety_level": "read",
            "effective_bk_tenant_id": bk_tenant_id,
            "tenant_scope": "single",
        },
    }


def _normalize_bk_biz_id(value: Any) -> int:
    if value in (None, ""):
        raise CustomException(message="bk_biz_id 为必填项")
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="bk_biz_id 必须是整数") from error


def _normalize_optional_timestamp(value: Any, field_name: str) -> int | None:
    if value in (None, ""):
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message=f"{field_name} 必须是 Unix 秒级时间戳") from error

    if timestamp < 0:
        raise CustomException(message=f"{field_name} 必须大于等于 0")
    return timestamp


def _normalize_strategy_ids(value: Any) -> list[int] | None:
    if value in (None, ""):
        return None
    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, list | tuple | set):
        raw_values = value
    else:
        raise CustomException(message="strategy_ids 必须是整数列表或逗号分隔字符串")

    strategy_ids = []
    for raw_value in raw_values:
        if raw_value in (None, ""):
            continue
        try:
            strategy_ids.append(int(raw_value))
        except (TypeError, ValueError) as error:
            raise CustomException(message="strategy_ids 必须是整数列表或逗号分隔字符串") from error
    return sorted(set(strategy_ids)) if strategy_ids else None


def _normalize_max_workers(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        max_workers = int(value)
    except (TypeError, ValueError) as error:
        raise CustomException(message="max_workers 必须是整数") from error
    if max_workers < 1:
        raise CustomException(message="max_workers 必须大于等于 1")
    return max_workers


def _normalize_optional_bool(value: Any, field_name: str) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized_value = value.strip().lower()
        if normalized_value in {"true", "1", "yes", "y"}:
            return True
        if normalized_value in {"false", "0", "no", "n"}:
            return False
    raise CustomException(message=f"{field_name} 必须是布尔值")


@KernelRPCRegistry.register(
    FUNC_STRATEGY_DATA_RECONCILE_COLLECT,
    summary="Admin 统计业务策略查询数据",
    description=(
        "调用 monitor_web.data_migrate.strategy_data_reconcile.collect_strategy_data_stats，"
        "按业务统计每条非系统事件策略在指定时间段内的查询结果、维度组合数和数据点数，"
        "用于迁移前后两个环境的策略数据对账。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID；仅用于 Kernel RPC 元信息和租户注入，统计逻辑按 bk_biz_id 查询策略",
        "bk_biz_id": "必填，业务 ID",
        "start_time": "可选，查询开始时间，Unix 秒级时间戳；缺省为 end_time 往前 1 小时",
        "end_time": "可选，查询结束时间，Unix 秒级时间戳；缺省为当前时间",
        "strategy_ids": "可选，策略 ID 列表或逗号分隔字符串；不传时统计业务下全部启用策略",
        "include_dimension_keys": "可选，布尔值；true 时输出每个维度组合的稳定 JSON key 和点数，默认 false",
        "max_workers": "可选，策略查询并发数；缺省时使用统计 helper 默认值，传 1 表示串行",
    },
    example_params={
        "bk_tenant_id": "system",
        "bk_biz_id": 2,
        "start_time": 1719800000,
        "end_time": 1719803600,
        "strategy_ids": [1001, 1002],
        "include_dimension_keys": False,
        "max_workers": 4,
    },
)
def collect_strategy_data_reconcile_stats(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = _get_bk_tenant_id(params)
    bk_biz_id = _normalize_bk_biz_id(params.get("bk_biz_id"))
    start_time = _normalize_optional_timestamp(params.get("start_time"), "start_time")
    end_time = _normalize_optional_timestamp(params.get("end_time"), "end_time")
    strategy_ids = _normalize_strategy_ids(params.get("strategy_ids"))
    include_dimension_keys = _normalize_optional_bool(params.get("include_dimension_keys"), "include_dimension_keys")
    max_workers = _normalize_max_workers(params.get("max_workers"))

    if start_time is not None and end_time is not None and start_time >= end_time:
        raise CustomException(message="start_time 必须小于 end_time")

    from monitor_web.data_migrate.strategy_data_reconcile import collect_strategy_data_stats

    result = collect_strategy_data_stats(
        bk_biz_id=bk_biz_id,
        start_time=start_time,
        end_time=end_time,
        strategy_ids=strategy_ids,
        include_dimension_keys=bool(include_dimension_keys),
        **({"max_workers": max_workers} if max_workers is not None else {}),
    )
    return _build_response(
        operation="strategy_data_reconcile.collect",
        func_name=FUNC_STRATEGY_DATA_RECONCILE_COLLECT,
        bk_tenant_id=bk_tenant_id,
        data=result,
    )
