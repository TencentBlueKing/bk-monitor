"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from functools import wraps
from typing import Any
from collections.abc import Callable

from monitor_web.custom_report.constants import UNGROUP_SCOPE_NAME, DEFAULT_FIELD_SCOPE


def scope_prefix_handler(
    input_field: str | list[str] | None = None,
    output_field: str | list[str] | None = None,
):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, params: dict[str, Any]) -> Any:
            scope_prefix = params.get("scope_prefix", "")
            if not scope_prefix:
                return func(self, params)

            if input_field:
                _process_paths(params, scope_prefix, input_field, add=True)

            result = func(self, params)

            if result and output_field:
                _process_paths(result, scope_prefix, output_field, add=False)

            return result

        return wrapper

    return decorator


def _process_paths(data: Any, prefix: str, paths: str | list[str], add: bool):
    """处理多个路径"""
    for path in [paths] if isinstance(paths, str) else paths:
        _process_path(data, prefix, path.split("."), add)


def _process_path(data: Any, prefix: str, parts: list[str], add: bool):
    """处理单个路径"""
    if not parts or not data:
        return

    # 处理列表
    if isinstance(data, list):
        for item in data:
            _process_path(item, prefix, parts, add)
        return

    if not isinstance(data, dict):
        return

    key = parts[0]
    if key not in data:
        return

    # 最后一层：处理字符串值
    if len(parts) == 1:
        if isinstance(data[key], str):
            data[key] = f"{prefix}{data[key]}" if add else data[key].removeprefix(prefix)
    else:
        _process_path(data[key], prefix, parts[1:], add)


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
