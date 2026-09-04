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

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DecisionSource(str, Enum):
    """放行来源。用集合记录而不是布尔字段，新增来源时不必改决策结构。"""

    LEGACY = "legacy"
    IAM = "iam"
    STRATEGY = "strategy"


def empty_resources_result() -> dict[str, Any]:
    """与 ExternalPermission.get_resources 的返回结构保持一致。"""
    return {"allowed": False, "resources": []}


@dataclass(frozen=True)
class SourceResult:
    """单个鉴权来源的判定结果，OR 聚合前不允许压成 bool。

    拒绝时同样可以带 matched_action_id 与 resource_id：旧票命中了授权项但资源越权就属于这种情况，
    审计需要记下命中的授权项和被拒的资源。
    """

    allowed: bool
    matched_action_id: str = ""
    resource_id: int | None = None
    allow_resources_result: dict[str, Any] = field(default_factory=empty_resources_result)
    reject_reason: str = ""
    errored: bool = False

    @classmethod
    def allow(
        cls,
        matched_action_id: str = "",
        resource_id: int | None = None,
        allow_resources_result: dict[str, Any] | None = None,
    ) -> "SourceResult":
        return cls(
            allowed=True,
            matched_action_id=matched_action_id,
            resource_id=resource_id,
            allow_resources_result=allow_resources_result or empty_resources_result(),
        )

    @classmethod
    def deny(
        cls,
        reason: str,
        matched_action_id: str = "",
        resource_id: int | None = None,
        allow_resources_result: dict[str, Any] | None = None,
    ) -> "SourceResult":
        return cls(
            allowed=False,
            matched_action_id=matched_action_id,
            resource_id=resource_id,
            allow_resources_result=allow_resources_result or empty_resources_result(),
            reject_reason=reason,
        )

    @classmethod
    def error(cls, reason: str) -> "SourceResult":
        """来源自身故障。不放行，但要让决策标记 degraded，避免与「明确拒绝」混为一谈。"""
        return cls(allowed=False, reject_reason=reason, errored=True)


@dataclass(frozen=True)
class ExternalAuthDecision:
    """外部访问的最终鉴权决策。

    sources 为空且 allowed=True 表示走了默认放行旁路，没有任何来源参与判定。
    degraded 表示至少一个来源故障；allowed 仍可能为 True（另一个来源放行）。
    """

    allowed: bool
    sources: frozenset[DecisionSource] = frozenset()
    matched_action_id: str = ""
    resource_id: int | None = None
    allow_resources_result: dict[str, Any] = field(default_factory=empty_resources_result)
    reject_reason: str = ""
    degraded: bool = False
