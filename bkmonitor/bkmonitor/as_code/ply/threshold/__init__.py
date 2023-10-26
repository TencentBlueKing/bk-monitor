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

keywords = {
    "and": "AND",
    "or": "OR",
}

tokens = ["EQ", "NEQ", "GT", "GTE", "LT", "LTE", "INT", "FLOAT", "MINUS"] + list(keywords.values())

t_ignore = " \t"

t_EQ = r"="
t_NEQ = r"!="
t_GT = r">"
t_GTE = r">="
t_LT = r"<"
t_LTE = r"<="
t_INT = r"\d+"
t_FLOAT = r"\d+\.\d+"
t_OR = "or"
t_AND = "and"
t_MINUS = "-"

METHOD_MAPPING = {
    t_EQ: "eq",
    t_NEQ: "neq",
    t_GT: "gt",
    t_LT: "lt",
    t_GTE: "gte",
    t_LTE: "lte",
}


def t_error(t):
    print(f"Illegal character {t.value[0]!r}")
    t.lexer.skip(1)


threshold_lexer = lex()


def p_expression(p):
    """
    expression : expression OR term
    """
    p[0] = [*p[1], p[3]]


def p_expression_term(p):
    """
    expression : term
    """
    p[0] = [p[1]]


def p_term(p):
    """
    term : term AND condition
    """
    p[0] = [*p[1], p[3]]


def p_term_condition(p):
    """
    term : condition
    """
    p[0] = [p[1]]


def p_condition(p):
    """
    condition : EQ number
              | NEQ number
              | GT number
              | GTE number
              | LT number
              | LTE number
    """
    p[0] = {"method": METHOD_MAPPING[p[1]], "threshold": p[2]}


def p_number(p):
    """
    number : INT
           | MINUS INT
    """
    if len(p) == 2:
        p[0] = int(p[1])
    else:
        p[0] = -int(p[2])


def p_number_float(p):
    """
    number : FLOAT
           | MINUS FLOAT
    """
    if len(p) == 2:
        p[0] = float(p[1])
    else:
        p[0] = -float(p[2])


def p_error(p):
    from bkmonitor.as_code.ply.error import ParseError

    raise ParseError(f"Syntax error when parse threshold at {p!r}")


threshold_parser = yacc()
