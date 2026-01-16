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

from bkmonitor.documents import AlertDocument


_MONITOR_TO_LOG_OPERATOR_MAP: dict[str, str] = {
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


def convert_operator_to_log_platform(operator: str) -> str | None:
    """将监控平台操作符转换为日志平台操作符"""

    return _MONITOR_TO_LOG_OPERATOR_MAP.get(operator)


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


def get_alert_dimensions(alert: AlertDocument) -> dict[str, str | None]:
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


def build_log_search_condition(query_config: dict[str, Any], dimensions: dict[str, Any]) -> dict[str, Any]:
    """构造日志查询过滤条件。

    按顺序构造日志查询的 addition 列表，先添加告警维度作为精确匹配条件，再添加策略过滤条件（排除已存在的维度 key）
    如果策略过滤条件中存在 OR 条件，则仅使用告警维度作为过滤条件（日志平台不支持 OR 条件）

    :param query_config: 告警策略查询配置
    :param dimensions: 已过滤的告警维度信息字典（仅包含有效维度字段）
    :return: 包含 addition 列表和 keyword 字符串的字典
    """
    addition: list[dict[str, Any]] = []
    added_dimension_keys: set[str] = set()

    # 先添加告警维度作为精确匹配条件
    for field, value in dimensions.items():
        addition.append(
            {
                "field": field,
                "operator": "=",
                "value": value if isinstance(value, list) else [value],
            }
        )
        added_dimension_keys.add(field)

    # 检查是否存在 or 条件，如果存在则仅使用告警维度
    agg_condition: list[dict[str, Any]] = query_config.get("agg_condition") or []
    has_or_condition: bool = any(cond.get("condition", "") == "or" for cond in agg_condition)
    if not has_or_condition:
        for condition in agg_condition:
            if condition["key"] in added_dimension_keys:
                continue

            # 转换操作符为日志平台格式，如果不支持则跳过该条件
            operator: str = condition.get("method") or "="
            log_operator: str | None = convert_operator_to_log_platform(operator)
            if log_operator is None:
                continue

            addition.append(
                {
                    "field": condition["key"],
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

    # 构建 key → 索引位置的映射，并处理操作符转换（事件检索页的不等于操作符为 ne）
    condition_index: dict[str, int] = {}
    for idx, condition in enumerate(filter_conditions):
        condition_index[condition["key"]] = idx
        if condition["method"] == "neq":
            condition["method"] = "ne"

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
