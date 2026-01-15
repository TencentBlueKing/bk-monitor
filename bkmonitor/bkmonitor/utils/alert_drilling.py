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


def merge_dimensions_into_conditions(
    agg_condition: list[dict[str, Any]] | None,
    dimensions: dict[str, Any],
    dimension_fields: list[str],
) -> list[dict[str, Any]]:
    """合并维度信息到初始过滤条件中。

    将维度信息合并到初始过滤条件中，用于告警下钻时构建查询过滤条件。
    如果维度已存在于初始条件中，则用维度值覆盖；如果维度不存在于初始条件中，则添加为新的过滤条件。

    :param agg_condition: 初始过滤条件列表
    :param dimensions: 维度信息字典
    :param dimension_fields: 有效维度字段列表
    :return: 合并后的过滤条件列表
    """
    # 使用告警策略配置的汇聚条件作为初始过滤条件
    filter_conditions: list[dict[str, Any]] = agg_condition or []

    # 构建 key → 索引位置的映射，方便后续更新替换
    condition_index: dict[str, int] = {condition["key"]: idx for idx, condition in enumerate(filter_conditions)}

    # 遍历告警的原始维度信息，增加维度过滤条件
    for key, value in dimensions.items():
        if key not in dimension_fields or value is None:
            continue

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
