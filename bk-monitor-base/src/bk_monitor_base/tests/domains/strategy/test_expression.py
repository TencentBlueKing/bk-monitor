"""
测试 strategy.expression 模块

该模块实现了基于 PLY 的表达式解析器，用于多告警关联策略的表达式解析和求值。
测试使用表驱动测试模式，提高测试的可维护性和可读性。
"""

import pytest

from bk_monitor_base.domains.strategy.expression import (
    AlertExpressionValue,
    AndItem,
    GroupItem,
    NotItem,
    OrItem,
    VarItem,
    parse_expression,
)


class TestParseExpression:
    """测试 parse_expression 函数"""

    def test_parse_basic_expressions(self):
        """测试基本表达式的解析"""
        test_cases = [
            ("A", VarItem),
            ("A && B", AndItem),
            ("A || B", OrItem),
            ("!A", NotItem),
            ("(A)", GroupItem),
        ]

        for expression, expected_type in test_cases:
            result = parse_expression(expression)
            assert isinstance(result, expected_type), f"表达式 '{expression}' 应该解析为 {expected_type.__name__}"

    def test_parse_complex_expressions(self):
        """测试复杂表达式的解析"""
        test_cases = [
            ("A && B && C", AndItem),  # 多个 AND 操作
            ("A || B || C", OrItem),  # 多个 OR 操作
            ("A && (B || C)", AndItem),  # 嵌套括号
            ("(A && B) || C", OrItem),  # 括号优先级
            ("!A && B", AndItem),  # NOT 优先级
            ("A && !B", AndItem),  # NOT 优先级
            ("A && (B || C) && !D", AndItem),  # 复杂组合
        ]

        for expression, expected_type in test_cases:
            result = parse_expression(expression)
            assert isinstance(result, expected_type), f"表达式 '{expression}' 应该解析为 {expected_type.__name__}"

    def test_parse_expression_errors(self):
        """测试表达式解析错误情况"""
        test_cases = [
            {
                "expression": "",
                "should_raise": True,
                "exception_type": ValueError,
            },
            {
                "expression": None,
                "should_raise": True,
                "exception_type": (TypeError, ValueError),
            },
            {
                "expression": "A & B",  # 单个 & 不是合法操作符
                "should_raise": True,
                "exception_type": ValueError,
            },
            {
                "expression": "A | B",  # 单个 | 不是合法操作符
                "should_raise": True,
                "exception_type": ValueError,
            },
            {
                "expression": "A &&",  # 缺少右操作数
                "should_raise": True,
                "exception_type": ValueError,
            },
            {
                "expression": "&& A",  # 缺少左操作数
                "should_raise": True,
                "exception_type": ValueError,
            },
            {
                "expression": "(A",  # 未闭合括号
                "should_raise": True,
                "exception_type": ValueError,
            },
            {
                "expression": "A)",  # 多余的右括号
                "should_raise": True,
                "exception_type": ValueError,
            },
            {
                "expression": "A @ B",  # 非法字符
                "should_raise": True,
                "exception_type": ValueError,
            },
        ]

        for case in test_cases:
            expression = case["expression"]
            should_raise = case.get("should_raise", False)
            exception_type = case.get("exception_type", Exception)

            if should_raise:
                with pytest.raises(exception_type):
                    parse_expression(expression)
            else:
                result = parse_expression(expression)
                assert result is not None


class TestVarItem:
    """测试 VarItem 类"""

    def test_var_item_eval(self):
        """测试 VarItem 的 eval 方法"""
        test_cases = [
            {
                "var": "A",
                "context": {"A": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.ABNORMAL,
            },
            {
                "var": "B",
                "context": {"B": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.NORMAL,
            },
            {
                "var": "C",
                "context": {"C": AlertExpressionValue.NO_DATA},
                "expected": AlertExpressionValue.NO_DATA,
            },
            {
                "var": "A",
                "context": {"a": AlertExpressionValue.ABNORMAL},  # 大小写不敏感
                "expected": AlertExpressionValue.ABNORMAL,
            },
            {
                "var": "TestVar",
                "context": {"testvar": AlertExpressionValue.NORMAL},  # 大小写不敏感
                "expected": AlertExpressionValue.NORMAL,
            },
            {
                "var": "A",
                "context": None,  # None 上下文
                "should_raise": True,
                "exception_type": ValueError,
            },
            {
                "var": "UndefinedVar",
                "context": {"A": AlertExpressionValue.ABNORMAL},  # 未定义变量
                "should_raise": True,
                "exception_type": ValueError,
            },
        ]

        for case in test_cases:
            var_item = VarItem(case["var"])
            context = case.get("context")
            expected = case.get("expected")
            should_raise = case.get("should_raise", False)
            exception_type = case.get("exception_type", Exception)

            if should_raise:
                with pytest.raises(exception_type):
                    var_item.eval(context)
            else:
                result = var_item.eval(context)
                assert result == expected, f"变量 '{case['var']}' 在上下文 {context} 下应该返回 {expected}"

    def test_var_item_translate(self):
        """测试 VarItem 的 translate 方法"""
        test_cases = [
            {
                "var": "A",
                "context": None,
                "expected": "A",  # 无上下文时返回变量名
            },
            {
                "var": "A",
                "context": {},
                "expected": "A",  # 空上下文时返回变量名
            },
            {
                "var": "A",
                "context": {"A": "告警A"},
                "expected": "告警A",  # 有上下文时返回翻译值
            },
            {
                "var": "B",
                "context": {"B": "告警B", "C": "告警C"},
                "expected": "告警B",  # 只返回对应变量的翻译
            },
            {
                "var": "UndefinedVar",
                "context": {"A": "告警A"},
                "expected": "UndefinedVar",  # 未定义变量返回变量名
            },
        ]

        for case in test_cases:
            var_item = VarItem(case["var"])
            context = case.get("context")
            expected = case["expected"]

            result = var_item.translate(context)
            assert result == expected, f"变量 '{case['var']}' 在上下文 {context} 下应该翻译为 '{expected}'"

    def test_var_item_repr(self):
        """测试 VarItem 的 __repr__ 方法"""
        test_cases = [
            ("A", "VarItem(A)"),
            ("TestVar", "VarItem(TestVar)"),
            ("var123", "VarItem(var123)"),
        ]

        for var, expected_repr in test_cases:
            var_item = VarItem(var)
            result = repr(var_item)
            assert result == expected_repr, f"变量 '{var}' 的 __repr__ 应该返回 '{expected_repr}'"


class TestAndItem:
    """测试 AndItem 类"""

    def test_and_item_eval(self):
        """测试 AndItem 的 eval 方法，验证取最小值逻辑"""
        # 创建测试用的 VarItem
        var_a = VarItem("A")
        var_b = VarItem("B")

        test_cases = [
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.ABNORMAL,  # min(20, 20) = 20
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.NORMAL,  # min(20, 10) = 10
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.NORMAL, "B": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.NORMAL,  # min(10, 20) = 10
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.NORMAL, "B": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.NORMAL,  # min(10, 10) = 10
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.NO_DATA},
                "expected": AlertExpressionValue.NO_DATA,  # min(20, 0) = 0
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.NORMAL, "B": AlertExpressionValue.NO_DATA},
                "expected": AlertExpressionValue.NO_DATA,  # min(10, 0) = 0
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.NO_DATA, "B": AlertExpressionValue.NO_DATA},
                "expected": AlertExpressionValue.NO_DATA,  # min(0, 0) = 0
            },
        ]

        for case in test_cases:
            and_item = AndItem(case["left"], case["right"])
            context = case["context"]
            expected = case["expected"]

            result = and_item.eval(context)
            assert result == expected, (
                f"AndItem({case['left']}, {case['right']}) 在上下文 {context} 下应该返回 {expected}"
            )

    def test_and_item_translate(self):
        """测试 AndItem 的 translate 方法"""
        var_a = VarItem("A")
        var_b = VarItem("B")

        test_cases = [
            {
                "left": var_a,
                "right": var_b,
                "context": None,
                "expected": "A && B",
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": "告警A", "B": "告警B"},
                "expected": "告警A && 告警B",
            },
        ]

        for case in test_cases:
            and_item = AndItem(case["left"], case["right"])
            context = case.get("context")
            expected = case["expected"]

            result = and_item.translate(context)
            assert result == expected, f"AndItem 在上下文 {context} 下应该翻译为 '{expected}'"

    def test_and_item_repr(self):
        """测试 AndItem 的 __repr__ 方法"""
        var_a = VarItem("A")
        var_b = VarItem("B")
        and_item = AndItem(var_a, var_b)

        result = repr(and_item)
        assert "AndItem" in result
        assert "VarItem(A)" in result or "A" in result
        assert "VarItem(B)" in result or "B" in result


class TestOrItem:
    """测试 OrItem 类"""

    def test_or_item_eval(self):
        """测试 OrItem 的 eval 方法，验证取最大值逻辑"""
        var_a = VarItem("A")
        var_b = VarItem("B")

        test_cases = [
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.ABNORMAL,  # max(20, 20) = 20
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.ABNORMAL,  # max(20, 10) = 20
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.NORMAL, "B": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.ABNORMAL,  # max(10, 20) = 20
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.NORMAL, "B": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.NORMAL,  # max(10, 10) = 10
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.NO_DATA},
                "expected": AlertExpressionValue.ABNORMAL,  # max(20, 0) = 20
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.NORMAL, "B": AlertExpressionValue.NO_DATA},
                "expected": AlertExpressionValue.NORMAL,  # max(10, 0) = 10
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": AlertExpressionValue.NO_DATA, "B": AlertExpressionValue.NO_DATA},
                "expected": AlertExpressionValue.NO_DATA,  # max(0, 0) = 0
            },
        ]

        for case in test_cases:
            or_item = OrItem(case["left"], case["right"])
            context = case["context"]
            expected = case["expected"]

            result = or_item.eval(context)
            assert result == expected, (
                f"OrItem({case['left']}, {case['right']}) 在上下文 {context} 下应该返回 {expected}"
            )

    def test_or_item_translate(self):
        """测试 OrItem 的 translate 方法"""
        var_a = VarItem("A")
        var_b = VarItem("B")

        test_cases = [
            {
                "left": var_a,
                "right": var_b,
                "context": None,
                "expected": "A || B",
            },
            {
                "left": var_a,
                "right": var_b,
                "context": {"A": "告警A", "B": "告警B"},
                "expected": "告警A || 告警B",
            },
        ]

        for case in test_cases:
            or_item = OrItem(case["left"], case["right"])
            context = case.get("context")
            expected = case["expected"]

            result = or_item.translate(context)
            assert result == expected, f"OrItem 在上下文 {context} 下应该翻译为 '{expected}'"

    def test_or_item_repr(self):
        """测试 OrItem 的 __repr__ 方法"""
        var_a = VarItem("A")
        var_b = VarItem("B")
        or_item = OrItem(var_a, var_b)

        result = repr(or_item)
        assert "OrItem" in result
        assert "VarItem(A)" in result or "A" in result
        assert "VarItem(B)" in result or "B" in result


class TestNotItem:
    """测试 NotItem 类"""

    def test_not_item_eval(self):
        """测试 NotItem 的 eval 方法，验证状态转换规则"""
        var_a = VarItem("A")

        test_cases = [
            {
                "item": var_a,
                "context": {"A": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.NORMAL,  # 异常 => 正常
            },
            {
                "item": var_a,
                "context": {"A": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.ABNORMAL,  # 正常 => 异常
            },
            {
                "item": var_a,
                "context": {"A": AlertExpressionValue.NO_DATA},
                "expected": AlertExpressionValue.NO_DATA,  # 无数据 => 无数据
            },
        ]

        for case in test_cases:
            not_item = NotItem(case["item"])
            context = case["context"]
            expected = case["expected"]

            result = not_item.eval(context)
            assert result == expected, f"NotItem({case['item']}) 在上下文 {context} 下应该返回 {expected}"

    def test_not_item_translate(self):
        """测试 NotItem 的 translate 方法"""
        var_a = VarItem("A")

        test_cases = [
            {
                "item": var_a,
                "context": None,
                "expected": "!A",
            },
            {
                "item": var_a,
                "context": {"A": "告警A"},
                "expected": "!告警A",
            },
        ]

        for case in test_cases:
            not_item = NotItem(case["item"])
            context = case.get("context")
            expected = case["expected"]

            result = not_item.translate(context)
            assert result == expected, f"NotItem 在上下文 {context} 下应该翻译为 '{expected}'"

    def test_not_item_repr(self):
        """测试 NotItem 的 __repr__ 方法"""
        var_a = VarItem("A")
        not_item = NotItem(var_a)

        result = repr(not_item)
        assert "NotItem" in result
        assert "VarItem(A)" in result or "A" in result


class TestGroupItem:
    """测试 GroupItem 类"""

    def test_group_item_eval(self):
        """测试 GroupItem 的 eval 方法，验证分组不影响求值结果"""
        var_a = VarItem("A")
        var_b = VarItem("B")
        and_item = AndItem(var_a, var_b)

        test_cases = [
            {
                "item": var_a,
                "context": {"A": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.ABNORMAL,
            },
            {
                "item": and_item,
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.NORMAL,  # min(20, 10) = 10
            },
        ]

        for case in test_cases:
            group_item = GroupItem(case["item"])
            context = case["context"]
            expected = case["expected"]

            result = group_item.eval(context)
            assert result == expected, f"GroupItem({case['item']}) 在上下文 {context} 下应该返回 {expected}"

    def test_group_item_translate(self):
        """测试 GroupItem 的 translate 方法，验证翻译结果包含括号"""
        var_a = VarItem("A")
        var_b = VarItem("B")
        and_item = AndItem(var_a, var_b)

        test_cases = [
            {
                "item": var_a,
                "context": None,
                "expected": "(A)",
            },
            {
                "item": var_a,
                "context": {"A": "告警A"},
                "expected": "(告警A)",
            },
            {
                "item": and_item,
                "context": None,
                "expected": "(A && B)",
            },
            {
                "item": and_item,
                "context": {"A": "告警A", "B": "告警B"},
                "expected": "(告警A && 告警B)",
            },
        ]

        for case in test_cases:
            group_item = GroupItem(case["item"])
            context = case.get("context")
            expected = case["expected"]

            result = group_item.translate(context)
            assert result == expected, f"GroupItem 在上下文 {context} 下应该翻译为 '{expected}'"

    def test_group_item_repr(self):
        """测试 GroupItem 的 __repr__ 方法"""
        var_a = VarItem("A")
        group_item = GroupItem(var_a)

        result = repr(group_item)
        assert "GroupItem" in result
        assert "VarItem(A)" in result or "A" in result


class TestItemBaseClass:
    """测试 Item 基类"""

    def test_item_call_method(self):
        """测试 Item 基类的 __call__ 方法"""
        var_a = VarItem("A")
        context = {"A": AlertExpressionValue.ABNORMAL}

        # __call__ 方法应该调用 eval 方法
        result = var_a(context)
        assert result == AlertExpressionValue.ABNORMAL

        # 验证 __call__ 和 eval 返回相同结果
        assert var_a(context) == var_a.eval(context)


class TestExpressionIntegration:
    """测试表达式的集成测试，覆盖复杂表达式的端到端场景"""

    def test_complex_expression_eval(self):
        """测试复杂表达式的求值"""
        test_cases = [
            {
                "expression": "A && B",
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.ABNORMAL,
            },
            {
                "expression": "A && B",
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.NORMAL,  # min(20, 10) = 10
            },
            {
                "expression": "A || B",
                "context": {"A": AlertExpressionValue.NORMAL, "B": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.ABNORMAL,  # max(10, 20) = 20
            },
            {
                "expression": "A || B",
                "context": {"A": AlertExpressionValue.NORMAL, "B": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.NORMAL,  # max(10, 10) = 10
            },
            {
                "expression": "!A",
                "context": {"A": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.NORMAL,  # 异常 => 正常
            },
            {
                "expression": "!A",
                "context": {"A": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.ABNORMAL,  # 正常 => 异常
            },
            {
                "expression": "A && (B || C)",
                "context": {
                    "A": AlertExpressionValue.ABNORMAL,
                    "B": AlertExpressionValue.NORMAL,
                    "C": AlertExpressionValue.ABNORMAL,
                },
                "expected": AlertExpressionValue.ABNORMAL,  # min(20, max(10, 20)) = min(20, 20) = 20
            },
            {
                "expression": "A && (B || C)",
                "context": {
                    "A": AlertExpressionValue.ABNORMAL,
                    "B": AlertExpressionValue.NO_DATA,
                    "C": AlertExpressionValue.NO_DATA,
                },
                "expected": AlertExpressionValue.NO_DATA,  # min(20, max(0, 0)) = min(20, 0) = 0
            },
            {
                "expression": "(A && B) || C",
                "context": {
                    "A": AlertExpressionValue.NORMAL,
                    "B": AlertExpressionValue.NORMAL,
                    "C": AlertExpressionValue.ABNORMAL,
                },
                "expected": AlertExpressionValue.ABNORMAL,  # max(min(10, 10), 20) = max(10, 20) = 20
            },
            {
                "expression": "!A && B",
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.ABNORMAL},
                "expected": AlertExpressionValue.NORMAL,  # min(10, 20) = 10 (因为 !ABNORMAL = NORMAL)
            },
            {
                "expression": "A && !B",
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.NORMAL},
                "expected": AlertExpressionValue.ABNORMAL,  # min(20, 20) = 20 (因为 !NORMAL = ABNORMAL)
            },
            {
                "expression": "A && (B || C) && !D",
                "context": {
                    "A": AlertExpressionValue.ABNORMAL,
                    "B": AlertExpressionValue.NORMAL,
                    "C": AlertExpressionValue.NO_DATA,
                    "D": AlertExpressionValue.NORMAL,
                },
                "expected": AlertExpressionValue.NORMAL,  # min(20, max(10, 0), 20) = min(20, 10, 20) = 10
            },
        ]

        for case in test_cases:
            expr = parse_expression(case["expression"])
            context = case["context"]
            expected = case["expected"]

            result = expr.eval(context)
            assert result == expected, f"表达式 '{case['expression']}' 在上下文 {context} 下应该返回 {expected}"

    def test_complex_expression_translate(self):
        """测试复杂表达式的翻译"""
        test_cases = [
            {
                "expression": "A && B",
                "context": None,
                "expected": "A && B",
            },
            {
                "expression": "A && B",
                "context": {"A": "告警A", "B": "告警B"},
                "expected": "告警A && 告警B",
            },
            {
                "expression": "A || B",
                "context": None,
                "expected": "A || B",
            },
            {
                "expression": "!A",
                "context": None,
                "expected": "!A",
            },
            {
                "expression": "A && (B || C)",
                "context": None,
                "expected": "A && (B || C)",
            },
            {
                "expression": "A && (B || C)",
                "context": {"A": "告警A", "B": "告警B", "C": "告警C"},
                "expected": "告警A && (告警B || 告警C)",
            },
            {
                "expression": "(A && B) || C",
                "context": None,
                "expected": "(A && B) || C",
            },
            {
                "expression": "!A && B",
                "context": None,
                "expected": "!A && B",
            },
            {
                "expression": "A && !B",
                "context": None,
                "expected": "A && !B",
            },
            {
                "expression": "A && (B || C) && !D",
                "context": None,
                "expected": "A && (B || C) && !D",
            },
            {
                "expression": "A && (B || C) && !D",
                "context": {"A": "告警A", "B": "告警B", "C": "告警C", "D": "告警D"},
                "expected": "告警A && (告警B || 告警C) && !告警D",
            },
        ]

        for case in test_cases:
            expr = parse_expression(case["expression"])
            context = case.get("context")
            expected = case["expected"]

            result = expr.translate(context)
            assert result == expected, f"表达式 '{case['expression']}' 在上下文 {context} 下应该翻译为 '{expected}'"

    def test_expression_call_method(self):
        """测试表达式对象的 __call__ 方法"""
        test_cases = [
            {
                "expression": "A && B",
                "context": {"A": AlertExpressionValue.ABNORMAL, "B": AlertExpressionValue.NORMAL},
            },
            {
                "expression": "A || B",
                "context": {"A": AlertExpressionValue.NORMAL, "B": AlertExpressionValue.ABNORMAL},
            },
            {
                "expression": "!A",
                "context": {"A": AlertExpressionValue.ABNORMAL},
            },
        ]

        for case in test_cases:
            expr = parse_expression(case["expression"])
            context = case["context"]

            # __call__ 方法应该返回与 eval 相同的结果
            call_result = expr(context)
            eval_result = expr.eval(context)

            assert call_result == eval_result, f"表达式 '{case['expression']}' 的 __call__ 和 eval 应该返回相同结果"
