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
from ply.lex import lex
from ply.yacc import yacc

tokens = ["FLOAT", "LEFT_PARENTHESES", "RIGHT_PARENTHESES", "OPERATOR", "NAME"]

t_ignore = " \t"

t_FLOAT = r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?|0x[\da-fA-F]+|[+-]?[iI][nN][fF]|[nN][aA][nN]"
t_LEFT_PARENTHESES = r"\("
t_RIGHT_PARENTHESES = r"\)"
t_OPERATOR = r"[-+*/%^]"
t_NAME = r"(?!.*(?:[iI][nN][fF]|[nN][aA][nN]))[a-zA-Z_][a-zA-Z_0-9]*"


def t_error(t):
    print(f"Illegal character {t.value[0]!r}")
    t.lexer.skip(1)


expression_lexer = lex()


def p_expression(p):
    """
    expression : expression OPERATOR expression
               | LEFT_PARENTHESES expression RIGHT_PARENTHESES
               | FLOAT
               | NAME
    """
    if len(p) == 2:
        p[0] = [p[1]]
    elif len(p) == 4:
        expression = []
        for token in p[1:]:
            if isinstance(token, (tuple, list)):
                expression.extend(token)
            else:
                expression.append(token)
        p[0] = expression


def p_error(p):
    from bkmonitor.as_code.ply.error import ParseError

    raise ParseError(f"Syntax error when parse function at {p!r}")


expression_parser = yacc()
