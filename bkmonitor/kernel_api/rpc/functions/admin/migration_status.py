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

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc import KernelRPCRegistry
from kernel_api.rpc.functions.admin.common import build_response, get_bk_tenant_id, normalize_optional_bool
from monitor_web.data_migrate.migration_status_check import collect_migration_status

FUNC_MIGRATION_STATUS_CHECK = "admin.migration_status.check"


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


@KernelRPCRegistry.register(
    FUNC_MIGRATION_STATUS_CHECK,
    summary="Admin 查询业务迁移状态",
    description=(
        "调用 monitor_web.data_migrate.migration_status_check.collect_migration_status，"
        "按业务汇总主机、K8S、拨测、自定义上报、插件采集、APM 和策略等迁移后状态。"
    ),
    params_schema={
        "bk_tenant_id": "可选，租户 ID；缺省时使用默认租户或由 Kernel RPC 根据 bk_biz_id 注入",
        "bk_biz_id": "必填，业务 ID",
        "start_time": "可选，查询开始时间，Unix 秒级时间戳；缺省为 end_time 往前 1 小时",
        "end_time": "可选，查询结束时间，Unix 秒级时间戳；缺省为当前时间",
        "with_detail": "可选，布尔值；true 时返回更详细的检查信息，默认 false",
    },
    example_params={"bk_tenant_id": "system", "bk_biz_id": 2, "with_detail": False},
)
def check_migration_status(params: dict[str, Any]) -> dict[str, Any]:
    bk_tenant_id = get_bk_tenant_id(params)
    bk_biz_id = _normalize_bk_biz_id(params.get("bk_biz_id"))
    start_time = _normalize_optional_timestamp(params.get("start_time"), "start_time")
    end_time = _normalize_optional_timestamp(params.get("end_time"), "end_time")
    with_detail = normalize_optional_bool(params.get("with_detail"), "with_detail")

    if start_time is not None and end_time is not None and start_time >= end_time:
        raise CustomException(message="start_time 必须小于 end_time")

    result = collect_migration_status(
        bk_tenant_id=bk_tenant_id,
        bk_biz_id=bk_biz_id,
        start_time=start_time,
        end_time=end_time,
        with_detail=bool(with_detail),
    )
    return build_response(
        operation="migration_status.check",
        func_name=FUNC_MIGRATION_STATUS_CHECK,
        bk_tenant_id=bk_tenant_id,
        data=result,
    )
