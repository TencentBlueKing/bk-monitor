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
# IAMFramework —— 框架中心装配器与对外门面
#
# 职责：
#   1. 持有只读 SchemaRegistry（schema 元数据查询）
#   2. 持有所有 Provider 实例（通过 fw.providers["name"] 直接访问）
#   3. 持有 ProviderRouter（读策略 + 通用权限写策略 + bypass 横切）
#   4. 对外暴露鉴权 / 数据查询接口
#
# 生命周期：
#   构造 → 注入 schema + providers + composition + bypass_rules → 即用
#   不持有 Django 依赖；django/ 层负责从 settings 构建 IAMFramework 实例。
#
# 典型用法::
#
#   fw = IAMFramework(
#       schema=registry,
#       providers=[v4_provider, v3_provider],
#       read_policy=AnyOfPolicy([v4_provider, v3_provider]),
#       permission_writer=PermissionWriter([v4_provider, v3_provider]),
#       bypass_rules=[SettingsSkipRule()],
#   )
#   allowed = fw.is_allowed(request)
#   v3_expr = fw.providers["v3"].query_policy(subject, action_id)
# ---------------------------------------------------------------------------

from typing import TYPE_CHECKING

from ..core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceInstance,
    Subject,
    VisibleResult,
)
from ..core.exceptions import ProviderNotFound
from ..provider.base import PermissionProvider
from ..provider.permission_writer import PermissionWriteResult, PermissionWriter

if TYPE_CHECKING:
    from ..schema.definitions import ActionDef, ResourceTypeDef
from ..provider.composition.base import CompositionPolicy
from ..provider.router import ProviderRouter
from ..schema.registry import SchemaRegistry

if TYPE_CHECKING:
    from ..crosscutting.bypass import BypassRule
    from ..policy.expression import PolicyExpression


class IAMFramework:
    """IAM 鉴权框架的中心装配器与对外门面。

    用法::

        fw = IAMFramework(
            schema=registry,
            providers=[v4, v3],
            read_policy=AnyOfPolicy([v4, v3]),
            permission_writer=PermissionWriter([v4, v3]),
            bypass_rules=[SettingsSkipRule()],
        )
        allowed = fw.is_allowed(request)
    """

    def __init__(
        self,
        schema: SchemaRegistry,
        providers: list[PermissionProvider],
        read_policy: CompositionPolicy,
        permission_writer: PermissionWriter,
        bypass_rules: list[BypassRule] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("IAMFramework requires at least one provider")

        self._schema = schema
        if len({p.name for p in providers}) != len(providers):
            raise ValueError(f"Provider names must be unique, got: {[p.name for p in providers]}")
        self._providers: dict[str, PermissionProvider] = {p.name: p for p in providers}
        self._router = ProviderRouter(read_policy, permission_writer, bypass_rules)

    # ---- 只读资源 ----

    @property
    def schema(self) -> SchemaRegistry:
        """只读 Schema 注册表。"""
        return self._schema

    @property
    def providers(self) -> dict[str, PermissionProvider]:
        """按名称访问 Provider 实例。

        用于直接调用某个 Provider 的独有能力，绕过组合策略::

            v3_expr = fw.providers["v3"].query_policy(subject, action_id)
        """
        return self._providers

    def get_provider(self, name: str) -> PermissionProvider:
        """按名称获取 Provider（框架导航入口）。

        Args:
            name: Provider 名称（如 "v3" / "v4"）。

        Returns:
            已装配的 Provider 实例。

        Raises:
            ProviderNotFound: 名称不存在。
        """
        try:
            return self._providers[name]
        except KeyError:
            raise ProviderNotFound(f"Provider {name!r} not found. Available: {sorted(self._providers)}") from None

    @property
    def router(self) -> ProviderRouter:
        """内部 Router（用于需要直接访问读策略或写策略的场景）。"""
        return self._router

    # ==================== 鉴权通路 ====================

    def is_allowed(self, request: AuthRequest) -> bool:
        """单次鉴权。走 bypass 横切 + composition 组合。"""
        return self._router.is_allowed(request)

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        """同 action、多 resource 批量鉴权。"""
        return self._router.batch_by_resource(request)

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        """多 action 批量鉴权。"""
        return self._router.batch_by_action(request)

    def get_apply_url(self, request: ApplyURLRequest) -> str:
        """生成权限申请 URL。由 composition 的 primary Provider 生成。"""
        return self._router.get_apply_url(request)

    def get_apply_data(
        self,
        action_ids: list[str],
        resources: list[ResourceInstance],
        subject: Subject,
    ) -> dict | None:
        """生成权限申请数据（前端 "permission" 字段）。

        由 composition 的 primary Provider 生成，Provider 不支持时返回 None。
        """
        return self._router.get_apply_data(action_ids, resources, subject)

    # ==================== 创建者授权 ====================

    def grant_creator_action(
        self,
        resource_type: ResourceTypeDef | str,
        resource_id: str,
        creator: str,
        expired_at: int | None = None,
        tenant_id: str = "",
    ) -> PermissionWriteResult:
        """授予资源创建者对该资源的管理权限，返回每个写目标的执行结果。"""
        return self._router.grant_creator_action(resource_type, resource_id, creator, expired_at, tenant_id)

    # ==================== 数据通路 ====================

    def query_policies(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> list[PolicyExpression]:
        """收集所有 Provider 的策略 AST，原样返回不合并。"""
        return self._router.query_policies(subject, action_id)

    def query_policies_by_actions(
        self,
        subject: Subject,
        action_ids: list[ActionDef | str],
    ) -> dict[str, list[PolicyExpression]]:
        """批量收集多个 action 的策略 AST。"""
        return self._router.query_policies_by_actions(subject, action_ids)

    def has_any_permission(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> bool:
        """用户对该 action 是否存在任意实例级权限（布尔，无需候选列表）。

        用于权限层粗门禁；多 Provider 组合时任一为真即真。
        """
        return self._router.has_any_permission(subject, action_id)

    def filter_visible_resources(
        self,
        subject: Subject,
        action_id: ActionDef | str,
        candidates: tuple[ResourceInstance, ...],
    ) -> VisibleResult:
        """从候选资源中过滤出可见实例（反向列举消费方统一入口）。

        多 Provider 组合时框架负责合并（all_granted 取 OR，visible_ids 取并集）。
        """
        return self._router.filter_visible_resources(subject, action_id, candidates)
