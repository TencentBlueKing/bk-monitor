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

from typing import Protocol, runtime_checkable

from apps.log_commons.external_auth.context import ExternalRequestContext
from apps.log_commons.external_auth.decision import DecisionSource, SourceResult


@runtime_checkable
class AuthSource(Protocol):
    """一条独立的放行依据。

    实现方只回答「我这一侧允不允许」，不关心还有哪些来源，也不做 OR 合并——
    合并由 pipeline 负责，来源之间不允许互相引用。
    """

    name: DecisionSource

    def check(self, ctx: ExternalRequestContext) -> SourceResult: ...


@runtime_checkable
class HardConstraint(Protocol):
    """无论哪个来源放行都必须拒绝的约束。

    与 AuthSource 的区别在于它不参与 OR：任何一条命中就直接拒绝，
    用于承载合规、封禁一类不能被新旧权限互相兜底的规则。
    返回空字符串表示通过，返回非空字符串作为拒绝原因。
    """

    def check(self, ctx: ExternalRequestContext) -> str: ...
