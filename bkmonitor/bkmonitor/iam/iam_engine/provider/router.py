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
# ProviderRouter —— Framework 的统一权限路由入口
#
# 职责：
#   1. 在委托给读 CompositionPolicy 之前，先跑 BypassRules；命中即放行
#   2. 委托给读 CompositionPolicy 完成鉴权、展示和数据查询
#   3. 委托给独立 PermissionWriter 完成权限写入
#
# 为什么需要独立一层：
#   * BypassRule 是读鉴权横切能力，不同 CompositionPolicy 都需要
#   * 未来若增加 Metrics / Audit / CircuitBreaker，也在此层挂钩
#   * 上层 IAMFramework 只与 Router 打交道，接口稳定
#
# ---------------------------------------------------------------------------

from typing import TYPE_CHECKING

from ..core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceAuthResult,
    ResourceInstance,
    Subject,
    VisibleResult,
    to_action_id,
    to_resource_type_id,
)
from ..provider.composition.base import CompositionPolicy
from ..provider.permission_writer import PermissionWriteResult, PermissionWriter

if TYPE_CHECKING:
    from ..crosscutting.bypass import BypassRule
    from ..policy.expression import PolicyExpression
    from ..schema.definitions import ActionDef, ResourceTypeDef


class ProviderRouter:
    """Framework 的统一权限路由入口。

    典型用法（由 IAMFramework 装配）::

        router = ProviderRouter(
            read_policy=AnyOfPolicy([v3, v4]),
            permission_writer=PermissionWriter([v4, v3]),
            bypass_rules=[SettingsSkipRule(), TokenBypassRule()],
        )
        allowed = router.is_allowed(request)
    """

    def __init__(
        self,
        read_policy: CompositionPolicy,
        permission_writer: PermissionWriter,
        bypass_rules: list[BypassRule] | None = None,
    ) -> None:
        self.read_policy = read_policy
        self.permission_writer = permission_writer
        self.bypass_rules: list[BypassRule] = list(bypass_rules or [])

    # ---- 内部 helper ----

    def _should_bypass(
        self,
        subject: Subject,
        actions: tuple[ActionDef | str, ...],
        resources: tuple[ResourceInstance, ...],
    ) -> bool:
        """任一 BypassRule 命中即返回 True。"""
        for rule in self.bypass_rules:
            if rule.should_bypass(subject, actions, resources):
                return True
        return False

    # ==================== 鉴权通路（bypass 横切） ====================

    def is_allowed(self, request: AuthRequest) -> bool:
        if self._should_bypass(
            request.subject,
            (request.action_id,),
            (request.resource,) if request.resource else (),
        ):
            return True
        return self.read_policy.is_allowed(request)

    def batch_by_resource(self, request: BatchByResourceRequest) -> BatchAuthResult:
        if self._should_bypass(
            request.subject,
            (request.action_id,),
            request.resources,
        ):
            return BatchAuthResult(
                items=tuple(
                    ResourceAuthResult(
                        action_id=to_action_id(request.action_id),
                        resource_type=to_resource_type_id(r.type),
                        resource_id=r.id,
                        allowed=True,
                    )
                    for r in request.resources
                )
            )
        return self.read_policy.batch_by_resource(request)

    def batch_by_action(self, request: BatchByActionRequest) -> BatchAuthResult:
        if self._should_bypass(
            request.subject,
            request.action_ids,
            (request.resource,) if request.resource else (),
        ):
            return BatchAuthResult(
                items=tuple(
                    ResourceAuthResult(
                        action_id=to_action_id(aid),
                        resource_type=to_resource_type_id(request.resource.type) if request.resource else "",
                        resource_id=request.resource.id if request.resource else "",
                        allowed=True,
                    )
                    for aid in request.action_ids
                )
            )
        return self.read_policy.batch_by_action(request)

    def get_apply_url(self, request: ApplyURLRequest) -> str:
        return self.read_policy.get_apply_url(request)

    def get_apply_data(
        self,
        action_ids: list[str],
        resources: list[ResourceInstance],
        subject: Subject,
    ) -> dict | None:
        """权限申请数据由组合策略的主 Provider 生成。"""
        return self.read_policy.get_apply_data(action_ids, resources, subject)

    # ==================== 创建者授权 ====================

    def grant_creator_action(
        self,
        resource_type: ResourceTypeDef | str,
        resource_id: str,
        creator: str,
        expired_at: int | None = None,
        tenant_id: str = "",
    ) -> PermissionWriteResult:
        """授予创建者权限；写目标由独立写配置决定，不受读策略影响。"""
        return self.permission_writer.grant_creator_action(resource_type, resource_id, creator, expired_at, tenant_id)

    # ==================== 数据通路（通用收集，不经过 bypass） ====================

    def query_policies(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> list[PolicyExpression]:
        """收集所有 Provider 的策略 AST，原样返回不合并。

        不走 BypassRule：bypass 决定"整个鉴权是否放行"，与 AST 数据查询的语义不匹配。
        """
        return self.read_policy.query_policies(subject, action_id)

    def query_policies_by_actions(
        self,
        subject: Subject,
        action_ids: list[ActionDef | str],
    ) -> dict[str, list[PolicyExpression]]:
        """批量收集多个 action 的策略 AST。"""
        return self.read_policy.query_policies_by_actions(subject, action_ids)

    def has_any_permission(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> bool:
        """是否存在任意实例级权限（不走 bypass：与 AST 数据查询同理）。"""
        return self.read_policy.has_any_permission(subject, action_id)

    def filter_visible_resources(
        self,
        subject: Subject,
        action_id: ActionDef | str,
        candidates: tuple[ResourceInstance, ...],
    ) -> VisibleResult:
        """过滤可见资源。"""
        return self.read_policy.filter_visible_resources(subject, action_id, candidates)
