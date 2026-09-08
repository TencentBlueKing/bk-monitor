from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

from django.conf import settings

from apps.iam.backends.v4.config import resolve_effective_v4_system_id

# 模型基线目录：与 V3 的 support-files/iam/ 保持同一约定，文件按序号累加，历史文件不回改。
DEFAULT_MODEL_DIR = os.path.join("support-files", "iam", "v4")
# 当前生效的基线文件。新增编号文件后需要同步改这里，保证只有一个期望态。
CURRENT_MODEL_FILE = "0001_initial.json"

# V4 资源回调注册在独立路由上（见 apps/iam/urls.py 的 v4/resource/），不能复用 V3 的 resource/。
V4_RESOURCE_CALLBACK_PATH = "api/v1/iam/v4/resource/"

# IAM V4 对 system / resource_type / action / role 的 ID 使用同一套命名约束：
# 小写字母开头，只含小写字母、数字、下划线和连接符，最长 32 个字符。
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")

# 空字符串表示「与资源实例无关」，IAM V4 用它区分功能操作和资源操作。
NO_RESOURCE_TYPE = ""

# 以下 Action 存在于 BKLOG 的 ActionEnum，但按 IAM V4 模型基线（iWiki 4030598376）不注册到 V4。
# 新增 ActionEnum 成员时必须显式决定是否进入 V4 模型，否则一致性测试会失败。
ACTIONS_NOT_REGISTERED_IN_V4 = frozenset({"view_dashboard", "manage_dashboard"})


class ModelDefinitionError(ValueError):
    """模型基线不满足 IAM V4 的权限模型契约。"""


@dataclass(frozen=True, slots=True)
class SystemDefinition:
    id: str
    name: str
    description: str
    clients: tuple[str, ...]
    callback_url: str
    # None 表示管理员不由 as-code 托管，同步时既不下发也不比对，避免清空人工配置。
    managers: tuple[str, ...] | None


@dataclass(frozen=True, slots=True)
class ResourceTypeDefinition:
    id: str
    name: str
    ancestors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    id: str
    name: str
    resource_type_id: str


@dataclass(frozen=True, slots=True)
class RoleActionDefinition:
    id: str
    resource_type_id: str


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    id: str
    name: str
    description: str
    actions: tuple[RoleActionDefinition, ...]


@dataclass(frozen=True, slots=True)
class ModelDefinition:
    version: int
    system: SystemDefinition
    resource_types: tuple[ResourceTypeDefinition, ...]
    actions: tuple[ActionDefinition, ...]
    roles: tuple[RoleDefinition, ...]

    def resource_type_ids(self) -> tuple[str, ...]:
        return tuple(resource_type.id for resource_type in self.resource_types)

    def action_ids(self) -> tuple[str, ...]:
        return tuple(action.id for action in self.actions)

    def role_ids(self) -> tuple[str, ...]:
        return tuple(role.id for role in self.roles)


def resolve_model_file_path(file_name: str = CURRENT_MODEL_FILE) -> str:
    model_dir = str(getattr(settings, "BK_IAM_V4_MODEL_DIR", "") or "").strip()
    if not model_dir:
        model_dir = os.path.join(settings.BASE_DIR, DEFAULT_MODEL_DIR)
    return os.path.join(model_dir, file_name)


def load_model_payload(file_name: str = CURRENT_MODEL_FILE) -> dict[str, Any]:
    file_path = resolve_model_file_path(file_name)
    try:
        with open(file_path, encoding="utf-8") as model_file:
            payload = json.load(model_file)
    except FileNotFoundError as error:
        raise ModelDefinitionError(f"IAM V4 model baseline not found: {file_path}") from error
    except json.JSONDecodeError as error:
        raise ModelDefinitionError(f"IAM V4 model baseline is not valid JSON: {file_path}") from error

    if not isinstance(payload, dict):
        raise ModelDefinitionError("IAM V4 model baseline must be a JSON object")
    return payload


def resolve_callback_url() -> str:
    """V4 资源回调地址：优先显式配置，否则由资源回调 Host 拼出 V4 专用路径。"""
    explicit = str(getattr(settings, "BK_IAM_V4_CALLBACK_URL", "") or "").strip()
    if explicit:
        return explicit

    host = str(getattr(settings, "BK_IAM_RESOURCE_API_HOST", "") or "").strip()
    if not host:
        raise ModelDefinitionError(
            "IAM V4 callback url is not resolvable; set BK_IAM_V4_CALLBACK_URL or BK_IAM_RESOURCE_API_HOST"
        )
    return urljoin(host.rstrip("/") + "/", V4_RESOURCE_CALLBACK_PATH)


def resolve_model_managers() -> tuple[str, ...] | None:
    raw = getattr(settings, "BK_IAM_V4_MODEL_MANAGERS", "")
    if raw is None:
        return None
    if isinstance(raw, str):
        managers = [item.strip() for item in raw.split(",")]
    elif isinstance(raw, Iterable):
        managers = [str(item).strip() for item in raw]
    else:
        raise ModelDefinitionError(f"invalid BK_IAM_V4_MODEL_MANAGERS: {raw!r}")

    managers = [manager for manager in managers if manager]
    if not managers:
        return None
    return _dedupe(managers)


def build_model_definition(
    payload: Mapping[str, Any],
    *,
    system_id: str,
    callback_url: str,
    managers: Sequence[str] | None = None,
    extra_clients: Sequence[str] = (),
) -> ModelDefinition:
    """把基线文件内容与环境相关字段合成期望态，并做完整的契约校验。"""
    version = payload.get("version")
    if not isinstance(version, int) or version < 1:
        raise ModelDefinitionError("IAM V4 model baseline requires a positive integer version")

    system = _build_system(
        payload.get("system"),
        system_id=system_id,
        callback_url=callback_url,
        managers=managers,
        extra_clients=extra_clients,
    )
    resource_types = _build_resource_types(payload.get("resource_types"))
    actions = _build_actions(payload.get("actions"), resource_types=resource_types)
    roles = _build_roles(payload.get("roles"), resource_types=resource_types, actions=actions)

    return ModelDefinition(
        version=version,
        system=system,
        resource_types=resource_types,
        actions=actions,
        roles=roles,
    )


def load_model_definition(file_name: str = CURRENT_MODEL_FILE) -> ModelDefinition:
    """按当前 settings 加载期望态模型。"""
    return build_model_definition(
        load_model_payload(file_name),
        system_id=resolve_effective_v4_system_id(),
        callback_url=resolve_callback_url(),
        managers=resolve_model_managers(),
        extra_clients=[str(getattr(settings, "APP_CODE", "") or "").strip()],
    )


def _build_system(
    raw: Any,
    *,
    system_id: str,
    callback_url: str,
    managers: Sequence[str] | None,
    extra_clients: Sequence[str],
) -> SystemDefinition:
    if not isinstance(raw, Mapping):
        raise ModelDefinitionError("IAM V4 model baseline requires a system object")

    system_id = str(system_id or "").strip()
    _validate_id("system", system_id)

    name = _require_text(raw, "name", scope="system")
    callback_url = str(callback_url or "").strip()
    if not callback_url:
        raise ModelDefinitionError("IAM V4 system requires a non-empty callback_url")

    clients = _require_str_list(raw.get("clients"), scope="system.clients")
    # 调用方 app_code 必须在 clients 中，否则本应用调用 bkiam 会被拒绝。
    clients = _dedupe([*clients, *(str(client).strip() for client in extra_clients if str(client).strip())])
    if not clients:
        raise ModelDefinitionError("IAM V4 system requires at least one client")

    return SystemDefinition(
        id=system_id,
        name=name,
        description=str(raw.get("description") or ""),
        clients=clients,
        callback_url=callback_url,
        managers=_dedupe([str(manager).strip() for manager in managers]) if managers else None,
    )


def _build_resource_types(raw: Any) -> tuple[ResourceTypeDefinition, ...]:
    items = _require_list(raw, scope="resource_types")

    resource_types: list[ResourceTypeDefinition] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ModelDefinitionError(f"resource_types[{index}] must be an object")
        resource_type_id = str(item.get("id") or "").strip()
        _validate_id("resource_type", resource_type_id)
        if resource_type_id in seen:
            raise ModelDefinitionError(f"duplicate resource_type id: {resource_type_id}")
        seen.add(resource_type_id)

        ancestors = _require_str_list(item.get("ancestors", []), scope=f"resource_types[{resource_type_id}].ancestors")
        if resource_type_id in ancestors:
            raise ModelDefinitionError(f"resource_type {resource_type_id} cannot be its own ancestor")
        if len(set(ancestors)) != len(ancestors):
            raise ModelDefinitionError(f"resource_type {resource_type_id} has duplicate ancestors")

        resource_types.append(
            ResourceTypeDefinition(
                id=resource_type_id,
                name=_require_text(item, "name", scope=f"resource_types[{resource_type_id}]"),
                ancestors=ancestors,
            )
        )

    known = {resource_type.id for resource_type in resource_types}
    for resource_type in resource_types:
        unknown = [ancestor for ancestor in resource_type.ancestors if ancestor not in known]
        if unknown:
            raise ModelDefinitionError(f"resource_type {resource_type.id} refers to unknown ancestors: {unknown}")

    _reject_ancestor_cycles(tuple(resource_types))
    return tuple(resource_types)


def _reject_ancestor_cycles(resource_types: tuple[ResourceTypeDefinition, ...]) -> None:
    """祖先关系必须是有向无环的，否则注册顺序无解。"""
    pending = {resource_type.id: set(resource_type.ancestors) for resource_type in resource_types}
    resolved: set[str] = set()
    while pending:
        ready = {rt_id for rt_id, ancestors in pending.items() if ancestors <= resolved}
        if not ready:
            raise ModelDefinitionError(f"resource_type ancestors form a cycle: {sorted(pending)}")
        resolved |= ready
        pending = {rt_id: ancestors for rt_id, ancestors in pending.items() if rt_id not in ready}


def _build_actions(raw: Any, *, resource_types: tuple[ResourceTypeDefinition, ...]) -> tuple[ActionDefinition, ...]:
    items = _require_list(raw, scope="actions")
    known = {resource_type.id for resource_type in resource_types}

    actions: list[ActionDefinition] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ModelDefinitionError(f"actions[{index}] must be an object")
        action_id = str(item.get("id") or "").strip()
        _validate_id("action", action_id)
        if action_id in seen:
            raise ModelDefinitionError(f"duplicate action id: {action_id}")
        seen.add(action_id)

        resource_type_id = str(item.get("resource_type_id") or NO_RESOURCE_TYPE).strip()
        if resource_type_id != NO_RESOURCE_TYPE and resource_type_id not in known:
            raise ModelDefinitionError(f"action {action_id} refers to unknown resource_type: {resource_type_id}")

        actions.append(
            ActionDefinition(
                id=action_id,
                name=_require_text(item, "name", scope=f"actions[{action_id}]"),
                resource_type_id=resource_type_id,
            )
        )

    return tuple(actions)


def _build_roles(
    raw: Any,
    *,
    resource_types: tuple[ResourceTypeDefinition, ...],
    actions: tuple[ActionDefinition, ...],
) -> tuple[RoleDefinition, ...]:
    items = _require_list(raw, scope="roles")
    ancestors_by_type = {resource_type.id: set(resource_type.ancestors) for resource_type in resource_types}
    action_by_id = {action.id: action for action in actions}

    roles: list[RoleDefinition] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ModelDefinitionError(f"roles[{index}] must be an object")
        role_id = str(item.get("id") or "").strip()
        _validate_id("role", role_id)
        if role_id in seen:
            raise ModelDefinitionError(f"duplicate role id: {role_id}")
        seen.add(role_id)

        role_actions = _build_role_actions(
            item.get("actions"),
            role_id=role_id,
            action_by_id=action_by_id,
            ancestors_by_type=ancestors_by_type,
        )
        roles.append(
            RoleDefinition(
                id=role_id,
                name=_require_text(item, "name", scope=f"roles[{role_id}]"),
                description=str(item.get("description") or ""),
                actions=role_actions,
            )
        )

    return tuple(roles)


def _build_role_actions(
    raw: Any,
    *,
    role_id: str,
    action_by_id: Mapping[str, ActionDefinition],
    ancestors_by_type: Mapping[str, set[str]],
) -> tuple[RoleActionDefinition, ...]:
    items = _require_list(raw, scope=f"roles[{role_id}].actions")
    if not items:
        raise ModelDefinitionError(f"role {role_id} requires at least one action")

    role_actions: list[RoleActionDefinition] = []
    seen: set[str] = set()
    # IAM V4 要求同一角色内、同一资源类型的操作使用一致的授权维度。
    grant_dimension_by_action_resource: dict[str, str] = {}
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ModelDefinitionError(f"roles[{role_id}].actions[{index}] must be an object")
        action_id = str(item.get("id") or "").strip()
        action = action_by_id.get(action_id)
        if action is None:
            raise ModelDefinitionError(f"role {role_id} refers to unknown action: {action_id}")
        if action_id in seen:
            raise ModelDefinitionError(f"role {role_id} has duplicate action: {action_id}")
        seen.add(action_id)

        grant_dimension = str(item.get("resource_type_id") or NO_RESOURCE_TYPE).strip()
        _validate_grant_dimension(
            role_id=role_id,
            action=action,
            grant_dimension=grant_dimension,
            ancestors_by_type=ancestors_by_type,
        )

        expected = grant_dimension_by_action_resource.setdefault(action.resource_type_id, grant_dimension)
        if expected != grant_dimension:
            raise ModelDefinitionError(
                f"role {role_id} grants resource_type {action.resource_type_id!r} at inconsistent dimensions: "
                f"{expected!r} and {grant_dimension!r}"
            )

        role_actions.append(RoleActionDefinition(id=action_id, resource_type_id=grant_dimension))

    return tuple(role_actions)


def _validate_grant_dimension(
    *,
    role_id: str,
    action: ActionDefinition,
    grant_dimension: str,
    ancestors_by_type: Mapping[str, set[str]],
) -> None:
    if action.resource_type_id == NO_RESOURCE_TYPE:
        if grant_dimension != NO_RESOURCE_TYPE:
            raise ModelDefinitionError(
                f"role {role_id} must grant resource-free action {action.id} with an empty resource_type_id"
            )
        return

    if grant_dimension == NO_RESOURCE_TYPE:
        raise ModelDefinitionError(f"role {role_id} must grant action {action.id} on a resource_type")

    allowed = {action.resource_type_id, *ancestors_by_type.get(action.resource_type_id, set())}
    if grant_dimension not in allowed:
        raise ModelDefinitionError(
            f"role {role_id} grants action {action.id} at {grant_dimension!r}, "
            f"which is neither its resource_type nor an ancestor of it"
        )


def _validate_id(scope: str, value: str) -> None:
    if not ID_PATTERN.match(value):
        raise ModelDefinitionError(f"invalid {scope} id: {value!r}")


def _require_list(raw: Any, *, scope: str) -> list[Any]:
    if not isinstance(raw, list):
        raise ModelDefinitionError(f"{scope} must be a list")
    return raw


def _require_text(raw: Mapping[str, Any], key: str, *, scope: str) -> str:
    value = str(raw.get(key) or "").strip()
    if not value:
        raise ModelDefinitionError(f"{scope} requires a non-empty {key}")
    return value


def _require_str_list(raw: Any, *, scope: str) -> tuple[str, ...]:
    items = _require_list(raw, scope=scope)
    values = []
    for index, item in enumerate(items):
        value = str(item or "").strip()
        if not value:
            raise ModelDefinitionError(f"{scope}[{index}] must be a non-empty string")
        values.append(value)
    return tuple(values)


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))
