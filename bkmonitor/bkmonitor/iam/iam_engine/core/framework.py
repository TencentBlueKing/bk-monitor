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
#   3. 持有 ProviderRouter（鉴权通路 = bypass 横切 + composition 组合）
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
#       composition=AnyOfPolicy([v4_provider, v3_provider]),
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
)
from ..provider.base import PermissionProvider

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
            composition=AnyOfPolicy([v4, v3]),
            bypass_rules=[SettingsSkipRule()],
        )
        allowed = fw.is_allowed(request)
    """

    def __init__(
        self,
        schema: SchemaRegistry,
        providers: list[PermissionProvider],
        composition: CompositionPolicy,
        bypass_rules: list[BypassRule] | None = None,
    ) -> None:
        if not providers:
            raise ValueError("IAMFramework requires at least one provider")

        self._schema = schema
        if len({p.name for p in providers}) != len(providers):
            raise ValueError(f"Provider names must be unique, got: {[p.name for p in providers]}")
        self._providers: dict[str, PermissionProvider] = {p.name: p for p in providers}
        self._router = ProviderRouter(composition, bypass_rules)

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

    @property
    def router(self) -> ProviderRouter:
        """内部 Router（用于需要直接访问 bypass/composition 的场景）。"""
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
    ) -> None:
        """授予资源创建者对该资源的管理权限。由 composition 的 primary Provider 执行。"""
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
