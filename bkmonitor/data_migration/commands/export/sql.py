"""导出 SQL 逻辑

实现要点:
    - 使用 raw SQL 导出，避免 ORM 层字段转换开销
    - 使用主键游标分页（`WHERE pk > last_pk ORDER BY pk LIMIT N`）降低大表导出时的内存压力
    - 支持 RowTransformer 批次处理，通过 TablePipeline 进行变换与过滤
    - 支持通过 `EXPORT_SQL_FILTER_MAPPING` 为指定表追加 WHERE 条件片段，用于导出阶段数据过滤
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from django.apps import apps
from django.db import connection
from django.db.models import Model

from ...config import EXPORT_SQL_FILTER_MAPPING
from ...utils.types import ExportBatch
from ..handle.handle import TablePipeline, get_table_pipeline

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 1000


@dataclass
class ExportOrmDataStats:
    """ORM 导出过程统计信息。

    Attributes:
        dropped_rows: 被 RowTransformer 丢弃的行数（返回 None 的数量）。
    """

    dropped_rows: int = 0


def get_export_sql_filter(model_label: str) -> str | None:
    """获取导出 SQL 过滤条件片段

    Args:
        model_label: 模型标签（app_label.ModelName）

    Returns:
        过滤条件片段（不包含 WHERE），为空或未配置返回 None

    Raises:
        ValueError: 配置包含 WHERE 关键字（避免重复拼接导致语法错误）
    """

    where = EXPORT_SQL_FILTER_MAPPING.get(model_label)
    if where is None:
        return None
    where = where.strip()
    if not where:
        return None
    # 约定 value 为“条件片段”，不应包含 WHERE
    if where.lower().startswith("where "):
        raise ValueError(f"EXPORT_SQL_FILTER_MAPPING[{model_label!r}] 不应包含 WHERE 关键字")
    return where


def export_orm_data(
    model_label: str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    stats: ExportOrmDataStats | None = None,
    apply_pipeline: bool = True,
) -> Iterator[ExportBatch]:
    """按批导出 ORM 数据"""
    model = apps.get_model(model_label)
    if model is None:
        raise LookupError(f"未找到模型: {model_label}")
    fields = _resolve_export_fields(model)
    pipeline = get_table_pipeline(model_label) if apply_pipeline else None

    pk_field = model._meta.pk
    if pk_field is None:
        raise ValueError(f"模型 {model_label} 未配置主键")

    pk_name = pk_field.name
    pk_column = pk_field.column
    table_name = model._meta.db_table
    quoted = connection.ops.quote_name

    select_columns = ", ".join(f"{quoted(field.column)} AS {quoted(field.name)}" for field in fields)
    pk_column_sql = quoted(pk_column)
    table_sql = quoted(table_name)
    export_where = get_export_sql_filter(model_label)

    last_pk: Any | None = None
    while True:
        if last_pk is None:
            if export_where:
                sql = (
                    f"SELECT {select_columns} FROM {table_sql} "
                    f"WHERE ({export_where}) "
                    f"ORDER BY {pk_column_sql} ASC LIMIT %s"
                )
            else:
                sql = f"SELECT {select_columns} FROM {table_sql} ORDER BY {pk_column_sql} ASC LIMIT %s"
            params = [batch_size]
        else:
            if export_where:
                sql = (
                    f"SELECT {select_columns} FROM {table_sql} "
                    f"WHERE ({export_where}) AND {pk_column_sql} > %s "
                    f"ORDER BY {pk_column_sql} ASC LIMIT %s"
                )
            else:
                sql = (
                    f"SELECT {select_columns} FROM {table_sql} "
                    f"WHERE {pk_column_sql} > %s "
                    f"ORDER BY {pk_column_sql} ASC LIMIT %s"
                )
            params = [last_pk, batch_size]

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            if not rows:
                break
            if cursor.description is None:
                raise RuntimeError(f"模型 {model_label} 返回空的字段描述")
            columns = [desc[0] for desc in cursor.description]
            pk_index = columns.index(pk_name)
            last_pk = rows[-1][pk_index]
            batch = [dict(zip(columns, row)) for row in rows]

        if pipeline:
            processed_rows, batch_drop_rows_count = _apply_pipeline(batch, pipeline, model_label)
            if stats is not None:
                stats.dropped_rows += batch_drop_rows_count
            yield processed_rows
        else:
            yield batch


def _apply_pipeline(
    rows: ExportBatch,
    pipeline: TablePipeline,
    model_label: str,
) -> tuple[ExportBatch, int]:
    """使用 pipeline 处理数据批次

    Args:
        rows: 输入行列表
        pipeline: 表级处理管道
        model_label: 模型标签（app_label.ModelName）

    Returns:
        (处理后的行列表, 被过滤的行数)
    """
    try:
        processed_rows, drop_rows_count = pipeline.process_batch(rows, model_label)
        if drop_rows_count > 0:
            logger.debug("Pipeline 过滤了 %d 行数据: %s", drop_rows_count, model_label)
        return processed_rows, drop_rows_count
    except Exception:
        logger.exception("Pipeline 处理失败: %s", model_label)
        # 处理失败时返回原数据，不丢弃
        return rows, 0


def _resolve_export_fields(model: type[Model]) -> list[Any]:
    """解析导出字段"""
    pk_field = model._meta.pk
    if pk_field is None:
        raise ValueError(f"模型 {model._meta.label} 未配置主键")

    fields = list(model._meta.concrete_fields)
    if pk_field not in fields:
        fields.insert(0, pk_field)
    return fields
