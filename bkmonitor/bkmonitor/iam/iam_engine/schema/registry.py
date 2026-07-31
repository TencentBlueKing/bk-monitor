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
# SchemaRegistry —— 元数据中心注册表
#
# 生命周期（严格三阶段）：
#     构建阶段（可写） → freeze() → 服务阶段（只读）
#
# 相较于"每次从 type.__dict__ 里 collect"的做法：
#   1. 支持多来源加载（class / dict / 未来 yaml）
#   2. freeze 时做一次性完整性校验（引用完整、无循环等）
#   3. 提供反向查询（action 属于哪些 role、resource_type 的祖先链）
#   4. 冻结后不可变，Provider 之间共享同一份只读视图，避免并发问题
#
# 并发与多副本约束（重要）：
#   * 构建阶段假定单线程；由 Django AppConfig.ready() 触发，Django 保证 ready
#     在单进程内单线程执行，因此构建期不加锁是安全的。
#   * 多副本部署（例如 K8s 多 Pod、Gunicorn 多 Worker）时，每个进程各自构建
#     并冻结自己的 Registry 实例，不跨进程共享；由于 Schema 定义源自 Python
#     静态代码，各进程构建结果一致，无同步问题。
#   * freeze() 之后所有查询方法都是纯读操作（不修改任何 dict / 内部状态），
#     多线程 / 多协程 / 多 Provider 并发查询天然安全，无需加锁。
#   * 构建阶段结束的时点：整个应用生命周期内必须在"任何 Provider 首次调用
#     鉴权接口之前"完成 freeze()。当前实现由 IAMFramework 在启动时统一调用
#     freeze()，禁止在服务阶段（运行时）调用任何 register_* 方法——违反将
#     抛出 SchemaFrozenError。
#   * 不承担 Schema → IAM 平台的同步职责（那属于 Migration 层），因此本类
#     内部不涉及分布式锁。
# ---------------------------------------------------------------------------

from bkmonitor.iam.iam_engine.core.exceptions import (
    ActionNotFound,
    ResourceTypeNotFound,
    RoleNotFound,
    SchemaConflict,
    SchemaError,
    SchemaFrozenError,
)
from bkmonitor.iam.iam_engine.schema.definitions import (
    ActionDef,
    ResourceTypeDef,
    RoleDef,
    SystemDef,
)


class SchemaRegistry:
    """Schema 元数据中心注册表。

    典型用法：
        registry = SchemaRegistry()
        registry.register_system(SystemDef(id="bk_monitor", name="蓝鲸监控"))
        registry.register_resource_type(ResourceTypeDef(id="space", name="业务"))
        registry.register_action(ActionDef(id="view_business", name="业务查看",
                                            resource_type="space"))
        registry.freeze()   # 一次性校验并冻结

        registry.get_action("view_business")
        registry.roles_containing_action("view_business")

    线程安全：
        * 构建阶段（freeze 之前）**假定单线程**——预期由 Django AppConfig.ready()
          阶段一次性完成，Django 保证 ready 单进程单线程执行；因此
          register_* 系列方法**不加锁**。
        * freeze() 是构建阶段与服务阶段的分水岭；调用后 self._frozen = True，
          任何 register_* 调用将抛出 SchemaFrozenError，从而杜绝服务阶段
          的意外写入。
        * 服务阶段所有查询方法（get_* / has_* / all_* / *_of_* /
          resolve_ancestor_types 等）都是纯读操作，多线程/多协程/多 Provider
          并发访问天然安全。
        * 多副本部署时，各进程独立构建各自
          的 Registry 实例，不跨进程共享；Schema 源自 Python 静态代码，
          构建结果一致，无需分布式同步。
    """

    def __init__(self) -> None:
        self._systems: dict[str, SystemDef] = {}
        self._resource_types: dict[str, ResourceTypeDef] = {}
        self._actions: dict[str, ActionDef] = {}
        self._roles: dict[str, RoleDef] = {}
        self._frozen: bool = False

    # ------------------------------------------------------------------
    # 状态管理
    # ------------------------------------------------------------------

    @property
    def frozen(self) -> bool:
        return self._frozen

    def _assert_not_frozen(self) -> None:
        if self._frozen:
            raise SchemaFrozenError("SchemaRegistry is frozen, no modification allowed")

    def freeze(self) -> None:
        """执行完整性校验并冻结。冻结后禁止任何注册操作。

        校验内容：
          - Action.resource_type 引用的 ResourceType 存在
          - ResourceTypeDef.ancestor 引用的类型存在，且祖先链无循环
          - RoleDef.actions 中每个 action 存在
          - RoleActionBinding.resource_type（若非空）必须是 action.resource_type
            自身或其祖先
        """
        self._validate()
        self._frozen = True

    def _validate(self) -> None:
        # 1) ResourceType 祖先合法性 & 无环
        for rt in self._resource_types.values():
            self._check_ancestor_chain(rt.id, seen=[])

        # 2) Action.resource_type 存在性
        for action in self._actions.values():
            if action.resource_type and action.resource_type not in self._resource_types:
                raise SchemaError(f"Action {action.id!r} references unknown resource_type {action.resource_type!r}")

        # 3) Role.actions 完整性
        for role in self._roles.values():
            for binding in role.actions:
                if binding.action_id not in self._actions:
                    raise SchemaError(f"Role {role.id!r} references unknown action {binding.action_id!r}")
                if not binding.resource_type:
                    if self._actions[binding.action_id].resource_type:
                        raise SchemaError(f"Role {role.id!r} binding {binding.action_id!r} specifies no resource_type")
                else:
                    self._check_role_binding_resource_type(role, binding)

    def _check_ancestor_chain(self, rt_id: str, seen: list[str]) -> None:
        """递归检查资源类型的祖先链无环且引用完整。入口 rt_id 必须已注册。"""
        if rt_id in seen:
            cycle = " -> ".join([*seen, rt_id])
            raise SchemaError(f"resource_type ancestor cycle detected: {cycle}")

        rt = self._resource_types.get(rt_id)
        if rt is None:
            raise SchemaError(f"resource_type {seen[-1]!r} references unknown ancestor {rt_id!r}")

        if rt.ancestor:
            self._check_ancestor_chain(rt.ancestor, [*seen, rt_id])

    def _check_role_binding_resource_type(self, role: RoleDef, binding) -> None:
        action = self._actions[binding.action_id]
        if not action.resource_type:
            raise SchemaError(
                f"Role {role.id!r} binding {binding.action_id!r} specifies resource_type "
                f"{binding.resource_type!r}, but the action itself has no resource_type"
            )
        allowed = {action.resource_type, *self.resolve_ancestor_types(action.resource_type)}
        if binding.resource_type not in allowed:
            raise SchemaError(
                f"Role {role.id!r} binding {binding.action_id!r} resource_type "
                f"{binding.resource_type!r} must be one of {sorted(allowed)}"
            )

    # ------------------------------------------------------------------
    # 注册接口（仅在 freeze 之前可用）
    # ------------------------------------------------------------------

    def register_system(self, system: SystemDef) -> None:
        self._assert_not_frozen()
        if system.id in self._systems:
            raise SchemaConflict(f"duplicate system id: {system.id!r}")
        self._systems[system.id] = system

    def register_resource_type(self, rt: ResourceTypeDef) -> None:
        self._assert_not_frozen()
        if rt.id in self._resource_types:
            raise SchemaConflict(f"duplicate resource_type id: {rt.id!r}")
        self._resource_types[rt.id] = rt

    def register_action(self, action: ActionDef) -> None:
        self._assert_not_frozen()
        if action.id in self._actions:
            raise SchemaConflict(f"duplicate action id: {action.id!r}")
        self._actions[action.id] = action

    def register_role(self, role: RoleDef) -> None:
        self._assert_not_frozen()
        if role.id in self._roles:
            raise SchemaConflict(f"duplicate role id: {role.id!r}")
        self._roles[role.id] = role

    # ------------------------------------------------------------------
    # 查询接口（freeze 前后均可用）
    # ------------------------------------------------------------------

    # ---- System ----

    def get_system(self, system_id: str) -> SystemDef:
        try:
            return self._systems[system_id]
        except KeyError as exc:
            raise SchemaError(f"system {system_id!r} not found") from exc

    def all_systems(self) -> list[SystemDef]:
        return list(self._systems.values())

    # ---- ResourceType ----

    def get_resource_type(self, rt_id: str) -> ResourceTypeDef:
        try:
            return self._resource_types[rt_id]
        except KeyError as exc:
            raise ResourceTypeNotFound(f"resource_type {rt_id!r} not found") from exc

    def has_resource_type(self, rt_id: str) -> bool:
        return rt_id in self._resource_types

    def all_resource_types(self) -> list[ResourceTypeDef]:
        return list(self._resource_types.values())

    def resolve_ancestor_types(self, rt_id: str) -> list[str]:
        """递归展开某资源类型的完整祖先链（从最近的父到最远的根）。

        rt_id 自身不包含在结果中；rt_id 未注册时返回空列表。
        无环由 freeze() 阶段的 _check_ancestor_chain 保证。
        """
        chain: list[str] = []
        current = self._resource_types.get(rt_id)
        while current and current.ancestor:
            chain.append(current.ancestor)
            current = self._resource_types.get(current.ancestor)
        return chain

    # ---- Action ----

    def get_action(self, action_id: str) -> ActionDef:
        try:
            return self._actions[action_id]
        except KeyError as exc:
            raise ActionNotFound(f"action {action_id!r} not found") from exc

    def has_action(self, action_id: str) -> bool:
        return action_id in self._actions

    def all_actions(self) -> list[ActionDef]:
        return list(self._actions.values())

    # ---- Role ----

    def get_role(self, role_id: str) -> RoleDef:
        try:
            return self._roles[role_id]
        except KeyError as exc:
            raise RoleNotFound(f"role {role_id!r} not found") from exc

    def has_role(self, role_id: str) -> bool:
        return role_id in self._roles

    def all_roles(self) -> list[RoleDef]:
        return list(self._roles.values())

    def actions_of_role(self, role_id: str) -> list[ActionDef]:
        """正向查询：某角色包含哪些 action 定义。"""
        role = self.get_role(role_id)
        return [self._actions[b.action_id] for b in role.actions if b.action_id in self._actions]

    def roles_containing_action(self, action_id: str) -> list[RoleDef]:
        """反向查询：某 action 出现在哪些角色里。"""
        return [role for role in self._roles.values() if any(b.action_id == action_id for b in role.actions)]
