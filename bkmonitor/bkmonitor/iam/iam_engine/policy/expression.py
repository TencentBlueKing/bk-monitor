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
# PolicyExpression —— 中立的策略表达式 AST
#
# 目的：让"资源过滤"从"单层 filter_resources()"升级为可下推的表达式。
#   * v3 平台可返回策略 AST（policy_expression），本 AST 是它的中立映射
#   * Provider 内部把平台原始格式转成本 AST
#   * 上层用 DictEvaluator（内存求值）或 DjangoQTranslator（DB 下推）消费
#
# 规则：
#   1. 不绑定任何 IAM 平台的原始数据结构；纯 Python
#   2. frozen dataclass；children 用 tuple 保证可 hash / 不可变
#   3. 只依赖 stdlib，不 import django / iam SDK
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field as dc_field
from enum import Enum
from typing import Any


class Op(str, Enum):
    """策略表达式支持的操作符。

    分三类：
      * 逻辑：AND / OR / NOT
      * 比较：EQ / NEQ / IN / NOT_IN / STARTS_WITH / ENDS_WITH / CONTAINS
      * 通配：ANY（恒真，全量放行）/ NONE（恒假，全量拒绝）
    """

    # 逻辑
    AND = "AND"
    OR = "OR"
    NOT = "NOT"

    # 比较
    EQ = "eq"
    NEQ = "not_eq"
    IN = "in"
    NOT_IN = "not_in"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    CONTAINS = "contains"

    # 通配
    ANY = "any"
    NONE = "none"


@dataclass(frozen=True)
class PolicyExpression:
    """策略表达式抽象语法树节点。

    一棵表达式树由内部节点（逻辑 op + children）和叶子节点（比较 op + field/value）
    组成；ANY / NONE 是两个特殊的常量节点。

    字段用法约定：
      * 逻辑节点：op ∈ {AND, OR, NOT}，仅使用 children；field/value 保持默认
      * 比较节点：op ∈ 比较类，仅使用 field/value；children 保持默认为 ()
      * 通配节点：op ∈ {ANY, NONE}，全部字段保持默认
    """

    op: Op
    field: str = ""
    value: Any = None
    children: tuple[PolicyExpression, ...] = dc_field(default_factory=tuple)

    # ---- 工厂方法：便捷构造 -----------------------------------------

    @classmethod
    def any(cls) -> PolicyExpression:
        """恒真：拥有所有资源权限。"""
        return cls(op=Op.ANY)

    @classmethod
    def none(cls) -> PolicyExpression:
        """恒假：没有任何权限。"""
        return cls(op=Op.NONE)

    @classmethod
    def leaf(cls, op: Op, field: str, value: Any) -> PolicyExpression:
        """构造比较类叶子节点。"""
        return cls(op=op, field=field, value=value)

    @classmethod
    def and_(cls, *children: PolicyExpression) -> PolicyExpression:
        """构造 AND 节点。"""
        return cls(op=Op.AND, children=tuple(children))

    @classmethod
    def or_(cls, *children: PolicyExpression) -> PolicyExpression:
        """构造 OR 节点。"""
        return cls(op=Op.OR, children=tuple(children))

    @classmethod
    def not_(cls, child: PolicyExpression) -> PolicyExpression:
        """构造 NOT 节点。"""
        return cls(op=Op.NOT, children=(child,))
