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
# ProviderRouter —— Framework 与 CompositionPolicy 之间的胶水层
#
# 职责：
#   1. 在委托给 CompositionPolicy 之前，先跑 BypassRules；命中即放行
#   2. 委托给 CompositionPolicy 完成实际鉴权组合决策
#   3. 数据查询（query_policies）不经过 bypass，直接委托给 policy
#
# 为什么需要独立一层：
#   * BypassRule 是横切能力，不同 CompositionPolicy 都需要
#   * 未来若增加 Metrics / Audit / CircuitBreaker，也在此层挂钩
#   * 上层 IAMFramework 只与 Router 打交道，接口稳定
#
# ---------------------------------------------------------------------------

from typing import TYPE_CHECKING

from bkmonitor.iam.iam_engine.core.types import (
    ApplyURLRequest,
    AuthRequest,
    BatchAuthResult,
    BatchByActionRequest,
    BatchByResourceRequest,
    ResourceAuthResult,
    ResourceInstance,
    Subject,
    to_action_id,
    to_resource_type_id,
)
from bkmonitor.iam.iam_engine.provider.composition.base import CompositionPolicy

if TYPE_CHECKING:
    from bkmonitor.iam.iam_engine.crosscutting.bypass import BypassRule
    from bkmonitor.iam.iam_engine.policy.expression import PolicyExpression
    from bkmonitor.iam.iam_engine.schema.definitions import ActionDef


class ProviderRouter:
    """Framework 与 CompositionPolicy 之间的胶水层。

    典型用法（由 IAMFramework 装配）::

        router = ProviderRouter(
            policy=AnyOfPolicy([v3, v4]),
            bypass_rules=[SettingsSkipRule(), TokenBypassRule()],
        )
        allowed = router.is_allowed(request)
    """

    def __init__(
        self,
        policy: CompositionPolicy,
        bypass_rules: list[BypassRule] | None = None,
    ) -> None:
        self.policy = policy
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
        return self.policy.is_allowed(request)

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
        return self.policy.batch_by_resource(request)

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
        return self.policy.batch_by_action(request)

    def get_apply_url(self, request: ApplyURLRequest) -> str:
        return self.policy.get_apply_url(request)

    # ==================== 数据通路（通用收集，不经过 bypass） ====================

    def query_policies(
        self,
        subject: Subject,
        action_id: ActionDef | str,
    ) -> list[PolicyExpression]:
        """收集所有 Provider 的策略 AST，原样返回不合并。

        不走 BypassRule：bypass 决定"整个鉴权是否放行"，与 AST 数据查询的语义不匹配。
        """
        return self.policy.query_policies(subject, action_id)

    def query_policies_by_actions(
        self,
        subject: Subject,
        action_ids: list[ActionDef | str],
    ) -> dict[str, list[PolicyExpression]]:
        """批量收集多个 action 的策略 AST。"""
        return self.policy.query_policies_by_actions(subject, action_ids)
