"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from apps.log_commons.external_auth.base import AuthSource, HardConstraint
from apps.log_commons.external_auth.capability import Capability, get_capability
from apps.log_commons.external_auth.context import ExternalRequestContext
from apps.log_commons.external_auth.decision import (
    DecisionSource,
    ExternalAuthDecision,
    SourceResult,
    empty_resources_result,
)
from apps.log_commons.external_auth.view_mapping import is_default_allowed

# 不可被任何来源兜底的约束。当前为空：现有实现里没有「无论如何都拒绝」的规则，
# 凭空补一条就是改变放行行为。合规封禁一类需求出现时挂在这里，不要塞进 AuthSource。
HARD_CONSTRAINTS: tuple[HardConstraint, ...] = ()


def authorize(
    ctx: ExternalRequestContext,
    *,
    capability: Capability | None = None,
    hard_constraints: tuple[HardConstraint, ...] | None = None,
) -> ExternalAuthDecision:
    """外部访问的统一鉴权入口。

    顺序固定为：默认放行旁路 -> 硬约束 -> 按能力 OR 聚合。
    OR 只发生在最后一步，硬约束永远不参与，避免新旧权限互相兜底掉合规规则。
    """
    if is_default_allowed(ctx.view_set, ctx.view_action):
        return ExternalAuthDecision(allowed=True)

    for constraint in HARD_CONSTRAINTS if hard_constraints is None else hard_constraints:
        reason = constraint.check(ctx)
        if reason:
            return ExternalAuthDecision(allowed=False, reject_reason=reason)

    capability = capability or get_capability(ctx.declared_action_id)
    return combine_or(capability.sources, ctx)


def combine_or(sources: tuple[AuthSource, ...], ctx: ExternalRequestContext) -> ExternalAuthDecision:
    """任一来源放行即放行。

    来源故障只置 degraded，不单独否决，也不单独放行——否则新侧一挂，要么全站拒绝，
    要么旧票形同虚设。
    """
    if not sources:
        return ExternalAuthDecision(allowed=False, reject_reason="no auth source is registered for this capability")

    results: list[tuple[AuthSource, SourceResult]] = [(source, source.check(ctx)) for source in sources]
    allowed_pairs = [(source, result) for source, result in results if result.allowed]

    # 审计要的是「命中了哪个授权项、指向哪个资源」，放行来源优先，其次按注册顺序回落到拒绝结果，
    # 这样「授权项命中但资源越权」的拒绝依然能带出 action_id 与 resource_id
    ordered = [result for _, result in allowed_pairs] + [result for _, result in results if not result.allowed]
    matched_action_id = next((item.matched_action_id for item in ordered if item.matched_action_id), "")
    resource_id = next((item.resource_id for item in ordered if item.resource_id is not None), None)
    allow_resources_result = next(
        (item.allow_resources_result for item in ordered if item.allow_resources_result["allowed"]),
        empty_resources_result(),
    )
    degraded = any(result.errored for _, result in results)

    if allowed_pairs:
        return ExternalAuthDecision(
            allowed=True,
            sources=frozenset(source.name for source, _ in allowed_pairs),
            matched_action_id=matched_action_id,
            resource_id=resource_id,
            allow_resources_result=allow_resources_result,
            degraded=degraded,
        )

    return ExternalAuthDecision(
        allowed=False,
        sources=frozenset(),
        matched_action_id=matched_action_id,
        resource_id=resource_id,
        allow_resources_result=allow_resources_result,
        reject_reason=_join_reasons(result for _, result in results),
        degraded=degraded,
    )


def _join_reasons(results) -> str:
    """单来源时保留原文案，多来源时并列展示，避免只报一侧让排障失去线索。"""
    reasons = [result.reject_reason for result in results if result.reject_reason]
    return " | ".join(reasons)


__all__ = ["DecisionSource", "ExternalAuthDecision", "HARD_CONSTRAINTS", "authorize", "combine_or"]
