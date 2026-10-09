from typing import Any, TypedDict

from bk_monitor_base.infras.third_party_api.log_search.client import (
    fetch_statistics_graph_client,
    fetch_statistics_info_client,
    fetch_topk_list_client,
    list_es_router_client,
)


class BaseLogSearchParams(TypedDict, total=False):
    """日志检索通用参数

    Attributes:
        bk_biz_id: 业务ID
        index_set_ids: 索引集ID列表
        agg_field: 聚合字段
        start_time: 开始时间 (秒级时间戳)
        end_time: 结束时间 (秒级时间戳)
        time_range: 时间范围
        keyword: 查询关键字
        addition: 附加条件
        host_scopes: 主机范围
        ip_chooser: IP选择器
    """

    bk_biz_id: int | str
    index_set_ids: list[int]
    agg_field: str
    start_time: int
    end_time: int
    time_range: str
    keyword: str
    addition: dict
    host_scopes: dict
    ip_chooser: dict


class TopKParams(BaseLogSearchParams, total=False):
    """TopK 参数

    Attributes:
        limit: 返回数量限制
    """

    limit: int


class StatisticsInfoParams(BaseLogSearchParams, total=False):
    """统计信息参数

    Attributes:
        field_type: 字段类型
    """

    field_type: str


class StatisticsGraphParams(BaseLogSearchParams, total=False):
    """统计图表参数

    Attributes:
        field_type: 字段类型
        max: 最大值
        min: 最小值
        threshold: 分桶阈值
        limit: 返回数量限制
        distinct_count: 去重后字段计数
    """

    field_type: str
    max: float | int | None
    min: float | int | None
    threshold: float | int | None
    limit: int
    distinct_count: int | None


class ValueAnalysis(TypedDict, total=False):
    """数值分析结果

    Attributes:
        max: 最大值
        min: 最小值
        avg: 平均值
        median: 中位数
    """

    max: float
    min: float
    avg: float
    median: float


class StatisticsInfoResult(TypedDict, total=False):
    """字段统计信息结果

    Attributes:
        total_count: 总记录数
        distinct_count: 去重计数
        field_count: 字段计数
        field_percent: 字段占比
        value_analysis: 数值分析
    """

    total_count: int
    distinct_count: int
    field_count: int
    field_percent: float
    value_analysis: ValueAnalysis


class TopKListResult(TypedDict, total=False):
    """TopK 列表结果

    Attributes:
        name: 字段名
        columns: 列名列表
        types: 列类型列表
        limit: 限制数量
        total_count: 总记录数
        field_count: 字段计数
        distinct_count: 去重计数
        values: 值列表
    """

    name: str
    columns: list[str]
    types: list[str]
    limit: int
    total_count: int
    field_count: int
    distinct_count: int
    values: list[list[Any]]


class GraphSeries(TypedDict, total=False):
    """图表序列数据

    Attributes:
        name: 序列名称
        metric_name: 指标名称
        columns: 列名列表
        types: 列类型列表
        group_keys: 分组键列表
        group_values: 分组值列表
        values: 数据点列表
    """

    name: str
    metric_name: str
    columns: list[str]
    types: list[str]
    group_keys: list[str]
    group_values: list[str]
    values: list[list[int | float | str]]


class StatisticsGraphDictResult(TypedDict, total=False):
    """统计图表字典结果

    Attributes:
        series: 图表序列列表
    """

    series: list[GraphSeries]


# 统计图表返回类型：dict (关键词 topk 图表包含 series) 或 list (TopK列表 或 分桶数据)
StatisticsGraphResult = StatisticsGraphDictResult | list[Any]


def list_es_router(bk_tenant_id: str, space_uid: str = "", page: int = 1, pagesize: int = 10) -> dict[str, Any]:
    """
    获取Es的结果表

    Args:
        bk_tenant_id: 租户ID
        space_uid: 空间UID
        page: 页码
        pagesize: 页大小

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    params: dict[str, Any] = {"page": page, "pagesize": pagesize}
    if space_uid:
        params["space_uid"] = space_uid
    return list_es_router_client(
        bk_tenant_id=bk_tenant_id,
        params=params,
    )


def fetch_statistics_info(bk_tenant_id: str, params: StatisticsInfoParams) -> StatisticsInfoResult:
    """
    获取统计信息

    :param bk_tenant_id: 租户ID
    :param params: 统计信息参数
    :return: 统计结果
    """
    return fetch_statistics_info_client(bk_tenant_id=bk_tenant_id, params=params)


def fetch_statistics_graph(bk_tenant_id: str, params: StatisticsGraphParams) -> StatisticsGraphResult:
    """
    获取统计图表

    :param bk_tenant_id: 租户ID
    :param params: 统计图表参数
    :return: 统计图表数据
    """
    return fetch_statistics_graph_client(bk_tenant_id=bk_tenant_id, params=params)


def fetch_topk_list(bk_tenant_id: str, params: TopKParams) -> TopKListResult:
    """
    获取TopK列表

    :param bk_tenant_id: 租户ID
    :param params: TopK 参数
    :return: TopK 列表数据
    """
    return fetch_topk_list_client(bk_tenant_id=bk_tenant_id, params=params)
