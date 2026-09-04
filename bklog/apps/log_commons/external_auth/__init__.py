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

# PO 外部访问的鉴权管道。
#
# 外部请求的放行依据不止一种：旧的 ExternalPermission 授权记录、权限中心、以及提取这类按策略匹配的
# 能力。它们的判定方式互不相同，但对调用方来说只有一个问题——这次请求放不放行。本包把这件事收敛成
# 「默认放行旁路 -> 硬约束 -> 按能力 OR 聚合」三步，调用方只依赖 authorize() 和 ExternalAuthDecision。
#
# 接入新的放行依据时实现 AuthSource 协议并注册到对应能力即可，不需要改 pipeline，也不需要改调用方。

from apps.log_commons.external_auth.base import AuthSource, HardConstraint
from apps.log_commons.external_auth.capability import CAPABILITY_REGISTRY, Capability, get_capability
from apps.log_commons.external_auth.context import ExternalRequestContext, IdentityContext
from apps.log_commons.external_auth.decision import (
    DecisionSource,
    ExternalAuthDecision,
    SourceResult,
    empty_resources_result,
)
from apps.log_commons.external_auth.execution import SELF_EXECUTED_SOURCES, resolve_execution_user
from apps.log_commons.external_auth.pipeline import HARD_CONSTRAINTS, authorize, combine_or
from apps.log_commons.external_auth.space_access import (
    SPACE_ACCESS_SOURCES,
    SpaceAccessSource,
    has_space_access,
    list_authorized_space_actions,
    list_authorized_space_uids,
)
from apps.log_commons.external_auth.view_mapping import (
    is_default_allowed,
    resolve_declared_action_id,
    resolve_resource,
)

__all__ = [
    "CAPABILITY_REGISTRY",
    "HARD_CONSTRAINTS",
    "SPACE_ACCESS_SOURCES",
    "AuthSource",
    "Capability",
    "DecisionSource",
    "ExternalAuthDecision",
    "ExternalRequestContext",
    "HardConstraint",
    "IdentityContext",
    "SELF_EXECUTED_SOURCES",
    "SourceResult",
    "SpaceAccessSource",
    "authorize",
    "combine_or",
    "resolve_execution_user",
    "empty_resources_result",
    "get_capability",
    "has_space_access",
    "is_default_allowed",
    "list_authorized_space_actions",
    "list_authorized_space_uids",
    "resolve_declared_action_id",
    "resolve_resource",
]
