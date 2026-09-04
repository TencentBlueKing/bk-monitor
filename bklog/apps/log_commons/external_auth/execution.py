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

from apps.log_commons.external_auth.context import IdentityContext
from apps.log_commons.external_auth.decision import DecisionSource, ExternalAuthDecision

# 这些来源放行后，下游必须 login 成外部用户本人；旧票和默认放行仍穿空间授权人。
SELF_EXECUTED_SOURCES = frozenset({DecisionSource.IAM, DecisionSource.STRATEGY})


def resolve_execution_user(
    decision: ExternalAuthDecision,
    identity: IdentityContext,
    authorizer: str,
) -> str:
    """按放行来源解析执行身份，不能在 authorize() 之前写死。

    本单注册表只有旧票，因此生产路径只会落到 authorizer。含 IAM / STRATEGY 的分支留给后续单据，
    但解析规则必须现在锁住，避免第 03 单再推翻身份结构。
    """
    if decision.sources & SELF_EXECUTED_SOURCES:
        return identity.authorization_subject
    return authorizer
