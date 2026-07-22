"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# Issue title construction and source classification helpers.

TITLE_SOURCE_DEFAULT = "default"
TITLE_SOURCE_SYSTEM = "system"
TITLE_SOURCE_USER = "user"
TITLE_SOURCE_UNKNOWN = "unknown"

_NAME_DIM_VALUE_MAX_LEN = 40


def build_issue_default_name(strategy_name: str, dimension_values: dict, is_regression: bool) -> str:
    """生成 Issue 默认名称。

    格式：``[回归] {strategy_name} - {v1} | {v2}``（dimension_values 非空时追加 value 后缀）。
    维度值按 key 排序，单值过长时截断，保证创建与后续资格检查使用同一确定性口径。
    """
    base = f"[回归] {strategy_name}" if is_regression else strategy_name
    if not dimension_values:
        return base

    parts = []
    for key in sorted(dimension_values.keys()):
        value = str(dimension_values[key])
        if len(value) > _NAME_DIM_VALUE_MAX_LEN:
            value = value[: _NAME_DIM_VALUE_MAX_LEN - 3] + "..."
        parts.append(value)
    return f"{base} - {' | '.join(parts)}"


def classify_issue_title_source(current_name: str, default_name: str, latest_operator: str | None) -> str:
    """Classify whether the current title is default, system-managed, or user-managed.

    A user NAME_CHANGE remains authoritative even if the user changed the title
    back to the generated default value.
    """
    if latest_operator is not None and latest_operator != "system":
        return TITLE_SOURCE_USER if latest_operator else TITLE_SOURCE_UNKNOWN
    if current_name == default_name:
        return TITLE_SOURCE_DEFAULT
    if latest_operator == "system":
        return TITLE_SOURCE_SYSTEM
    return TITLE_SOURCE_UNKNOWN
