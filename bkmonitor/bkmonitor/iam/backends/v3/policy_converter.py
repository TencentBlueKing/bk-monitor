"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# IAM SDK dict AST → PolicyExpression 转换器
#
# V3Client._do_policy_query / _do_policy_query_by_actions 返回的 dict AST
# 格式（IAM SDK 原生格式），转换为框架中立的 PolicyExpression。
#
# dict AST 节点结构：
#   * ANY:  {"op": "any",          "field": "",  "value": []}
#   * AND:  {"op": "and"|"AND",   "content": [child, ...]}
#   * OR:   {"op": "or"|"OR",     "content": [child, ...]}
#   * EQ:   {"op": "eq",           "field": "...", "value": "..."}
#   * IN:   {"op": "in",           "field": "...", "value": [...]}
#   * NOT_IN: {"op": "not_in",     "field": "...", "value": [...]}
#   * STARTS_WITH: {"op": "starts_with", "field": "...", "value": "..."}
#   * 等等
#
# 规则：
#   1. 不依赖 django / IAM SDK
#   2. 只依赖 stdlib + framework 的 PolicyExpression
# ---------------------------------------------------------------------------

from __future__ import annotations

from iam_engine.policy.expression import Op, PolicyExpression

# IAM SDK dict op → PolicyExpression Op 的映射
_OP_MAP: dict[str, Op] = {
    "eq": Op.EQ,
    "not_eq": Op.NEQ,
    "in": Op.IN,
    "not_in": Op.NOT_IN,
    "starts_with": Op.STARTS_WITH,
    "ends_with": Op.ENDS_WITH,
    "contains": Op.CONTAINS,
    "not_contains": Op.NOT_CONTAINS,
    "not_starts_with": Op.NOT_STARTS_WITH,
    "not_ends_with": Op.NOT_ENDS_WITH,
    "string_contains": Op.STRING_CONTAINS,
    "lt": Op.LT,
    "lte": Op.LTE,
    "gt": Op.GT,
    "gte": Op.GTE,
}


def iam_dict_to_expression(node: dict | None) -> PolicyExpression | None:
    """将 IAM SDK 返回的 dict AST 节点转换为 PolicyExpression。

    Args:
        node: IAM SDK 策略 dict 节点，或 None（表示无策略）

    Returns:
        PolicyExpression 或 None（无策略 / 无法解析）
    """
    if not node:
        return None

    op = node.get("op", "").lower()

    # ---- 通配 ----
    if op == "any":
        return PolicyExpression.any()
    if op == "none":
        return PolicyExpression.none()

    # ---- 逻辑 ----
    if op in ("and", "or"):
        content = node.get("content", [])
        children = [iam_dict_to_expression(c) for c in content]
        if any(c is None for c in children):
            raise ValueError("IAM policy contains an empty logical operand")
        if op == "and":
            return PolicyExpression.and_(*children)
        return PolicyExpression.or_(*children)

    # ---- 比较（叶子节点） ----
    framework_op = _OP_MAP.get(op)
    if framework_op is not None:
        field = node.get("field", "")
        value = node.get("value")
        # IN / NOT_IN 的 value 应该是 tuple（PolicyExpression 叶子要求 tuple）
        if isinstance(value, list):
            value = tuple(value)
        return PolicyExpression.leaf(framework_op, field, value)

    # 不能删除无法识别的限制条件，否则 AND 会被静默放宽。
    raise ValueError(f"Unsupported IAM V3 policy operator: {op}")


def expression_to_iam_dict(expression: PolicyExpression) -> dict:
    """在 V3 边界恢复 SDK AST，复用 SDK 的数组、类型和 IAM path 求值语义。"""
    if expression.op in (Op.AND, Op.OR):
        return {
            "op": expression.op.value,
            "content": [expression_to_iam_dict(child) for child in expression.children],
        }
    return {"op": expression.op.value, "field": expression.field, "value": expression.value}
