"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from typing import Any

from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.documents import AlertDocument
from constants.data_source import DataSourceLabel, DataTypeLabel

logger = logging.getLogger("fta_action.run")

MONITOR_TO_LOG_OPERATOR_MAP: dict[str, str] = {
    "=": "=",
    "!=": "!=",
    "eq": "=",
    "neq": "!=",
    "is": "=",
    "is not": "!=",
    "is one of": "=",
    "is not one of": "!=",
    "contains match phrase": "contains",
    "not contains match phrase": "not contains",
    "include": "contains",
    "exclude": "not contains",
    "contains": "contains",
    "not contains": "not contains",
}


class ClusteringType:
    NEW_CLASS = "new_class"
    COUNT = "count"


def get_alert_query_config_or_none(alert: AlertDocument) -> dict[str, Any] | None:
    """获取告警策略的查询配置。

    :param alert: 告警文档对象
    :return: 查询配置字典，如果获取失败则返回 None
    """
    try:
        return alert.strategy["items"][0]["query_configs"][0]
    except (KeyError, IndexError, TypeError):
        return None


def get_alert_data_source_or_none(alert: AlertDocument) -> tuple[str, str] | None:
    """获取告警的数据源类型。

    从告警策略的 query_config 中提取数据源标签和数据类型标签。

    :param alert: 告警文档对象
    :return: 数据源类型元组 (data_source_label, data_type_label)，如果获取失败则返回 None
    """
    query_config: dict[str, Any] | None = get_alert_query_config_or_none(alert)
    if query_config is None:
        return None
    return query_config.get("data_source_label", ""), query_config.get("data_type_label", "")


def get_alert_dimensions(alert: AlertDocument) -> dict[str, Any]:
    """获取告警的有效维度信息。

    从告警原始数据中提取维度信息，并过滤出在 dimension_fields 中有效的维度字段。

    :param alert: 告警文档对象
    :return: 过滤后的有效维度字典
    """
    alert_data: dict[str, Any] = alert.origin_alarm.get("data", {})
    # 获取原始告警中维度信息
    dimensions: dict[str, str | int] = alert_data.get("dimensions", {})
    # 获取告警策略配置的维度字段列表
    dimension_fields: list[str] = alert_data.get("dimension_fields", [])

    return {k: v for k, v in dimensions.items() if k in dimension_fields}


def _get_log_clustering_type(label: str) -> str | None:
    """获取日志聚类标签类型。"""
    if label.startswith("LogClustering/NewClass/") and label.split("/")[-1]:
        return ClusteringType.NEW_CLASS
    if label.startswith("LogClustering/Count/") and label.split("/")[-1]:
        return ClusteringType.COUNT
    return None


def get_log_clustering_info(strategy: dict[str, Any]) -> tuple[str | None, str | None]:
    """从日志聚类告警策略标签中提取聚类类型和索引集 ID。"""
    for label in strategy.get("labels") or []:
        clustering_type = _get_log_clustering_type(label)
        if clustering_type:
            index_set_id: str = label.split("/")[-1]
            if index_set_id:
                return clustering_type, index_set_id
    return None, None


def get_log_clustering_time_range(alert: AlertDocument, clustering_type: str) -> tuple[int, int] | None:
    """获取日志聚类告警关联日志检索的时间范围。"""
    query_config: dict[str, Any] | None = get_alert_query_config_or_none(alert)
    if query_config is None:
        return None

    interval: int = query_config.get("agg_interval", 60)
    if clustering_type == ClusteringType.COUNT:
        start_time: int = alert.begin_time - 60 * 60
    elif clustering_type == ClusteringType.NEW_CLASS:
        start_time = alert.begin_time
    else:
        return None

    end_time: int = max(alert.begin_time + interval, alert.latest_time)
    return start_time, end_time


def get_log_clustering_filter_dict(
    alert: AlertDocument, clustering_type: str, start_time: int | None = None, end_time: int | None = None
) -> dict[str, list[str]]:
    """提取日志聚类告警额外过滤条件。

    返回格式为 ``{sensitivity: signatures}``，用于补充日志检索的过滤条件。
    """
    if clustering_type == ClusteringType.COUNT:
        try:
            dimensions: dict[str, Any] = alert.origin_alarm["data"]["dimensions"]
            if "__dist_05" in dimensions:
                return {"__dist_05": [dimensions["__dist_05"]]}

            return {dimensions.get("sensitivity", "__dist_05"): [dimensions["signature"]]}
        except Exception as e:
            logger.exception("[get_log_clustering_extra_filter_dict] get count dimension error: %s", e)
            return {}

    if clustering_type != ClusteringType.NEW_CLASS:
        return {}

    signatures: list[str] = []
    try:
        dimensions: dict[str, Any] = alert.origin_alarm["data"]["dimensions"]
        if dimensions.get("signature"):
            signatures = [dimensions["signature"]]

        # 新类敏感度默认取最低档，即最少告警
        sensitivity: str = dimensions.get("sensitivity", "__dist_09")
        if not sensitivity.startswith("__"):
            sensitivity = "__" + sensitivity
    except Exception as e:
        logger.exception("[get_log_clustering_extra_filter_dict] get new class dimension error: %s", e)
        sensitivity = "__dist_09"

    if signatures:
        return {sensitivity: signatures}

    if start_time is None or end_time is None:
        return {}

    query_config: dict[str, Any] | None = get_alert_query_config_or_none(alert)
    if not query_config:
        return {}

    data_source_class = load_data_source(query_config["data_source_label"], query_config["data_type_label"])
    data_source = data_source_class.init_by_query_config(query_config, bk_biz_id=alert.event.bk_biz_id)
    uq: UnifyQuery = UnifyQuery(bk_biz_id=alert.event.bk_biz_id, data_sources=[data_source], expression="")
    # limit 用于占位，最终会被 pop 掉。
    signatures = uq.query_dimensions(
        dimension_field="signature", start_time=start_time * 1000, end_time=end_time * 1000, limit=1
    )
    return {sensitivity: signatures}


def build_log_search_condition(
    query_config: dict[str, Any],
    dimensions: dict[str, Any],
    exclude_fields: set[str] | None = None,
    extra_filter_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造日志查询过滤条件。

    按顺序构造日志查询的 addition 列表，先添加额外过滤条件，再添加告警维度作为精确匹配条件，
    最后添加策略过滤条件（排除已存在的维度 key）。
    如果策略过滤条件中存在 OR 条件，则仅使用告警维度作为过滤条件（日志平台不支持 OR 条件）

    :param query_config: 告警策略查询配置
    :param dimensions: 已过滤的告警维度信息字典（仅包含有效维度字段）
    :param exclude_fields: 需要从 dimensions 和 agg_condition 中排除的字段
    :param extra_filter_dict: 额外过滤条件，格式为 {field: values}
    :return: 包含 addition 列表和 keyword 字符串的字典
    """
    exclude_fields = exclude_fields or set()
    addition: list[dict[str, Any]] = []
    added_filter_keys: set[str] = set()

    # 先添加额外过滤条件，例如日志聚类的 {sensitivity: signatures}
    for field, value in (extra_filter_dict or {}).items():
        addition.append(
            {
                "field": field,
                "operator": "=",
                "value": value if isinstance(value, list) else [value],
            }
        )
        added_filter_keys.add(field)

    # 再添加告警维度作为精确匹配条件
    for field, value in dimensions.items():
        if field in exclude_fields or field in added_filter_keys:
            continue

        addition.append(
            {
                "field": field,
                "operator": "=",
                "value": value if isinstance(value, list) else [value],
            }
        )
        added_filter_keys.add(field)

    # 检查是否存在 or 条件，如果存在则仅使用告警维度
    agg_condition: list[dict[str, Any]] = query_config.get("agg_condition") or []
    has_or_condition: bool = any(cond.get("condition", "") == "or" for cond in agg_condition)
    if not has_or_condition:
        for condition in agg_condition:
            condition_key: str = condition["key"]
            if condition_key in exclude_fields or condition_key in added_filter_keys:
                continue

            # 转换操作符为日志平台格式，如果不支持则跳过该条件
            operator: str = condition.get("method") or "="
            log_operator: str | None = MONITOR_TO_LOG_OPERATOR_MAP.get(operator)
            if log_operator is None:
                continue

            addition.append(
                {
                    "field": condition_key,
                    "operator": log_operator,
                    "value": condition.get("value", []),
                }
            )

    return {
        "addition": addition,
        "keyword": query_config.get("query_string", ""),
    }


def merge_dimensions_into_conditions(
    agg_condition: list[dict[str, Any]] | None,
    dimensions: dict[str, Any],
) -> list[dict[str, Any]]:
    """合并维度信息到初始过滤条件中。

    将维度信息合并到初始过滤条件中，用于告警下钻时构建查询过滤条件。
    如果维度已存在于初始条件中，则用维度值覆盖；如果维度不存在于初始条件中，则添加为新的过滤条件。

    :param agg_condition: 初始过滤条件列表
    :param dimensions: 已过滤的维度信息字典（仅包含有效维度字段）
    :return: 合并后的过滤条件列表
    """
    # 使用告警策略配置的汇聚条件作为初始过滤条件
    filter_conditions: list[dict[str, Any]] = agg_condition or []

    # 构建 key → 索引位置的映射，方便后续更新替换
    condition_index: dict[str, int] = {condition["key"]: idx for idx, condition in enumerate(filter_conditions)}

    # 遍历告警的原始维度信息，增加维度过滤条件
    for key, value in dimensions.items():
        condition: dict[str, Any] = {
            "key": key,
            "method": "eq",
            "value": value if isinstance(value, list) else [value or ""],
            "condition": "and",
        }
        # 如果该维度已存在于汇聚条件中，则更新替换；否则添加为新过滤条件
        if key in condition_index:
            filter_conditions[condition_index[key]] = condition
        else:
            filter_conditions.append(condition)

    return filter_conditions


def clean_where_conditions(where: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """清洗 where 过滤条件列表。

    过滤掉 value 为 None、空列表或仅包含 None 的无效条件，
    同时移除有效条件列表中混杂的 None 值。

    :param where: where 过滤条件列表
    :return: 清洗后的过滤条件列表
    """
    cleaned: list[dict[str, Any]] = []
    for condition in where:
        value = condition.get("value")
        if value is None:
            continue
        if isinstance(value, list):
            filtered_value = [v for v in value if v is not None]
            if not filtered_value:
                continue
            condition["value"] = filtered_value
        cleaned.append(condition)
    return cleaned


def normalize_histogram_quantile_group_by(query_config: dict[str, Any]) -> None:
    """规范 histogram_quantile 函数 group_by 条件。

    注：histogram_quantile 统计函数依赖 le 维度进行分位数插值计算，但维度下钻、告警图表等场景会覆盖 group_by 导致 le 丢失
    """
    data_source: tuple[str, str] = (query_config["data_source_label"], query_config["data_type_label"])
    if data_source != (DataSourceLabel.CUSTOM, DataTypeLabel.TIME_SERIES):
        return
    if not any(f.get("id") == "histogram_quantile" for f in query_config.get("functions", [])):
        return
    group_by: list[str] = query_config.get("group_by") or []
    if "le" not in group_by:
        group_by.append("le")
        query_config["group_by"] = group_by
