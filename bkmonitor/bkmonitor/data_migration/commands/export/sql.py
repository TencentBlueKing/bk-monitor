"""导出 SQL 逻辑

实现要点:
    - 使用 raw SQL 导出，避免 ORM 层字段转换开销
    - 使用主键游标分页（`WHERE pk > last_pk ORDER BY pk LIMIT N`）降低大表导出时的内存压力
    - 支持 RowHandlerFn 逐行处理，返回 None 表示丢弃该行
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any

from django.apps import apps
from django.db import connection
from django.db.models import Model

from .handler import TABLE_HANDLER_MAPPING
from ...utils.types import ExportBatch, RowDict, RowHandlerFn

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 1000


def set_table_handler_mapping(mapping: dict[str, list[RowHandlerFn]]) -> None:
    """设置表级别 Handler 映射表"""
    TABLE_HANDLER_MAPPING.clear()
    TABLE_HANDLER_MAPPING.update(mapping)


def get_model_row_handlers(model_label: str) -> list[RowHandlerFn]:
    """获取模型 Row Handler"""
    # key="*" 的 handlers 会被追加到每张表 handlers 的最后执行
    handlers: list[RowHandlerFn] = []
    handlers.extend(TABLE_HANDLER_MAPPING.get(model_label, []))
    handlers.extend(TABLE_HANDLER_MAPPING.get("*", []))
    return handlers


def export_orm_data(model_label: str, batch_size: int = DEFAULT_BATCH_SIZE) -> Iterator[ExportBatch]:
    """按批导出 ORM 数据"""
    model = apps.get_model(model_label)
    if model is None:
        raise LookupError(f"未找到模型: {model_label}")
    fields = _resolve_export_fields(model)
    handlers = get_model_row_handlers(model_label)

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

    last_pk: Any | None = None
    while True:
        if last_pk is None:
            sql = f"SELECT {select_columns} FROM {table_sql} ORDER BY {pk_column_sql} ASC LIMIT %s"
            params = [batch_size]
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

        yield apply_row_handlers(batch, handlers, model_label)


def apply_row_handlers(rows: ExportBatch, handlers: list[RowHandlerFn], model_label: str) -> ExportBatch:
    """顺序执行 Row Handler"""
    if not handlers:
        return rows
    processed_rows: list[RowDict] = []
    for row in rows:
        try:
            current_row = row
            for handler in handlers:
                current_row = handler(current_row)
                if current_row is None:
                    break
            if current_row is None:
                logger.warning("Handler 丢弃数据，已跳过: %s (%s)", model_label, row)
                continue
            processed_rows.append(current_row)
        except Exception:
            logger.exception("Handler 处理失败，已跳过行: %s (%s)", model_label, row)
    return processed_rows


def _resolve_export_fields(model: type[Model]) -> list[Any]:
    """解析导出字段"""
    pk_field = model._meta.pk
    if pk_field is None:
        raise ValueError(f"模型 {model._meta.label} 未配置主键")

    fields = list(model._meta.concrete_fields)
    if pk_field not in fields:
        fields.insert(0, pk_field)
    return fields
