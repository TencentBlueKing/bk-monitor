"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from metadata.models.data_source import DataSource
    from metadata.models.result_table import ResultTable


@dataclass
class DatabusLabelContext:
    """Databus 标签生成上下文。

    Attributes:
        data_source: 监控侧数据源实例，可为 None。
        result_table: 监控侧结果表实例，可为 None。
        table_id: 监控侧结果表 ID；当未直接传入 result_table 时可据此解析。
        bk_tenant_id: 租户 ID。
        bk_data_id: 数据源 ID；当未直接传入 data_source 时可据此解析。
        extra_labels: 调用方显式传入的额外标签，最终合并时优先级最高（但仍低于系统保留键）。
    """

    data_source: DataSource | None = None
    result_table: ResultTable | None = None
    table_id: str | None = None
    bk_tenant_id: str | None = None
    bk_data_id: int | None = None
    extra_labels: dict[str, Any] | None = field(default=None)
