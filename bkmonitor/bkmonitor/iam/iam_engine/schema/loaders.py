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

# ---------------------------------------------------------------------------
# Schema Loaders —— 从各种来源加载定义到 SchemaRegistry
#
# 目前提供两种来源：
#   - load_from_class(cls)   :  以 Python 类作命名空间的 DSL（推荐）
#   - load_from_dict(data)   :  以字典（未来可对接 YAML / JSON / DB）
#
# 加载器不做校验，只做"把定义塞进 registry"；完整性校验统一在 registry.freeze() 里做。
# 这样保证：无论从哪里加载，最终都过同一个校验闸门。
# ---------------------------------------------------------------------------

from collections.abc import Iterable, Mapping
from typing import Any

from bkmonitor.iam.iam_engine.core.exceptions import SchemaError
from bkmonitor.iam.iam_engine.schema.definitions import (
    ActionDef,
    ResourceTypeDef,
    RoleActionBinding,
    RoleDef,
    SystemDef,
)
from bkmonitor.iam.iam_engine.schema.registry import SchemaRegistry


# ---- 从 Python 类加载 ------------------------------------------------------


def load_from_class(registry: SchemaRegistry, container: type) -> int:
    """扫描类的属性，按类型自动注册到 registry。

    这是"类作命名空间"的 DSL 用法：

        class Actions:
            VIEW_BUSINESS = ActionDef(id="view_business", name="业务查看",
                                       resource_type="space")
            MANAGE_RULE   = ActionDef(id="manage_rule", name="策略管理",
                                       resource_type="space")

        load_from_class(registry, Actions)   # 自动把两个 ActionDef 注册进去

    注意：
      - 只扫描类的直接属性（vars(cls)），不递归继承链
      - 支持一个类里混合 ActionDef / ResourceTypeDef / RoleDef / SystemDef
      - 私有属性（以 "_" 开头）跳过

    Args:
        registry: 目标注册表（尚未 freeze）
        container: 承载定义的类

    Returns:
        实际注册的条目数
    """
    count = 0
    for name, value in vars(container).items():
        if name.startswith("_"):
            continue
        if isinstance(value, ActionDef):
            registry.register_action(value)
            count += 1
        elif isinstance(value, ResourceTypeDef):
            registry.register_resource_type(value)
            count += 1
        elif isinstance(value, RoleDef):
            registry.register_role(value)
            count += 1
        elif isinstance(value, SystemDef):
            registry.register_system(value)
            count += 1
    return count


def load_from_classes(registry: SchemaRegistry, containers: Iterable[type]) -> int:
    """便捷方法：从多个容器类批量加载。"""
    return sum(load_from_class(registry, cls) for cls in containers)


# ---- 从 dict 加载（未来可对接 YAML/JSON/DB）--------------------------------


def load_from_dict(registry: SchemaRegistry, data: Mapping[str, Any]) -> int:
    """从字典结构加载定义。

    字典结构约定：
        {
            "systems": [
                {"id": "bk_monitor", "name": "蓝鲸监控", ...},
            ],
            "resource_types": [
                {"id": "space", "name": "业务", "ancestor": ""},
            ],
            "actions": [
                {"id": "view_business", "name": "业务查看", "resource_type": "space"},
            ],
            "roles": [
                {"id": "space_viewer", "name": "空间只读",
                 "actions": [{"action_id": "view_business", "resource_type": "space"}]},
            ],
        }

    每个键都是可选的；未提供的类别跳过。

    Args:
        registry: 目标注册表
        data: 定义字典

    Returns:
        实际注册的条目数
    """
    count = 0

    for item in data.get("systems", []) or []:
        registry.register_system(_build_system(item))
        count += 1

    for item in data.get("resource_types", []) or []:
        registry.register_resource_type(_build_resource_type(item))
        count += 1

    for item in data.get("actions", []) or []:
        registry.register_action(_build_action(item))
        count += 1

    for item in data.get("roles", []) or []:
        registry.register_role(_build_role(item))
        count += 1

    return count


# ---- 内部：dict → dataclass 转换 -------------------------------------------


def _build_system(item: Mapping[str, Any]) -> SystemDef:
    _require_keys(item, {"id", "name"}, "system")
    return SystemDef(
        id=item["id"],
        name=item["name"],
        description=item.get("description", ""),
        managers=tuple(item.get("managers", ()) or ()),
        clients=tuple(item.get("clients", ()) or ()),
        callback_url=item.get("callback_url", ""),
        extensions=dict(item.get("extensions", {}) or {}),
    )


def _build_resource_type(item: Mapping[str, Any]) -> ResourceTypeDef:
    _require_keys(item, {"id", "name"}, "resource_type")
    return ResourceTypeDef(
        id=item["id"],
        name=item["name"],
        ancestor=item.get("ancestor", "") or "",
        description=item.get("description", ""),
        extensions=dict(item.get("extensions", {}) or {}),
    )


def _build_action(item: Mapping[str, Any]) -> ActionDef:
    _require_keys(item, {"id", "name"}, "action")
    return ActionDef(
        id=item["id"],
        name=item["name"],
        resource_type=item.get("resource_type", ""),
        description=item.get("description", ""),
        extensions=dict(item.get("extensions", {}) or {}),
    )


def _build_role(item: Mapping[str, Any]) -> RoleDef:
    _require_keys(item, {"id", "name"}, "role")
    raw_actions = item.get("actions", ()) or ()
    _validate_bindings(raw_actions)
    bindings = tuple(
        RoleActionBinding(
            action_id=b["action_id"],
            resource_type=b.get("resource_type", ""),
        )
        for b in raw_actions
    )
    return RoleDef(
        id=item["id"],
        name=item["name"],
        description=item.get("description", ""),
        actions=bindings,
        extensions=dict(item.get("extensions", {}) or {}),
    )


def _validate_bindings(bindings) -> None:
    """校验每个绑定字典包含必填的 action_id。"""
    for i, b in enumerate(bindings):
        if not isinstance(b, dict):
            raise SchemaError(f"role action binding [{i}] must be a dict, got {type(b).__name__}")
        if "action_id" not in b:
            raise SchemaError(f"role action binding [{i}] missing required key: 'action_id'")


def _require_keys(item: Mapping[str, Any], required: set[str], kind: str) -> None:
    missing = required - set(item)
    if missing:
        raise SchemaError(f"{kind} definition missing required keys: {sorted(missing)}")
