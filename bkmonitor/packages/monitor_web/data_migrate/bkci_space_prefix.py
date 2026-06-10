from __future__ import annotations

from copy import deepcopy
from typing import Any

from django.db import transaction
from django.db.models import Model, Q

from bkmonitor.models import BCSCluster
from metadata.config import DATABASE_CONNECTION_NAME
from metadata.models import (
    BkAppSpaceRecord,
    DataSource,
    Space,
    SpaceDataSource,
    SpaceRelatedStorageInfo,
    SpaceResource,
    SpaceStickyInfo,
    SpaceVMInfo,
    VMShortLinkRecord,
)
from metadata.models.record_rule.rules import RecordRule
from metadata.models.record_rule.v4 import RecordRuleV4, RecordRuleV4Flow
from metadata.models.space.constants import SPACE_UID_HYPHEN, SpaceTypes

BKCI_SPACE_TYPE = SpaceTypes.BKCI.value
BCS_RESOURCE_TYPE = SpaceTypes.BCS.value


MODEL_REGISTRY: dict[str, type[Model]] = {
    "metadata.Space": Space,
    "metadata.SpaceDataSource": SpaceDataSource,
    "metadata.SpaceResource": SpaceResource,
    "metadata.DataSource": DataSource,
    "metadata.SpaceStickyInfo": SpaceStickyInfo,
    "metadata.BkAppSpaceRecord": BkAppSpaceRecord,
    "metadata.SpaceRelatedStorageInfo": SpaceRelatedStorageInfo,
    "metadata.SpaceVMInfo": SpaceVMInfo,
    "metadata.VMShortLinkRecord": VMShortLinkRecord,
    "metadata.RecordRule": RecordRule,
    "metadata.RecordRuleV4": RecordRuleV4,
    "metadata.RecordRuleV4Flow": RecordRuleV4Flow,
    "bkmonitor.BCSCluster": BCSCluster,
}


def repair_bkci_space_id_prefix(
    bk_tenant_id: str,
    space_ids: list[str] | tuple[str, ...] | set[str] | None = None,
    dry_run: bool = True,
) -> list[dict[str, Any]]:
    """
    Add tenant prefix to legacy BKCI space IDs and related persisted references.

    Args:
        bk_tenant_id: Tenant ID used as project code prefix, for example ``tencent``.
        space_ids: Legacy unprefixed space IDs to repair. If omitted, all unprefixed
            BKCI spaces in the tenant are scanned.
        dry_run: When true, only return planned changes. When false, apply them and
            return the same change records with ``applied=True``.
    """
    prefix = _get_tenant_prefix(bk_tenant_id)
    old_space_ids = _get_old_space_ids(bk_tenant_id=bk_tenant_id, prefix=prefix, space_ids=space_ids)

    change_records: list[dict[str, Any]] = []
    for old_space_id in old_space_ids:
        new_space_id = f"{prefix}{old_space_id}"
        old_space_uid = _compose_space_uid(old_space_id)
        new_space_uid = _compose_space_uid(new_space_id)

        conflicts = _collect_conflicts(old_space_id=old_space_id, new_space_id=new_space_id)
        if conflicts:
            change_records.extend(conflicts)
            continue

        change_records.extend(
            _collect_change_records(
                bk_tenant_id=bk_tenant_id,
                old_space_id=old_space_id,
                new_space_id=new_space_id,
                old_space_uid=old_space_uid,
                new_space_uid=new_space_uid,
            )
        )

    if not dry_run:
        _apply_change_records(change_records)

    return _serialize_change_records(change_records)


def _get_tenant_prefix(bk_tenant_id: str) -> str:
    bk_tenant_id = (bk_tenant_id or "").strip()
    if not bk_tenant_id:
        raise ValueError("bk_tenant_id is required")
    return f"{bk_tenant_id}-"


def _get_old_space_ids(
    bk_tenant_id: str, prefix: str, space_ids: list[str] | tuple[str, ...] | set[str] | None = None
) -> list[str]:
    # 租户内所有未加前缀的 BKCI 旧 space_id，作为后续合法性校验的全集。
    existing_old_space_ids = set(
        Space.objects.filter(bk_tenant_id=bk_tenant_id, space_type_id=BKCI_SPACE_TYPE)
        .exclude(space_id__startswith=prefix)
        .values_list("space_id", flat=True)
    )

    if space_ids is not None:
        # 显式传入时，先做前缀归一化，再与租户内真实存在的旧 space_id 取交集。避免误传
        # 不属于该租户/不存在的 space_id 时，对 SpaceStickyInfo、BkAppSpaceRecord 等
        # 全局表造成跨租户、跨空间的错误改写。
        normalized_space_ids = {_normalize_old_space_id(space_id, prefix) for space_id in space_ids if space_id}
        return sorted(normalized_space_ids & existing_old_space_ids)

    return sorted(existing_old_space_ids)


def _normalize_old_space_id(space_id: str, prefix: str) -> str:
    space_id = str(space_id).strip()
    if space_id.startswith(prefix):
        return space_id[len(prefix) :]
    return space_id


def _compose_space_uid(space_id: str) -> str:
    return f"{BKCI_SPACE_TYPE}{SPACE_UID_HYPHEN}{space_id}"


def _collect_conflicts(old_space_id: str, new_space_id: str) -> list[dict[str, Any]]:
    old_space_uid = _compose_space_uid(old_space_id)
    new_space_uid = _compose_space_uid(new_space_id)
    conflicts: list[dict[str, Any]] = []

    target_space = Space.objects.filter(space_type_id=BKCI_SPACE_TYPE, space_id=new_space_id).first()
    if target_space:
        conflicts.append(
            _build_conflict_record(
                model_label="metadata.Space",
                table=Space._meta.db_table,
                pk=target_space.pk,
                old_space_id=old_space_id,
                new_space_id=new_space_id,
                reason="target space already exists",
            )
        )

    old_data_source_rows = SpaceDataSource.objects.filter(space_type_id=BKCI_SPACE_TYPE, space_id=old_space_id)
    target_data_ids = set(
        SpaceDataSource.objects.filter(space_type_id=BKCI_SPACE_TYPE, space_id=new_space_id).values_list(
            "bk_data_id", flat=True
        )
    )
    for row in old_data_source_rows:
        if row.bk_data_id in target_data_ids:
            conflicts.append(
                _build_conflict_record(
                    model_label="metadata.SpaceDataSource",
                    table=SpaceDataSource._meta.db_table,
                    pk=row.pk,
                    old_space_id=old_space_id,
                    new_space_id=new_space_id,
                    reason=f"target bk_data_id already exists: {row.bk_data_id}",
                )
            )

    for row in _iter_old_space_resource_rows(old_space_id):
        target_space_id = (
            new_space_id if row.space_type_id == BKCI_SPACE_TYPE and row.space_id == old_space_id else row.space_id
        )
        target_resource_id = (
            new_space_id
            if row.resource_type in {BKCI_SPACE_TYPE, BCS_RESOURCE_TYPE} and row.resource_id == old_space_id
            else row.resource_id
        )
        if (
            SpaceResource.objects.filter(
                space_type_id=row.space_type_id,
                space_id=target_space_id,
                resource_type=row.resource_type,
                resource_id=target_resource_id,
            )
            .exclude(pk=row.pk)
            .exists()
        ):
            conflicts.append(
                _build_conflict_record(
                    model_label="metadata.SpaceResource",
                    table=SpaceResource._meta.db_table,
                    pk=row.pk,
                    old_space_id=old_space_id,
                    new_space_id=new_space_id,
                    reason=(
                        "target space resource already exists: "
                        f"{row.space_type_id}/{target_space_id}/{row.resource_type}/{target_resource_id}"
                    ),
                )
            )

    for row in BkAppSpaceRecord.objects.filter(space_uid=old_space_uid):
        if BkAppSpaceRecord.objects.filter(bk_app_code=row.bk_app_code, space_uid=new_space_uid).exists():
            conflicts.append(
                _build_conflict_record(
                    model_label="metadata.BkAppSpaceRecord",
                    table=BkAppSpaceRecord._meta.db_table,
                    pk=row.pk,
                    old_space_id=old_space_id,
                    new_space_id=new_space_id,
                    reason=f"target app authorization already exists: {row.bk_app_code}",
                )
            )

    return conflicts


def _build_conflict_record(
    model_label: str, table: str, pk: Any, old_space_id: str, new_space_id: str, reason: str
) -> dict[str, Any]:
    return {
        "action": "conflict",
        "model": model_label,
        "table": table,
        "pk": pk,
        "old_space_id": old_space_id,
        "new_space_id": new_space_id,
        "reason": reason,
        "applied": False,
    }


def _collect_change_records(
    bk_tenant_id: str,
    old_space_id: str,
    new_space_id: str,
    old_space_uid: str,
    new_space_uid: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    records.extend(
        _collect_simple_field_changes(
            model_label="metadata.Space",
            queryset=Space.objects.filter(
                bk_tenant_id=bk_tenant_id,
                space_type_id=BKCI_SPACE_TYPE,
                space_id=old_space_id,
            ),
            changes={"space_id": new_space_id},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(
        _collect_simple_field_changes(
            model_label="metadata.SpaceDataSource",
            queryset=SpaceDataSource.objects.filter(space_type_id=BKCI_SPACE_TYPE, space_id=old_space_id),
            changes={"space_id": new_space_id},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(_collect_space_resource_changes(old_space_id=old_space_id, new_space_id=new_space_id))
    records.extend(
        _collect_simple_field_changes(
            model_label="metadata.DataSource",
            queryset=DataSource.objects.filter(bk_tenant_id=bk_tenant_id, space_uid=old_space_uid),
            changes={"space_uid": new_space_uid},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(
        _collect_simple_field_changes(
            model_label="bkmonitor.BCSCluster",
            queryset=BCSCluster.objects.filter(bk_tenant_id=bk_tenant_id, space_uid=old_space_uid),
            changes={"space_uid": new_space_uid},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(_collect_space_sticky_changes(old_space_id, new_space_id, old_space_uid, new_space_uid))
    records.extend(
        _collect_simple_field_changes(
            model_label="metadata.BkAppSpaceRecord",
            queryset=BkAppSpaceRecord.objects.filter(space_uid=old_space_uid),
            changes={"space_uid": new_space_uid},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(
        _collect_simple_field_changes(
            model_label="metadata.SpaceRelatedStorageInfo",
            queryset=SpaceRelatedStorageInfo.objects.filter(
                bk_tenant_id=bk_tenant_id, space_type_id=BKCI_SPACE_TYPE, space_id=old_space_id
            ),
            changes={"space_id": new_space_id},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(
        _collect_simple_field_changes(
            model_label="metadata.SpaceVMInfo",
            queryset=SpaceVMInfo.objects.filter(space_type=BKCI_SPACE_TYPE, space_id=old_space_id),
            changes={"space_id": new_space_id},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(
        _collect_simple_field_changes(
            model_label="metadata.VMShortLinkRecord",
            queryset=VMShortLinkRecord.objects.filter(
                bk_tenant_id=bk_tenant_id, space_type=BKCI_SPACE_TYPE, space_id=old_space_id
            ),
            changes={"space_id": new_space_id},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(
        _collect_simple_field_changes(
            model_label="metadata.RecordRule",
            queryset=RecordRule.objects.filter(
                bk_tenant_id=bk_tenant_id,
                space_type=BKCI_SPACE_TYPE,
                space_id=old_space_id,
            ),
            changes={"space_id": new_space_id},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(
        _collect_simple_field_changes(
            model_label="metadata.RecordRuleV4",
            queryset=RecordRuleV4.objects.filter(
                bk_tenant_id=bk_tenant_id, space_type=BKCI_SPACE_TYPE, space_id=old_space_id
            ),
            changes={"space_id": new_space_id},
            old_space_id=old_space_id,
            new_space_id=new_space_id,
        )
    )
    records.extend(_collect_record_rule_v4_flow_changes(old_space_id, new_space_id, old_space_uid, new_space_uid))

    return records


def _collect_simple_field_changes(
    model_label: str,
    queryset,
    changes: dict[str, Any],
    old_space_id: str,
    new_space_id: str,
) -> list[dict[str, Any]]:
    records = []
    for instance in queryset.order_by("pk"):
        field_changes = {}
        for field, new_value in changes.items():
            old_value = getattr(instance, field)
            if old_value == new_value:
                continue
            field_changes[field] = {"old": old_value, "new": new_value}
        if field_changes:
            records.append(
                _build_update_record(
                    model_label=model_label,
                    instance=instance,
                    changes=field_changes,
                    old_space_id=old_space_id,
                    new_space_id=new_space_id,
                )
            )
    return records


def _iter_old_space_resource_rows(old_space_id: str):
    return SpaceResource.objects.filter(
        Q(space_type_id=BKCI_SPACE_TYPE, space_id=old_space_id)
        | Q(resource_type__in=[BKCI_SPACE_TYPE, BCS_RESOURCE_TYPE], resource_id=old_space_id)
    ).order_by("pk")


def _collect_space_resource_changes(old_space_id: str, new_space_id: str) -> list[dict[str, Any]]:
    records = []
    for row in _iter_old_space_resource_rows(old_space_id):
        changes = {}
        if row.space_type_id == BKCI_SPACE_TYPE and row.space_id == old_space_id:
            changes["space_id"] = {"old": old_space_id, "new": new_space_id}
        if row.resource_type in {BKCI_SPACE_TYPE, BCS_RESOURCE_TYPE} and row.resource_id == old_space_id:
            changes["resource_id"] = {"old": old_space_id, "new": new_space_id}
        new_dimension_values = _replace_dimension_project_id(row.dimension_values, old_space_id, new_space_id)
        if new_dimension_values != row.dimension_values:
            changes["dimension_values"] = {"old": row.dimension_values, "new": new_dimension_values}
        if changes:
            records.append(
                _build_update_record(
                    model_label="metadata.SpaceResource",
                    instance=row,
                    changes=changes,
                    old_space_id=old_space_id,
                    new_space_id=new_space_id,
                )
            )
    return records


def _collect_space_sticky_changes(
    old_space_id: str, new_space_id: str, old_space_uid: str, new_space_uid: str
) -> list[dict[str, Any]]:
    records = []
    for row in SpaceStickyInfo.objects.all().order_by("pk"):
        new_value = _replace_json_value(row.space_uid_list, old_space_uid, new_space_uid)
        if new_value == row.space_uid_list:
            continue
        records.append(
            _build_update_record(
                model_label="metadata.SpaceStickyInfo",
                instance=row,
                changes={"space_uid_list": {"old": row.space_uid_list, "new": new_value}},
                old_space_id=old_space_id,
                new_space_id=new_space_id,
            )
        )
    return records


def _collect_record_rule_v4_flow_changes(
    old_space_id: str, new_space_id: str, old_space_uid: str, new_space_uid: str
) -> list[dict[str, Any]]:
    records = []
    queryset = RecordRuleV4Flow.objects.filter(
        rule__space_type=BKCI_SPACE_TYPE,
        rule__space_id=old_space_id,
    ).order_by("pk")
    for row in queryset:
        new_value = _replace_json_value(row.flow_config, old_space_uid, new_space_uid)
        if new_value == row.flow_config:
            continue
        records.append(
            _build_update_record(
                model_label="metadata.RecordRuleV4Flow",
                instance=row,
                changes={"flow_config": {"old": row.flow_config, "new": new_value}},
                old_space_id=old_space_id,
                new_space_id=new_space_id,
            )
        )
    return records


def _replace_dimension_project_id(value: Any, old_space_id: str, new_space_id: str) -> Any:
    """仅替换 ``dimension_values`` 中 ``project_id`` 键对应的旧 space_id。

    ``SpaceResource.dimension_values`` 通常是形如
    ``[{"project_id": "demo", "cluster_id": "BCS-K8S-1000", "namespace": ["demo", ...]}]``
    的列表。其中只有 ``project_id`` 才是 BKCI 的 space_id（项目 code），需要加上租户前缀；
    而 ``namespace``、``cluster_id`` 等字段的取值可能恰好等于项目 code（例如某些命名空间
    与项目同名），若做全量递归替换会把这些无关字段一起改写，破坏资源维度数据。因此这里只
    针对 ``project_id`` 键、且值精确等于 ``old_space_id`` 时才替换。

    Args:
        value: 原始 ``dimension_values``，一般是 ``list[dict]``，也兼容其他结构原样返回。
        old_space_id: 旧的（未加前缀）BKCI space_id。
        new_space_id: 新的（带租户前缀）BKCI space_id。

    Returns:
        替换后的 ``dimension_values``，不会修改入参对象。
    """
    if isinstance(value, list):
        return [_replace_dimension_project_id(item, old_space_id, new_space_id) for item in value]
    if isinstance(value, dict):
        new_dict: dict[Any, Any] = {}
        for key, item in value.items():
            if key == "project_id" and item == old_space_id:
                new_dict[key] = new_space_id
            else:
                new_dict[key] = item
        return new_dict
    return value


def _replace_json_value(value: Any, old_value: str, new_value: str) -> Any:
    if isinstance(value, str):
        return new_value if value == old_value else value
    if isinstance(value, list):
        return [_replace_json_value(item, old_value, new_value) for item in value]
    if isinstance(value, dict):
        return {key: _replace_json_value(item, old_value, new_value) for key, item in value.items()}
    return value


def _build_update_record(
    model_label: str,
    instance: Model,
    changes: dict[str, dict[str, Any]],
    old_space_id: str,
    new_space_id: str,
) -> dict[str, Any]:
    return {
        "action": "update",
        "model": model_label,
        "table": instance._meta.db_table,
        "pk": instance.pk,
        "old_space_id": old_space_id,
        "new_space_id": new_space_id,
        "changes": changes,
        "applied": False,
    }


def _apply_change_records(change_records: list[dict[str, Any]]) -> None:
    """在单个事务内应用全部更新记录。

    所有更新共享同一个事务，任意一条写入失败都会整体回滚。由于 ``applied`` 标记是
    在内存对象上逐条写入的，一旦事务回滚，必须把本次已标记为成功的记录回写为失败，
    否则调用方在捕获异常后读到的报告会与数据库实际状态不一致（"假成功"）。

    Args:
        change_records: ``_collect_change_records`` 产出的变更记录列表，函数会就地更新
            其中 ``action == "update"`` 记录的 ``applied`` / ``stale`` 等状态字段。

    Raises:
        Exception: 透传底层数据库异常（如唯一约束冲突）。抛出前会把本批已标记成功的
            记录回写为 ``applied=False`` 并附带 ``error`` 字段。
    """
    update_records = [record for record in change_records if record.get("action") == "update"]
    if not update_records:
        return

    # 记录本事务内已写入成功的记录，便于回滚时统一回写状态。
    applied_in_txn: list[dict[str, Any]] = []
    try:
        # 显式指定 metadata 所在的后台数据库连接，避免在 default 连接非 metadata 库的
        # 进程（如 SaaS 侧）中 select_for_update 落在错误连接上导致事务失效。
        with transaction.atomic(using=DATABASE_CONNECTION_NAME):
            for record in update_records:
                model = MODEL_REGISTRY[record["model"]]
                instance = model.objects.select_for_update().get(pk=record["pk"])
                update_fields = []
                for field, change in record["changes"].items():
                    current_value = getattr(instance, field)
                    if current_value != change["old"]:
                        record["applied"] = False
                        record["stale"] = True
                        record["current_value"] = current_value
                        break
                    setattr(instance, field, change["new"])
                    update_fields.append(field)
                else:
                    instance.save(update_fields=update_fields)
                    record["applied"] = True
                    applied_in_txn.append(record)
    except Exception as exc:
        # 事务已整体回滚，把内存中误标为成功的记录回写为失败，保证报告与 DB 一致。
        for record in applied_in_txn:
            record["applied"] = False
            record["error"] = str(exc)
        raise


def _serialize_change_records(change_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [deepcopy(record) for record in change_records]
