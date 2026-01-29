"""导入 SQL 逻辑

实现要点:
    - 使用 raw SQL 写入，避免 ORM 层字段转换开销
    - 冲突策略:
      - update: 使用 MySQL `ON DUPLICATE KEY UPDATE` 执行 UPSERT（兼容 MySQL 5.7）
      - skip: 预先查询已存在唯一键集合，仅插入不存在的数据
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, Literal

from django.apps import apps
from django.db import connection, transaction
from django.db.models import Model, UniqueConstraint

from bkmonitor.data_migration.utils.types import ImportStats, RowDict

DEFAULT_BATCH_SIZE = 1000


def import_orm_data(
    model_label: str,
    rows: Iterable[RowDict],
    conflict_strategy: Literal["update", "skip"],
    batch_size: int = DEFAULT_BATCH_SIZE,
    dry_run: bool = False,
) -> ImportStats:
    """按批导入 ORM 数据"""
    model = apps.get_model(model_label)
    if model is None:
        raise LookupError(f"未找到模型: {model_label}")

    unique_keys = _resolve_unique_keys(model)
    if not unique_keys:
        raise ValueError(f"模型 {model_label} 未配置 unique_keys")

    stats = ImportStats()
    rows_list = list(rows)
    if not rows_list:
        return stats

    field_names = _resolve_import_fields(model, rows_list)
    _validate_unique_keys(field_names, unique_keys, model_label)
    field_columns = _field_columns_by_name(model, field_names)

    for batch in _iter_batches(rows_list, batch_size):
        stats.total += len(batch)
        existing_keys = fetch_existing_keys(model, unique_keys, batch)
        if conflict_strategy == "skip":
            insert_rows = [row for row in batch if _row_key(row, unique_keys) not in existing_keys]
            stats.skipped += len(batch) - len(insert_rows)
            stats.inserted += len(insert_rows)
            if dry_run or not insert_rows:
                continue
            _bulk_insert(model, field_columns, field_names, insert_rows)
            continue

        stats.updated += len(existing_keys)
        stats.inserted += len(batch) - len(existing_keys)
        if dry_run:
            continue
        _bulk_upsert(model, field_columns, field_names, batch)

    return stats


def fetch_existing_keys(model: type[Model], unique_keys: list[str], rows: list[RowDict]) -> set[tuple[Any, ...]]:
    """读取已存在唯一键集合"""
    if not rows:
        return set()
    table_name = model._meta.db_table
    quoted = connection.ops.quote_name
    field_columns = _field_columns_by_name(model, unique_keys)
    values = [_row_key(row, unique_keys) for row in rows]
    if len(unique_keys) == 1:
        placeholders = ", ".join(["%s"] * len(values))
        sql = (
            f"SELECT {quoted(field_columns[0])} FROM {quoted(table_name)} "
            f"WHERE {quoted(field_columns[0])} IN ({placeholders})"
        )
        params = [value[0] for value in values]
    else:
        row_placeholder = "(" + ", ".join(["%s"] * len(unique_keys)) + ")"
        placeholders = ", ".join([row_placeholder] * len(values))
        columns_sql = ", ".join(quoted(col) for col in field_columns)
        sql = f"SELECT {columns_sql} FROM {quoted(table_name)} WHERE ({columns_sql}) IN ({placeholders})"
        params: list[Any] = []
        for value in values:
            params.extend(value)
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return set(tuple(row) for row in cursor.fetchall())


def _bulk_insert(
    model: type[Model],
    field_columns: list[str],
    field_names: list[str],
    rows: list[RowDict],
) -> None:
    """批量插入数据"""
    if not rows:
        return
    quoted = connection.ops.quote_name
    columns_sql = ", ".join(quoted(col) for col in field_columns)
    placeholders = ", ".join(["%s"] * len(field_columns))
    sql = f"INSERT INTO {quoted(model._meta.db_table)} ({columns_sql}) VALUES ({placeholders})"
    values = [_row_values(row, field_names) for row in rows]
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.executemany(sql, values)


def _bulk_upsert(
    model: type[Model],
    field_columns: list[str],
    field_names: list[str],
    rows: list[RowDict],
) -> None:
    """批量 UPSERT 数据"""
    if not rows:
        return
    quoted = connection.ops.quote_name
    columns_sql = ", ".join(quoted(col) for col in field_columns)
    placeholders = ", ".join(["%s"] * len(field_columns))
    update_sql = ", ".join(f"{quoted(col)}=VALUES({quoted(col)})" for col in field_columns)
    sql = (
        f"INSERT INTO {quoted(model._meta.db_table)} ({columns_sql}) "
        f"VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {update_sql}"
    )
    values = [_row_values(row, field_names) for row in rows]
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.executemany(sql, values)


def _resolve_unique_keys(model: type[Model]) -> list[str]:
    """从模型定义解析唯一键"""
    if model._meta.unique_together:
        return list(model._meta.unique_together[0])
    constraints = [
        constraint
        for constraint in model._meta.constraints
        if isinstance(constraint, UniqueConstraint) and constraint.fields
    ]
    if constraints:
        return list(constraints[0].fields)
    if model._meta.pk is None:
        raise ValueError(f"模型 {model._meta.label} 未配置主键")
    return [model._meta.pk.name]


def _resolve_import_fields(model: type[Model], rows: list[RowDict]) -> list[str]:
    """解析导入字段"""
    if rows:
        return list(rows[0].keys())
    return [field.name for field in model._meta.concrete_fields]


def _field_columns_by_name(model: type[Model], field_names: list[str]) -> list[str]:
    """将字段名转为列名"""
    return [model._meta.get_field(field_name).column for field_name in field_names]


def _iter_batches(rows: list[RowDict], batch_size: int) -> Iterator[list[RowDict]]:
    """按批次切分数据"""
    for index in range(0, len(rows), batch_size):
        yield rows[index : index + batch_size]


def _row_values(row: RowDict, field_names: list[str]) -> list[Any]:
    """按顺序取行数据"""
    return [row.get(field_name) for field_name in field_names]


def _row_key(row: RowDict, unique_keys: list[str]) -> tuple[Any, ...]:
    """构造唯一键值"""
    return tuple(row.get(key) for key in unique_keys)


def _validate_unique_keys(field_names: list[str], unique_keys: list[str], model_label: str) -> None:
    """校验唯一键是否存在"""
    missing = [key for key in unique_keys if key not in field_names]
    if missing:
        raise ValueError(f"模型 {model_label} 缺少唯一键字段: {missing}")
