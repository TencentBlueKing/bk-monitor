# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
"""
多告警关联策略，表达式语法解析器
表达式格式示例： A && (B || C) && !D
"""
import abc

from ply import lex, yacc

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
def t_error(t):
    raise ValueError("Illegal character '%s' at position %d" % (t.value, t.lexpos))


lexer = lex.lex()


# ===============
# 表达式项目的定义
# ===============
class AlertExpressionValue:
    ABNORMAL = 20
    NORMAL = 10
    NO_DATA = 0


class Item(metaclass=abc.ABCMeta):
    def eval(self, context: dict = None) -> int:
        raise NotImplementedError

    def translate(self, context: dict = None) -> int:
        raise NotImplementedError

    def __call__(self, context: dict = None) -> int:
        return self.eval(context)


class VarItem(Item):
    def __init__(self, var: str):
        self.var = var

    def eval(self, context: dict = None) -> int:
        try:
            context = context or {}
            lower_context = {k.lower(): v for k, v in context.items()}
            return lower_context[self.var.lower()]
        except KeyError:
            raise ValueError("variable '%s' is not defined" % self.var)

    def translate(self, context: dict = None) -> str:
        return context.get(self.var, self.var)

    def __repr__(self):
        return f"VarItem({self.var})"


class AndItem(Item):
    def __init__(self, left: Item, right: Item):
        self.left = left
        self.right = right

    def eval(self, context: dict = None) -> int:
        """
        and 取最低状态
        """
        return min(self.left.eval(context), self.right.eval(context))

    def translate(self, context: dict = None) -> str:
        return f"{self.left.translate(context)} && {self.right.translate(context)}"

    def __repr__(self):
        return f"AndItem({self.left}, {self.right})"


class OrItem(Item):
    def __init__(self, left: Item, right: Item):
        self.left = left
        self.right = right

    def eval(self, context: dict = None) -> int:
        """
        or 取最高状态
        """
        return max(self.left.eval(context), self.right.eval(context))

    def translate(self, context: dict = None) -> str:
        return f"{self.left.translate(context)} || {self.right.translate(context)}"

    def __repr__(self):
        return f"OrItem({self.left}, {self.right})"


class GroupItem(Item):
    def __init__(self, item: Item):
        self.item = item

    def eval(self, context: dict = None) -> int:
        return self.item.eval(context)

    def translate(self, context: dict = None) -> str:
        return f"({self.item.translate(context)})"

    def __repr__(self):
        return f"GroupItem({self.item})"


class NotItem(Item):
    def __init__(self, item: Item):
        self.item = item

    def eval(self, context: dict = None) -> int:
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

    def translate(self, context: dict = None) -> str:
        return f"!{self.item.translate(context)}"

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


def p_expression_not(p):
    """expression : NOT expression %prec N_NOT"""
    p[0] = NotItem(p[2])


def p_expression_or(p):
    """expression : expression OR expression"""
    p[0] = OrItem(p[1], p[3])


def p_expression_and(p):
    """expression : expression AND expression"""
    p[0] = AndItem(p[1], p[3])


def p_expression_var(p):
    """expression : VAR"""
    p[0] = VarItem(p[1])


def p_expression_group(p):
    """expression : LPAREN expression RPAREN"""
    p[0] = GroupItem(p[2])


def p_error(p):
    if p:
        raise ValueError("Syntax error at '%s' at position %d" % (p.value, p.lexpos))
    else:
        raise ValueError("Syntax error at EOF")


# ===============
# 使用示例
# expr = parser.parse("A && B")
# expr.eval({"A": True, "B": False}) => True / False
# 或者
# expr({"A": True, "B": False})
# ===============
parser = yacc.yacc(debug=False)


def parse_expression(input: str = None):
    return parser.parse(input=input, lexer=lexer)
