from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from django.apps import apps
from django.core import serializers
from django.db import DEFAULT_DB_ALIAS, connections, router, transaction
from django.db.models import Max, Model, QuerySet

ModelType = type[Model] | str
MYSQL_AUTO_INCREMENT_REGEX = re.compile(r"\bAUTO_INCREMENT=(\d+)\b")


def read_json_file(file_path: str | Path, encoding: str = "utf-8") -> Any:
    """读取 JSON 文件并返回反序列化后的对象。"""
    return json.loads(Path(file_path).read_text(encoding=encoding))


def write_json_file(file_path: str | Path, payload: Any, encoding: str = "utf-8") -> Path:
    """将对象按 JSON 格式写入文件。"""
    target_file_path = Path(file_path)
    target_file_path.parent.mkdir(parents=True, exist_ok=True)
    target_file_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding=encoding,
    )
    return target_file_path


def _resolve_model(model: ModelType) -> type[Model]:
    """将 ``app_label.ModelName`` 或模型类解析为 Django 模型类。"""
    if isinstance(model, str):
        if "." not in model:
            raise ValueError("model 必须是 Django 模型类，或形如 'app_label.ModelName' 的字符串")
        app_label, model_name = model.split(".", 1)
        return apps.get_model(app_label, model_name)
    return model


def _resolve_using(model_cls: type[Model], using: str | None = None, for_write: bool = False) -> str:
    """
    自动推断模型对应的数据库别名。

    优先级：
    1. 调用方显式传入的 using
    2. Django router 的读/写路由结果
    3. 默认 manager 当前绑定的数据库
    4. default
    """
    if using:
        return using

    route_using = router.db_for_write(model_cls) if for_write else router.db_for_read(model_cls)
    if route_using:
        return route_using

    return model_cls._default_manager.db or DEFAULT_DB_ALIAS


def _build_export_queryset(
    model: ModelType,
    filters: dict[str, Any] | None = None,
    exclude: dict[str, Any] | None = None,
    order_by: Sequence[str] | None = None,
    using: str | None = None,
) -> QuerySet:
    # 导出前固定走 ORM 查询构建，避免调用侧自己处理排序和过滤细节。
    model_cls = _resolve_model(model)
    resolved_using = _resolve_using(model_cls, using=using, for_write=False)
    queryset = model_cls.objects.using(resolved_using).all()
    if filters:
        queryset = queryset.filter(**filters)
    if exclude:
        queryset = queryset.exclude(**exclude)
    return queryset.order_by(*(order_by or ("pk",)))


def _serialize_instances(
    instances: QuerySet | Iterable[Model],
    format: str = "json",
    use_natural_foreign_keys: bool = False,
    use_natural_primary_keys: bool = False,
    indent: int = 2,
    stream: Any | None = None,
) -> str | None:
    """导出 ORM 实例，保留主键和字段原值。"""
    return serializers.serialize(
        format,
        instances,
        use_natural_foreign_keys=use_natural_foreign_keys,
        use_natural_primary_keys=use_natural_primary_keys,
        indent=indent,
        stream=stream,
    )


def _is_auto_increment_pk(model_cls: type[Model]) -> bool:
    """仅识别 Django 默认自增主键类型。"""
    return model_cls._meta.pk.get_internal_type() in {"AutoField", "BigAutoField", "SmallAutoField"}


def _get_next_pk_by_max(model_cls: type[Model], using: str | None = None) -> int:
    """
    使用 ``MAX(pk) + 1`` 作为兜底结果。

    这个值不一定等于底层 sequence/AUTO_INCREMENT 的真实当前位置，
    但在数据库不方便读取元信息时，至少能得到一个可用的起始点。
    """
    resolved_using = _resolve_using(model_cls, using=using, for_write=False)
    pk_name = model_cls._meta.pk.attname
    max_pk = model_cls.objects.using(resolved_using).aggregate(max_pk=Max(pk_name))["max_pk"]
    return 1 if max_pk is None else max_pk + 1


def _quote_qualified_name(connection, name: str) -> str:
    """为 ``schema.table`` 或 ``schema.sequence`` 这种名字逐段加引号。"""
    return ".".join(connection.ops.quote_name(part) for part in name.split("."))


def _get_auto_increment_start_from_metadata(model_cls: type[Model], using: str | None = None) -> int | None:
    """
    优先从数据库元信息中读取当前自增起始点。

    不同数据库的实现差异较大，这里只覆盖常见后端；
    取不到时返回 ``None``，由调用方回退到 ``MAX(pk) + 1``。
    """
    resolved_using = _resolve_using(model_cls, using=using, for_write=False)
    connection = connections[resolved_using]
    table_name = model_cls._meta.db_table
    pk_column = model_cls._meta.pk.column

    with connection.cursor() as cursor:
        if connection.vendor == "mysql":
            quoted_table_name = _quote_qualified_name(connection, table_name)
            cursor.execute(f"SHOW CREATE TABLE {quoted_table_name}")
            row = cursor.fetchone()
            if not row or len(row) < 2 or not row[1]:
                return None
            match = MYSQL_AUTO_INCREMENT_REGEX.search(str(row[1]))
            return int(match.group(1)) if match else None

        if connection.vendor == "sqlite":
            cursor.execute("SELECT seq FROM sqlite_sequence WHERE name = %s", [table_name])
            row = cursor.fetchone()
            return 1 if not row or row[0] is None else row[0] + 1

        if connection.vendor == "postgresql":
            cursor.execute("SELECT pg_get_serial_sequence(%s, %s)", [table_name, pk_column])
            row = cursor.fetchone()
            if not row or not row[0]:
                return None

            sequence_name = row[0]
            cursor.execute(f"SELECT last_value, is_called FROM {_quote_qualified_name(connection, sequence_name)}")
            seq_row = cursor.fetchone()
            if not seq_row:
                return None

            last_value, is_called = seq_row
            return last_value + 1 if is_called else last_value

    return None


def _get_reserved_auto_increment_start(current_start: int) -> int:
    """
    基于当前自增游标计算带预留区间的新起点。

    规则：
    - 原游标小于 10000，则预留 10000 个 ID
    - 原游标大于等于 10000，则直接翻倍
    """
    if current_start < 10000:
        return current_start + 10000
    return current_start * 2


def _set_auto_increment_start_in_db(model_cls: type[Model], start: int, using: str | None = None) -> int:
    """将数据库自增游标设置为指定起点，返回最终设置值。"""
    resolved_using = _resolve_using(model_cls, using=using, for_write=True)
    connection = connections[resolved_using]
    table_name = model_cls._meta.db_table
    pk_column = model_cls._meta.pk.column

    with connection.cursor() as cursor:
        if connection.vendor == "mysql":
            quoted_table_name = _quote_qualified_name(connection, table_name)
            cursor.execute(f"ALTER TABLE {quoted_table_name} AUTO_INCREMENT = %s", [start])
            return start

        if connection.vendor == "sqlite":
            # sqlite_sequence 里保存的是“最近一次已使用”的值，因此要写 start - 1。
            cursor.execute("UPDATE sqlite_sequence SET seq = %s WHERE name = %s", [start - 1, table_name])
            if cursor.rowcount == 0:
                cursor.execute("INSERT INTO sqlite_sequence(name, seq) VALUES (%s, %s)", [table_name, start - 1])
            return start

        if connection.vendor == "postgresql":
            cursor.execute("SELECT pg_get_serial_sequence(%s, %s)", [table_name, pk_column])
            row = cursor.fetchone()
            if not row or not row[0]:
                raise ValueError(f"{table_name}.{pk_column} 没有关联可设置的 sequence")

            cursor.execute("SELECT setval(%s, %s, false)", [row[0], start])
            return start

    raise NotImplementedError(f"暂不支持数据库类型: {connection.vendor}")


def get_auto_increment_start(model: ModelType, using: str | None = None) -> int | None:
    """
    获取模型当前数据库中的自增主键起始点。

    仅当模型主键是 ``AutoField`` / ``BigAutoField`` / ``SmallAutoField`` 时返回值，
    否则返回 ``None``。优先读取数据库维护的真实自增位置，失败时退化为
    ``MAX(pk) + 1``，用于数据迁移场景下的 ID 偏移计算。
    """
    model_cls = _resolve_model(model)
    if not _is_auto_increment_pk(model_cls):
        return None

    return _get_auto_increment_start_from_metadata(model_cls, using) or _get_next_pk_by_max(model_cls, using)


def reset_auto_increment_start(model: ModelType, start: int | None = None, using: str | None = None) -> int | None:
    """
    重置模型的自增游标，并自动追加预留区间。

    最终设置值取以下两者的较大值：
    - 调用方显式传入的 ``start``（若有）
    - 基于数据库当前游标计算出的预留起点

    这样既能保证游标至少推进到迁移需要的位置，又能为后续二次导入保留安全区间。
    """
    model_cls = _resolve_model(model)
    if not _is_auto_increment_pk(model_cls):
        return None

    current_start = get_auto_increment_start(model_cls, using=using)
    if current_start is None:
        return None

    reserved_start = _get_reserved_auto_increment_start(current_start)
    target_start = reserved_start if start is None else start
    final_start = max(target_start, reserved_start)
    return _set_auto_increment_start_in_db(model_cls, final_start, using)


def export_model_data(
    model: ModelType,
    filters: dict[str, Any] | None = None,
    exclude: dict[str, Any] | None = None,
    order_by: Sequence[str] | None = None,
    using: str | None = None,
    format: str = "python",
    use_natural_foreign_keys: bool = False,
    use_natural_primary_keys: bool = False,
    indent: int = 2,
) -> str:
    """
    将模型数据导出为 Django fixture 文本。

    这里直接复用 Django 官方序列化能力，不手工拼字段字典，
    这样可以保持主键、字段值和外键表达方式与 ORM 默认行为一致。
    """
    queryset = _build_export_queryset(
        model=model,
        filters=filters,
        exclude=exclude,
        order_by=order_by,
        using=using,
    )
    payload = _serialize_instances(
        queryset,
        format=format,
        use_natural_foreign_keys=use_natural_foreign_keys,
        use_natural_primary_keys=use_natural_primary_keys,
        indent=indent,
    )
    return payload or ""


def export_model_to_file(
    file_path: str | Path,
    model: ModelType,
    filters: dict[str, Any] | None = None,
    exclude: dict[str, Any] | None = None,
    order_by: Sequence[str] | None = None,
    using: str | None = None,
    format: str = "json",
    use_natural_foreign_keys: bool = False,
    use_natural_primary_keys: bool = False,
    indent: int = 2,
    encoding: str = "utf-8",
) -> Path:
    """将导出的 fixture 文本落盘到指定文件"""
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    payload = export_model_data(
        model=model,
        filters=filters,
        exclude=exclude,
        order_by=order_by,
        using=using,
        format=format,
        use_natural_foreign_keys=use_natural_foreign_keys,
        use_natural_primary_keys=use_natural_primary_keys,
        indent=indent,
    )
    file_path.write_text(payload, encoding=encoding)
    return file_path


def _deserialize_data(
    payload: str,
    format: str,
    using: str | None = None,
    ignorenonexistent: bool = False,
    handle_forward_references: bool = True,
):
    # 反序列化结果是 DeserializedObject，后续直接调用 save()
    # 即可按 Django fixture 语义完成插入或更新。
    deserialize_kwargs = {
        "ignorenonexistent": ignorenonexistent,
        "handle_forward_references": handle_forward_references,
    }
    if using is not None:
        deserialize_kwargs["using"] = using
    return serializers.deserialize(format, payload, **deserialize_kwargs)


def import_model_data(
    payload: str,
    format: str = "python",
    using: str | None = None,
    ignorenonexistent: bool = False,
    handle_forward_references: bool = True,
    save: bool = True,
    atomic: bool = True,
) -> list[Model]:
    """
    导入 fixture 文本并按 ORM 语义写回数据库。

    反序列化后保留实例主键，调用 ``DeserializedObject.save()`` 时，
    Django 会按照主键状态执行新增或更新，从而实现“原样导入”。

    format: python/json/xml/yaml/jsonl
    """
    objects = list(
        _deserialize_data(
            payload,
            format=format,
            using=using,
            ignorenonexistent=ignorenonexistent,
            handle_forward_references=handle_forward_references,
        )
    )
    if not save:
        return [item.object for item in objects]

    def _save() -> list[Model]:
        saved_objects: list[Model] = []
        for item in objects:
            # 逐条保存而不是 bulk_create/bulk_update，原因是需要保留
            # Django fixture 的默认保存语义，包括主键、信号和字段清洗。
            if using is None:
                item.save()
            else:
                item.save(using=using)
            saved_objects.append(item.object)
        return saved_objects

    if atomic:
        # 默认整批导入包裹在同一个事务里，防止部分成功造成脏数据。
        # 当 using 未显式指定时，让 Django 自己按路由保存对象，
        # 此时无法保证跨库使用同一个事务，只包裹当前默认连接。
        with transaction.atomic(using=using or DEFAULT_DB_ALIAS):
            return _save()
    return _save()


def import_model_from_file(
    file_path: str | Path,
    format: str = "json",
    using: str | None = None,
    ignorenonexistent: bool = False,
    handle_forward_references: bool = True,
    save: bool = True,
    atomic: bool = True,
    encoding: str = "utf-8",
) -> list[Model]:
    """从文件读取 fixture 文本并导入数据库。"""
    payload = Path(file_path).read_text(encoding=encoding)
    return import_model_data(
        payload,
        format=format,
        using=using,
        ignorenonexistent=ignorenonexistent,
        handle_forward_references=handle_forward_references,
        save=save,
        atomic=atomic,
    )
