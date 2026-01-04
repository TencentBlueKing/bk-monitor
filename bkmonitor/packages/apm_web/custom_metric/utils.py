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

from monitor_web.custom_report.constants import UNGROUP_SCOPE_NAME, DEFAULT_FIELD_SCOPE


def remove_scope_prefix(
    items: list[dict[str, Any]], scope_prefix: str, scope_key: str | None = "scope"
) -> list[dict[str, Any]]:
    """
    去掉 scope.name 中的前缀

    :param items: 需要处理的数据列表
    :param scope_prefix: scope 前缀
    :param scope_key: scope 字段的键名，默认为 "scope"，对于直接包含 name 的情况传 None
    :return: 去掉前缀后的数据列表
    """
    for item in items:
        if scope_key:
            # 处理嵌套的 scope.name 结构（如 dimensions, metrics）
            scope_name = item.get(scope_key, {}).get("name", "")
            if scope_name.startswith(scope_prefix):
                item[scope_key]["name"] = scope_name[len(scope_prefix) :]
        else:
            # 处理直接的 name 字段（如 scopes 列表）
            scope_name = item.get("name", "")
            if scope_name.startswith(scope_prefix):
                item["name"] = scope_name[len(scope_prefix) :]
    return items


class ScopeNamePrefixMixin:
    def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
        validated_data = super().to_internal_value(data)  # type: ignore[misc]

        scope_prefix = validated_data.get("scope_prefix")
        if scope_prefix and "name" in validated_data:
            validated_data["name"] = f"{scope_prefix}{validated_data['name']}"

        return validated_data


class ScopeQueryFilterMixin:
    """提供基于 scope_prefix 的查询过滤器"""

    def get_query_scope_filters(self, params: dict) -> dict[str, str]:
        """返回基于 scope_prefix 的查询过滤器"""
        return {"scope_name": params["scope_prefix"]}


class DefaultScopeNameMixin:
    """提供默认 scope_name 的生成方法"""

    def get_default_scope_name(self, params: dict[str, Any]) -> str:
        """返回默认的 scope_name（带前缀的 UNGROUP_SCOPE_NAME）"""
        return params["scope_prefix"] + UNGROUP_SCOPE_NAME


class DefaultFieldScopeMixin:
    """提供默认字段 scope 的判断方法"""

    def is_default_field_scope(self, field_scope: str, params: dict) -> bool:
        """判断是否为默认字段 scope"""
        return field_scope == params["scope_prefix"] + DEFAULT_FIELD_SCOPE
