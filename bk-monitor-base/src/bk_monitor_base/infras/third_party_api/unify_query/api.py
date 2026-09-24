from typing import Any, TypedDict

from bk_monitor_base.infras.third_party_api.unify_query.client import (
    get_dimension_data_client,
    promql_to_struct_client,
    query_data_by_promql_client,
    struct_to_promql_client,
)


def promql_to_struct(bk_tenant_id: str, promql: str) -> dict[str, Any]:
    """PromQL转结构化查询参数"""
    response = promql_to_struct_client(bk_tenant_id=bk_tenant_id, params={"promql": promql})
    return response["data"]


class StructToPromqlParams(TypedDict):
    query_list: list[dict[str, Any]]
    metric_merge: str | None
    order_by: list | None
    step: str | None
    space_uid: str | None


def struct_to_promql(bk_tenant_id: str, params: StructToPromqlParams) -> str:
    """结构化查询参数转PromQL"""
    response = struct_to_promql_client(bk_tenant_id=bk_tenant_id, params=params)
    return response["data"]["promql"]


def query_data_by_promql(
    bk_tenant_id: str,
    promql: str,
    start: str,
    end: str,
    match: str | None = None,
    is_verify_dimensions: bool = False,
    bk_biz_ids: list[str] | None = None,
    step: str | None = None,
    timezone: str | None = None,
    down_sample_range: str | None = None,
    reference: bool = False,
) -> dict[str, Any]:
    """使用PromQL查询数据

    Args:
        bk_tenant_id: 租户ID
        promql: PromQL查询语句
        start: 开始时间
        end: 结束时间
        match: 匹配条件
        is_verify_dimensions: 是否验证维度
        bk_biz_ids: 业务ID列表
        step: 步长，格式：数字+(ms|s|m|h|d|w|y)，例如：30s, 1m, 5m
        timezone: 时区
        down_sample_range: 降采样范围
        reference: 是否引用

    Returns:
        查询结果

    Raises:
        BkApiError: 接口调用失败
        ValueError: 参数验证失败
    """
    import re

    # 验证step格式（如果提供）
    if step is not None:
        step_pattern = r"^\d+(ms|s|m|h|d|w|y)$"
        if not re.match(step_pattern, step):
            raise ValueError(
                f"Invalid step format: '{step}'. Expected format: number+(ms|s|m|h|d|w|y), e.g., '30s', '1m', '5m'"
            )

    # 构建参数字典
    params: dict[str, Any] = {
        "promql": promql,
        "start": start,
        "end": end,
        "is_verify_dimensions": is_verify_dimensions,
        "reference": reference,
    }

    # 添加可选参数
    if match is not None:
        params["match"] = match
    if bk_biz_ids is not None:
        params["bk_biz_ids"] = bk_biz_ids
    if step is not None:
        params["step"] = step
    if timezone is not None:
        params["timezone"] = timezone
    if down_sample_range is not None:
        params["down_sample_range"] = down_sample_range

    return query_data_by_promql_client(bk_tenant_id=bk_tenant_id, params=params)


class GetDimensionDataParams(TypedDict, total=False):
    """获取维度数据的参数"""

    space_uid: str | None
    info_type: str  # 必填：请求资源类型
    table_id: str
    conditions: dict[str, Any]
    keys: list[str]
    limit: int
    metric_name: str | None
    start_time: str
    end_time: str


def get_dimension_data(bk_tenant_id: str, params: GetDimensionDataParams) -> dict[str, Any]:
    """获取维度数据

    Args:
        bk_tenant_id: 租户ID
        params: 查询参数，包含以下字段：
            - info_type: 请求资源类型（必填）
            - space_uid: 空间UID（可选）
            - table_id: 表ID（可选）
            - conditions: 查询条件（可选）
            - keys: 查询的维度字段列表（可选）
            - limit: 返回数据条数限制，默认1000（可选）
            - metric_name: 指标名称（可选）
            - start_time: 开始时间（可选）
            - end_time: 结束时间（可选）

    Returns:
        维度数据查询结果

    Raises:
        BkApiError: 接口调用失败
        ValueError: 参数验证失败
    """
    response = get_dimension_data_client(bk_tenant_id=bk_tenant_id, params=params)
    return response["data"]
