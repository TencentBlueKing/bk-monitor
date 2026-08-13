from __future__ import annotations

import logging
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from django.conf import settings

from apps.iam.backends.v4.gateway import resolve_v4_gateway_url
from apps.iam.backends.v4.model_client import V4ModelClient
from apps.iam.backends.v4.model_definition import (
    CURRENT_MODEL_FILE,
    ActionDefinition,
    ModelDefinition,
    ResourceTypeDefinition,
    RoleDefinition,
    load_model_definition,
)

logger = logging.getLogger("iam.v4.model_migrator")


class ModelMigrationBlocked(RuntimeError):
    """收敛计划包含无法自动执行的变更，必须人工处理。"""


@dataclass(frozen=True, slots=True)
class ActualModel:
    """IAM V4 侧的实际态；system 为 None 表示系统尚未注册。"""

    system: dict[str, Any] | None = None
    resource_types: tuple[dict[str, Any], ...] = ()
    actions: tuple[dict[str, Any], ...] = ()
    roles: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class ModelMigrationPlan:
    create_system: dict[str, Any] | None = None
    update_system: dict[str, Any] | None = None
    create_resource_types: tuple[dict[str, Any], ...] = ()
    update_resource_types: tuple[tuple[str, dict[str, Any]], ...] = ()
    create_actions: tuple[dict[str, Any], ...] = ()
    update_actions: tuple[tuple[str, dict[str, Any]], ...] = ()
    create_roles: tuple[dict[str, Any], ...] = ()
    update_roles: tuple[tuple[str, dict[str, Any]], ...] = ()
    add_role_actions: tuple[tuple[str, tuple[dict[str, Any], ...]], ...] = ()
    remove_role_actions: tuple[tuple[str, tuple[str, ...]], ...] = ()
    # 无法自动收敛、必须人工处理的变更。存在 blocking 时不允许 apply。
    blocking: tuple[str, ...] = ()
    # IAM 侧存在但基线中没有的对象。只报告，不删除。
    drift: tuple[str, ...] = ()

    def has_changes(self) -> bool:
        return any(
            (
                self.create_system,
                self.update_system,
                self.create_resource_types,
                self.update_resource_types,
                self.create_actions,
                self.update_actions,
                self.create_roles,
                self.update_roles,
                self.add_role_actions,
                self.remove_role_actions,
            )
        )

    def describe(self) -> str:
        lines: list[str] = []
        if self.create_system:
            lines.append(f"create system: {self.create_system.get('name')}")
        if self.update_system:
            lines.append(f"update system: {sorted(self.update_system)}")
        for item in self.create_resource_types:
            lines.append(f"create resource_type: {item['id']} (ancestors={item.get('ancestors', [])})")
        for resource_type_id, payload in self.update_resource_types:
            lines.append(f"update resource_type: {resource_type_id} -> {payload}")
        for item in self.create_actions:
            lines.append(f"create action: {item['id']} (resource_type_id={item.get('resource_type_id', '')!r})")
        for action_id, payload in self.update_actions:
            lines.append(f"update action: {action_id} -> {payload}")
        for item in self.create_roles:
            lines.append(f"create role: {item['id']} ({len(item.get('actions', []))} actions)")
        for role_id, payload in self.update_roles:
            lines.append(f"update role: {role_id} -> {payload}")
        for role_id, action_ids in self.remove_role_actions:
            lines.append(f"remove role actions: {role_id} -> {list(action_ids)}")
        for role_id, actions in self.add_role_actions:
            lines.append(f"add role actions: {role_id} -> {[action['id'] for action in actions]}")
        for reason in self.blocking:
            lines.append(f"BLOCKING: {reason}")
        for reason in self.drift:
            lines.append(f"DRIFT: {reason}")
        return "\n".join(lines) if lines else "no changes"


def build_plan(desired: ModelDefinition, actual: ActualModel) -> ModelMigrationPlan:
    """比较期望态与实际态，产出幂等收敛计划。相同输入必须得到相同计划。"""
    blocking: list[str] = []
    drift: list[str] = []

    create_system, update_system = _diff_system(desired, actual.system)
    create_resource_types, update_resource_types = _diff_resource_types(desired, actual, drift)
    create_actions, update_actions = _diff_actions(desired, actual, blocking, drift)
    create_roles, update_roles, add_role_actions, remove_role_actions = _diff_roles(desired, actual, drift)

    return ModelMigrationPlan(
        create_system=create_system,
        update_system=update_system,
        create_resource_types=create_resource_types,
        update_resource_types=update_resource_types,
        create_actions=create_actions,
        update_actions=update_actions,
        create_roles=create_roles,
        update_roles=update_roles,
        add_role_actions=add_role_actions,
        remove_role_actions=remove_role_actions,
        blocking=tuple(blocking),
        drift=tuple(drift),
    )


def _diff_system(
    desired: ModelDefinition, actual: Mapping[str, Any] | None
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    system = desired.system
    payload: dict[str, Any] = {
        "name": system.name,
        "description": system.description,
        "clients": list(system.clients),
        "callback_url": system.callback_url,
    }
    if system.managers is not None:
        payload["managers"] = list(system.managers)

    if actual is None:
        return payload, None

    changed = {
        key: value
        for key, value in payload.items()
        # clients / managers 是覆盖式更新，只要集合等价就不必重写，避免顺序差异触发无谓调用。
        if not _values_equal(actual.get(key), value)
    }
    return None, changed or None


def _diff_resource_types(
    desired: ModelDefinition, actual: ActualModel, drift: list[str]
) -> tuple[tuple[dict[str, Any], ...], tuple[tuple[str, dict[str, Any]], ...]]:
    actual_by_id = {str(item.get("id")): item for item in actual.resource_types}
    desired_ids = set(desired.resource_type_ids())

    creates: list[ResourceTypeDefinition] = []
    updates: list[tuple[str, dict[str, Any]]] = []
    for resource_type in desired.resource_types:
        current = actual_by_id.get(resource_type.id)
        if current is None:
            creates.append(resource_type)
            continue
        changed: dict[str, Any] = {}
        if str(current.get("name") or "") != resource_type.name:
            changed["name"] = resource_type.name
        if tuple(str(item) for item in current.get("ancestors") or ()) != resource_type.ancestors:
            changed["ancestors"] = list(resource_type.ancestors)
        if changed:
            updates.append((resource_type.id, changed))

    for resource_type_id in actual_by_id:
        if resource_type_id not in desired_ids:
            drift.append(f"resource_type {resource_type_id} exists in IAM but not in the baseline")

    ordered = _order_by_ancestors(creates)
    return tuple(_resource_type_payload(item) for item in ordered), tuple(updates)


def _diff_actions(
    desired: ModelDefinition, actual: ActualModel, blocking: list[str], drift: list[str]
) -> tuple[tuple[dict[str, Any], ...], tuple[tuple[str, dict[str, Any]], ...]]:
    actual_by_id = {str(item.get("id")): item for item in actual.actions}
    desired_ids = set(desired.action_ids())

    creates: list[dict[str, Any]] = []
    updates: list[tuple[str, dict[str, Any]]] = []
    for action in desired.actions:
        current = actual_by_id.get(action.id)
        if current is None:
            creates.append(_action_payload(action))
            continue

        current_resource_type = str(current.get("resource_type_id") or "")
        if current_resource_type != action.resource_type_id:
            # update_action 只支持改名；换绑资源类型必须先删 action，而删除又要求它没有绑定角色。
            blocking.append(
                f"action {action.id} is bound to resource_type {current_resource_type!r} in IAM but "
                f"{action.resource_type_id!r} in the baseline; rebinding requires manual delete and recreate"
            )
            continue

        if str(current.get("name") or "") != action.name:
            updates.append((action.id, {"name": action.name}))

    for action_id in actual_by_id:
        if action_id not in desired_ids:
            drift.append(f"action {action_id} exists in IAM but not in the baseline")

    return tuple(creates), tuple(updates)


def _diff_roles(
    desired: ModelDefinition, actual: ActualModel, drift: list[str]
) -> tuple[
    tuple[dict[str, Any], ...],
    tuple[tuple[str, dict[str, Any]], ...],
    tuple[tuple[str, tuple[dict[str, Any], ...]], ...],
    tuple[tuple[str, tuple[str, ...]], ...],
]:
    actual_by_id = {str(item.get("id")): item for item in actual.roles}
    desired_ids = set(desired.role_ids())

    creates: list[dict[str, Any]] = []
    updates: list[tuple[str, dict[str, Any]]] = []
    add_actions: list[tuple[str, tuple[dict[str, Any], ...]]] = []
    remove_actions: list[tuple[str, tuple[str, ...]]] = []

    for role in desired.roles:
        current = actual_by_id.get(role.id)
        if current is None:
            creates.append(_role_payload(role))
            continue

        changed: dict[str, Any] = {}
        if str(current.get("name") or "") != role.name:
            changed["name"] = role.name
        if str(current.get("description") or "") != role.description:
            changed["description"] = role.description
        if changed:
            updates.append((role.id, changed))

        to_add, to_remove = _diff_role_actions(role, current.get("actions"))
        if to_remove:
            remove_actions.append((role.id, to_remove))
        if to_add:
            add_actions.append((role.id, to_add))

    for role_id in actual_by_id:
        if role_id not in desired_ids:
            drift.append(f"role {role_id} exists in IAM but not in the baseline")

    return tuple(creates), tuple(updates), tuple(add_actions), tuple(remove_actions)


def _diff_role_actions(role: RoleDefinition, actual_actions: Any) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    current = {
        str(item.get("id")): str(item.get("resource_type_id") or "")
        for item in (actual_actions or [])
        if isinstance(item, Mapping)
    }
    expected = {action.id: action.resource_type_id for action in role.actions}

    to_add: list[dict[str, Any]] = []
    to_remove: list[str] = []
    for action in role.actions:
        if action.id not in current:
            to_add.append({"id": action.id, "resource_type_id": action.resource_type_id})
        elif current[action.id] != action.resource_type_id:
            # 授权维度变了只能先摘掉再挂上；apply 里保证 remove 先于 add 执行。
            to_remove.append(action.id)
            to_add.append({"id": action.id, "resource_type_id": action.resource_type_id})

    to_remove.extend(action_id for action_id in current if action_id not in expected)
    return tuple(to_add), tuple(dict.fromkeys(to_remove))


def _order_by_ancestors(resource_types: Sequence[ResourceTypeDefinition]) -> list[ResourceTypeDefinition]:
    """新建资源类型必须让祖先先落地；已存在于 IAM 的祖先不参与排序。"""
    pending = list(resource_types)
    pending_ids = {resource_type.id for resource_type in pending}
    ordered: list[ResourceTypeDefinition] = []
    placed: set[str] = set()
    while pending:
        ready = [
            resource_type
            for resource_type in pending
            if all(ancestor in placed for ancestor in resource_type.ancestors if ancestor in pending_ids)
        ]
        if not ready:
            # model_definition 已拒绝环，这里兜底避免死循环。
            raise ModelMigrationBlocked(f"cannot order resource types: {[item.id for item in pending]}")
        ordered.extend(ready)
        placed |= {resource_type.id for resource_type in ready}
        ready_ids = {resource_type.id for resource_type in ready}
        pending = [resource_type for resource_type in pending if resource_type.id not in ready_ids]
    return ordered


def _resource_type_payload(resource_type: ResourceTypeDefinition) -> dict[str, Any]:
    return {"id": resource_type.id, "name": resource_type.name, "ancestors": list(resource_type.ancestors)}


def _action_payload(action: ActionDefinition) -> dict[str, Any]:
    return {"id": action.id, "name": action.name, "resource_type_id": action.resource_type_id}


def _role_payload(role: RoleDefinition) -> dict[str, Any]:
    return {
        "id": role.id,
        "name": role.name,
        "description": role.description,
        "actions": [{"id": action.id, "resource_type_id": action.resource_type_id} for action in role.actions],
    }


def _values_equal(actual: Any, desired: Any) -> bool:
    if isinstance(desired, list):
        return isinstance(actual, list | tuple) and set(str(item) for item in actual) == set(
            str(item) for item in desired
        )
    return str(actual or "") == str(desired or "")


class V4ModelMigrator:
    """把仓库中的模型基线幂等收敛到 IAM V4。"""

    def __init__(self, client: V4ModelClient, desired: ModelDefinition) -> None:
        self.client = client
        self.desired = desired

    @classmethod
    def from_settings(
        cls,
        *,
        bk_tenant_id: str,
        username: str = "admin",
        file_name: str = CURRENT_MODEL_FILE,
    ) -> V4ModelMigrator:
        return cls(
            client=V4ModelClient.from_settings(username=username, bk_tenant_id=bk_tenant_id),
            desired=load_model_definition(file_name),
        )

    def fetch_actual(self) -> ActualModel:
        system = self.client.retrieve_system()
        if system is None:
            # 系统还没注册，子资源接口必然 404，没必要再拉。
            return ActualModel()
        return ActualModel(
            system=system,
            resource_types=tuple(self.client.list_resource_types()),
            actions=tuple(self.client.list_actions()),
            roles=tuple(self.client.list_roles()),
        )

    def plan(self) -> ModelMigrationPlan:
        return build_plan(self.desired, self.fetch_actual())

    def apply(self, plan: ModelMigrationPlan) -> None:
        if plan.blocking:
            raise ModelMigrationBlocked("; ".join(plan.blocking))

        if plan.create_system:
            self.client.create_system(plan.create_system)
        elif plan.update_system:
            self.client.update_system(plan.update_system)

        if plan.create_resource_types:
            self.client.batch_create_resource_types(plan.create_resource_types)
        for resource_type_id, payload in plan.update_resource_types:
            self.client.update_resource_type(resource_type_id, payload)

        if plan.create_actions:
            self.client.batch_create_actions(plan.create_actions)
        for action_id, payload in plan.update_actions:
            self.client.update_action(action_id, payload)

        if plan.create_roles:
            self.client.batch_create_roles(plan.create_roles)
        for role_id, payload in plan.update_roles:
            self.client.update_role(role_id, payload)
        # 先摘后挂：授权维度变更依赖这个顺序。
        for role_id, action_ids in plan.remove_role_actions:
            self.client.batch_delete_role_actions(role_id, action_ids)
        for role_id, actions in plan.add_role_actions:
            self.client.batch_create_role_actions(role_id, actions)

    def migrate(self, *, dry_run: bool = True) -> ModelMigrationPlan:
        plan = self.plan()
        if dry_run:
            logger.info("IAM V4 model dry-run plan for system=%s:\n%s", self.desired.system.id, plan.describe())
            return plan

        if plan.drift:
            logger.warning("IAM V4 model drift for system=%s: %s", self.desired.system.id, list(plan.drift))
        if not plan.has_changes():
            logger.info("IAM V4 model for system=%s is already up to date", self.desired.system.id)
            return plan

        logger.info("IAM V4 model applying plan for system=%s:\n%s", self.desired.system.id, plan.describe())
        self.apply(plan)
        return plan


def is_auto_migration_enabled() -> bool:
    """自动同步只在显式打开开关、且 V4 网关已配置时生效。"""
    if not getattr(settings, "BK_IAM_V4_MODEL_MIGRATE_ENABLED", False):
        return False
    if not resolve_v4_gateway_url():
        logger.warning("IAM V4 model auto migration is enabled but BKAPP_IAM_V4_API_BASE_URL is not configured")
        return False
    return True


def migrate_v4_model_on_post_migrate() -> ModelMigrationPlan | None:
    """post_migrate 钩子入口：只在真正执行 migrate 时运行，且不能打断部署。"""
    if "migrate" not in sys.argv:
        return None
    if not is_auto_migration_enabled():
        return None

    try:
        migrator = V4ModelMigrator.from_settings(bk_tenant_id=settings.BK_APP_TENANT_ID)
        return migrator.migrate(dry_run=False)
    except Exception:  # pylint: disable=broad-except
        # 权限模型同步失败不应阻断数据库迁移和发布，留给 iam_v4_migrate_model 命令重跑。
        logger.exception("IAM V4 model migration failed; rerun `manage.py iam_v4_migrate_model --apply` to converge")
        return None
