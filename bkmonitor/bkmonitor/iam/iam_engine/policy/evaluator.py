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
# DictEvaluator —— 对内存 dict 求 PolicyExpression 的值
#
# 用法：
#   evaluator = DictEvaluator()
#   for space in Space.objects.all():
#       if evaluator.evaluate(expr, {"id": space.id, "name": space.name}):
#           yield space
#
# 与 DjangoQTranslator 的分工：
#   * DictEvaluator     —— 已加载到内存的对象，逐个求值（小数据集 / 单条判断）
#   * DjangoQTranslator —— 未加载的数据集，翻译成 Django Q，下推 DB 过滤
#
# 规则：
#   1. 只依赖 stdlib；不 import django / iam SDK
#   2. 未识别的操作符抛 NotImplementedError，方便后续扩展时立即报错
# ---------------------------------------------------------------------------

from collections.abc import Mapping
from typing import Any

from ..policy.expression import Op, PolicyExpression


def _as_collection(value):
    """Ensure value is a collection for IN/NOT_IN operators.

    Strings are wrapped as a single-element tuple to prevent
    substring/character-level matching.
    """
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return value


class DictEvaluator:
    """给一个 dict 对象和一个表达式，返回是否匹配。

    典型使用场景：
      * 拿到 v3 的策略 AST 之后，在内存里对已加载的对象做过滤
      * 单元测试里验证 Provider 生成的表达式是否正确
      * 权限申请前预判是否可以放行
    """

    def evaluate(self, expr: PolicyExpression, obj: Mapping[str, Any]) -> bool:
        """对单个 dict 求 expr 的值。

        Args:
            expr: 策略表达式
            obj: 被判定的对象；键即 expr.field 的取值来源

        Returns:
            表达式对 obj 是否成立
        """
        op = expr.op

        # ---- 通配 ----
        if op is Op.ANY:
            return True
        if op is Op.NONE:
            return False

        # ---- 逻辑 ----
        if op is Op.AND:
            return all(self.evaluate(c, obj) for c in expr.children)
        if op is Op.OR:
            return any(self.evaluate(c, obj) for c in expr.children)
        if op is Op.NOT:
            if not expr.children:
                raise ValueError("NOT expression must have exactly one child")
            return not self.evaluate(expr.children[0], obj)

        # ---- 比较 ----
        left = obj.get(expr.field)

        if op is Op.EQ:
            return left == expr.value
        if op is Op.NEQ:
            return left != expr.value
        if op is Op.IN:
            return left in _as_collection(expr.value)
        if op is Op.NOT_IN:
            return left not in _as_collection(expr.value)
        if op is Op.STARTS_WITH:
            return isinstance(left, str) and left.startswith(str(expr.value))
        if op is Op.ENDS_WITH:
            return isinstance(left, str) and left.endswith(str(expr.value))
        if op is Op.CONTAINS:
            # 语义与 Django __contains 对齐：left 是 str 时做子串匹配；
            # 其它可迭代类型做包含判断（例如 tags 列表包含某标签）
            if isinstance(left, str):
                return str(expr.value) in left
            try:
                return expr.value in left  # type: ignore[operator]
            except TypeError:
                return False

        raise NotImplementedError(f"Unsupported op: {op}")
