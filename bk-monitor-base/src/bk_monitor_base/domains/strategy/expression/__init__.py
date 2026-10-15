"""
多告警关联策略，表达式语法解析器
表达式格式示例： A && (B || C) && !D
"""

from typing import Any, cast, final

from ply import lex, yacc
from typing_extensions import override

# ===============
# 词法解析
# 解析前："A && (B || C) && !D"
# 解析后：
# LexToken(VAR,'A',1,0)
# LexToken(AND,'&&',1,2)
# LexToken(LPAREN,'(',1,5)
# LexToken(VAR,'B',1,6)
# LexToken(OR,'||',1,8)
# LexToken(VAR,'C',1,11)
# LexToken(RPAREN,')',1,12)
# LexToken(AND,'&&',1,14)
# LexToken(NOT,'!',1,17)
# LexToken(VAR,'D',1,18)
# ===============
tokens = (
    "VAR",  # 变量
    "NOT",  # 非
    "AND",  # 与
    "OR",  # 或
    "LPAREN",  # 左括号
    "RPAREN",  # 右括号
)

# 定义Token的匹配规则
t_VAR = r"\w+"
t_NOT = r"!"
t_AND = r"&&"
t_OR = r"\|\|"
t_LPAREN = r"\("
t_RPAREN = r"\)"
t_ignore = " "  # 忽略空格


# 未匹配到Token时的处理逻辑
def t_error(t: Any):
    raise ValueError(f"Illegal character '{t.value}' at position {t.lexpos}")


lexer: lex.Lexer = lex.lex()  # pyright: ignore[reportUnknownVariableType]


# ===============
# 表达式项目的定义
# ===============


@final
class AlertExpressionValue:
    ABNORMAL = 20
    NORMAL = 10
    NO_DATA = 0


class Item:
    def eval(self, context: dict[str, Any] | None = None) -> int:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError

    def translate(self, context: dict[str, Any] | None = None) -> str:  # pyright: ignore[reportUnusedParameter]
        raise NotImplementedError

    def __call__(self, context: dict[str, Any] | None = None) -> int:
        return self.eval(context)


@final
class VarItem(Item):
    def __init__(self, var: str):
        self.var = var

    @override
    def eval(self, context: dict[str, Any] | None = None) -> int:
        try:
            context = context or {}
            lower_context = {k.lower(): v for k, v in context.items()}
            return lower_context[self.var.lower()]
        except KeyError:
            raise ValueError(f"variable '{self.var}' is not defined") from None

    @override
    def translate(self, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        return context.get(self.var, self.var)

    @override
    def __repr__(self):
        return f"VarItem({self.var})"


@final
class AndItem(Item):
    def __init__(self, left: Item, right: Item):
        self.left = left
        self.right = right

    @override
    def eval(self, context: dict[str, Any] | None = None) -> int:
        """
        and 取最低状态
        """
        return min(self.left.eval(context), self.right.eval(context))

    @override
    def translate(self, context: dict[str, Any] | None = None) -> str:
        return f"{self.left.translate(context)} && {self.right.translate(context)}"

    @override
    def __repr__(self):
        return f"AndItem({self.left}, {self.right})"


@final
class OrItem(Item):
    def __init__(self, left: Item, right: Item):
        self.left = left
        self.right = right

    @override
    def eval(self, context: dict[str, Any] | None = None) -> int:
        """
        or 取最高状态
        """
        return max(self.left.eval(context), self.right.eval(context))

    @override
    def translate(self, context: dict[str, Any] | None = None) -> str:
        return f"{self.left.translate(context)} || {self.right.translate(context)}"

    @override
    def __repr__(self):
        return f"OrItem({self.left}, {self.right})"


@final
class GroupItem(Item):
    def __init__(self, item: Item):
        self.item = item

    @override
    def eval(self, context: dict[str, Any] | None = None) -> int:
        return self.item.eval(context)

    @override
    def translate(self, context: dict[str, Any] | None = None) -> str:
        return f"({self.item.translate(context)})"

    @override
    def __repr__(self):
        return f"GroupItem({self.item})"


@final
class NotItem(Item):
    def __init__(self, item: Item):
        self.item = item

    @override
    def eval(self, context: dict[str, Any] | None = None) -> int:
        """
        not 的状态转换规则
        1. 正常 => 异常
        2. 异常 => 正常
        3. 无数据 => 无数据
        """
        value = self.item.eval(context)
        if value == AlertExpressionValue.ABNORMAL:
            return AlertExpressionValue.NORMAL
        if value == AlertExpressionValue.NORMAL:
            return AlertExpressionValue.ABNORMAL
        return AlertExpressionValue.NO_DATA

    @override
    def translate(self, context: dict[str, Any] | None = None) -> str:
        return f"!{self.item.translate(context)}"

    @override
    def __repr__(self):
        return f"NotItem({self.item})"


# ===============
# 语法解析
# 解析前："A && (B || C) && !D"
# 解析后：
# AndItem(
#   AndItem(
#     VarItem(A),
#     GroupItem(
#       OrItem(
#         VarItem(B), VarItem(C)
#       )
#     )
#   ),
#   NotItem(VarItem(D))
# )
# ===============
precedence = (
    ("left", "AND", "OR"),
    ("right", "N_NOT"),
)


def p_expression_not(p: Any):
    """expression : NOT expression %prec N_NOT"""
    p[0] = NotItem(p[2])


def p_expression_or(p: Any):
    """expression : expression OR expression"""
    p[0] = OrItem(p[1], p[3])


def p_expression_and(p: Any):
    """expression : expression AND expression"""
    p[0] = AndItem(p[1], p[3])


def p_expression_var(p: Any):
    """expression : VAR"""
    p[0] = VarItem(p[1])


def p_expression_group(p: Any):
    """expression : LPAREN expression RPAREN"""
    p[0] = GroupItem(p[2])


def p_error(p: Any):
    if p:
        raise ValueError(f"Syntax error at '{p.value}' at position {p.lexpos}")
    else:
        raise ValueError("Syntax error at EOF")


# ===============
# 使用示例
# expr = parser.parse("A && B")
# expr.eval({"A": True, "B": False}) => True / False
# 或者
# expr({"A": True, "B": False})
# ===============
parser: yacc.LRParser = yacc.yacc(debug=False)  # pyright: ignore[reportUnknownVariableType]


def parse_expression(expression: str | None = None) -> Item:
    """
    解析表达式字符串为表达式树

    Args:
        input: 表达式字符串，例如 "A && B"

    Returns:
        Item: 表达式树的根节点

    Examples:
        >>> expr = parse_expression("A && B")
        >>> expr.eval({"A": True, "B": False})
        True
    """
    return cast(Item, parser.parse(input=expression, lexer=lexer))
