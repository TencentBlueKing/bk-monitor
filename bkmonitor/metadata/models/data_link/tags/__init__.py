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

import logging
from typing import TYPE_CHECKING, Any

from metadata.models.data_link.tags.context import DatabusLabelContext
from metadata.models.data_link.tags.generators import register_default_generators
from metadata.models.data_link.tags.protocol import DatabusLabelGenerator
from metadata.models.data_link.tags.registry import DatabusLabelRegistry

if TYPE_CHECKING:
    from metadata.models.data_source import DataSource
    from metadata.models.result_table import ResultTable

logger = logging.getLogger("metadata")

# 系统保留标签：始终由链路配置层写入，不允许被扩展生成器覆盖
RESERVED_DATABUS_LABEL_KEYS = frozenset({"bk_biz_id"})

_registry = DatabusLabelRegistry()
register_default_generators(_registry)


def get_databus_label_registry() -> DatabusLabelRegistry:
    """获取全局 Databus 标签生成器注册表。"""
    return _registry


def build_databus_labels(
    *,
    data_source: DataSource | None = None,
    result_table: ResultTable | None = None,
    table_id: str | None = None,
    bk_tenant_id: str | None = None,
    bk_data_id: int | None = None,
    extra_labels: dict[str, Any] | None = None,
) -> dict[str, str]:
    """构建 Databus metadata.labels 的扩展标签。

    会尽量从传入参数解析 DataSource / ResultTable，再交给注册表中的生成器推导标签。
    注意：本函数不包含系统保留键 ``bk_biz_id``，该键由 ``DataBusConfig`` 在最终组装时强制写入。

    Args:
        data_source: 数据源实例。
        result_table: 结果表实例。
        table_id: 结果表 ID；未传 result_table 时可据此查询。
        bk_tenant_id: 租户 ID。
        bk_data_id: 数据源 ID；未传 data_source 时可据此查询。
        extra_labels: 额外标签，优先级高于生成器产出。

    Returns:
        扩展标签字典（不含系统保留键）。
    """
    resolved_data_source = _resolve_data_source(
        data_source=data_source,
        bk_data_id=bk_data_id,
        bk_tenant_id=bk_tenant_id,
    )
    resolved_result_table = _resolve_result_table(
        result_table=result_table,
        table_id=table_id,
        bk_tenant_id=bk_tenant_id,
    )
    resolved_table_id = table_id or getattr(resolved_result_table, "table_id", None)
    resolved_bk_data_id = bk_data_id
    if resolved_bk_data_id is None and resolved_data_source is not None:
        resolved_bk_data_id = resolved_data_source.bk_data_id

    context = DatabusLabelContext(
        data_source=resolved_data_source,
        result_table=resolved_result_table,
        table_id=resolved_table_id,
        bk_tenant_id=bk_tenant_id,
        bk_data_id=resolved_bk_data_id,
        extra_labels=extra_labels,
    )
    labels = _registry.build(context)
    for reserved_key in RESERVED_DATABUS_LABEL_KEYS:
        labels.pop(reserved_key, None)
    return labels


def _resolve_data_source(
    *,
    data_source: DataSource | None,
    bk_data_id: int | None,
    bk_tenant_id: str | None,
) -> DataSource | None:
    """解析 DataSource；显式传入时优先使用。"""
    if data_source is not None:
        return data_source
    if not bk_data_id:
        return None

    from metadata.models import DataSource

    queryset = DataSource.objects.filter(bk_data_id=bk_data_id)
    if bk_tenant_id:
        queryset = queryset.filter(bk_tenant_id=bk_tenant_id)
    try:
        return queryset.get()
    except DataSource.DoesNotExist:
        logger.debug(
            "build_databus_labels: data_source not found, bk_data_id->[%s], bk_tenant_id->[%s]",
            bk_data_id,
            bk_tenant_id,
        )
        return None
    except DataSource.MultipleObjectsReturned:
        logger.warning(
            "build_databus_labels: multiple data_source found, bk_data_id->[%s], bk_tenant_id->[%s]",
            bk_data_id,
            bk_tenant_id,
        )
        return queryset.first()


def _resolve_result_table(
    *,
    result_table: ResultTable | None,
    table_id: str | None,
    bk_tenant_id: str | None,
) -> ResultTable | None:
    """解析 ResultTable；显式传入时优先使用。"""
    if result_table is not None:
        return result_table
    if not table_id:
        return None

    from metadata.models import ResultTable

    queryset = ResultTable.objects.filter(table_id=table_id)
    if bk_tenant_id:
        queryset = queryset.filter(bk_tenant_id=bk_tenant_id)
    try:
        return queryset.get()
    except ResultTable.DoesNotExist:
        logger.debug(
            "build_databus_labels: result_table not found, table_id->[%s], bk_tenant_id->[%s]",
            table_id,
            bk_tenant_id,
        )
        return None
    except ResultTable.MultipleObjectsReturned:
        logger.warning(
            "build_databus_labels: multiple result_table found, table_id->[%s], bk_tenant_id->[%s]",
            table_id,
            bk_tenant_id,
        )
        return queryset.first()


__all__ = [
    "RESERVED_DATABUS_LABEL_KEYS",
    "DatabusLabelContext",
    "DatabusLabelGenerator",
    "DatabusLabelRegistry",
    "build_databus_labels",
    "get_databus_label_registry",
]
