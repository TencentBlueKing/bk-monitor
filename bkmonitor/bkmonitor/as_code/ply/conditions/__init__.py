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

from bkmonitor.as_code.ply.error import ParseError

keywords = {
    "and": "AND",
    "or": "OR",
}

tokens = [
    "EQ",
    "NEQ",
    "REGEQ",
    "REGNEQ",
    "INCLUDE",
    "EXCLUDE",
    "GT",
    "GTE",
    "LT",
    "LTE",
    "STRING",
    "NUMBER",
    "NAME",
] + list(keywords.values())

t_ignore = " \t"

t_EQ = r"="
t_NEQ = r"!="
t_REGEQ = r"=~"
t_REGNEQ = r"!~"
t_INCLUDE = r"=-"
t_EXCLUDE = r"!-"
t_STRING = r'("([^"]|\\")*")|(\'([^\']|\\\')*\')'
t_NUMBER = r"-?\d+(\.\d+)?([ \t]*,[ \t]*-?\d+(\.\d+)?)*"
t_GT = r">"
t_GTE = r">="
t_LT = r"<"
t_LTE = r"<="


METHOD_MAPPING = {
    t_EQ: "eq",
    t_NEQ: "neq",
    t_REGEQ: "reg",
    t_REGNEQ: "nreg",
    t_GT: "gt",
    t_GTE: "gte",
    t_LT: "lt",
    t_LTE: "lte",
    t_INCLUDE: "include",
    t_EXCLUDE: "exclude",
}


def t_NAME(t):
    r"[a-zA-Z_][a-zA-Z0-9_\.]*"
    t.type = keywords.get(t.value, "NAME")
    return t


def t_error(t):
    print(f"Illegal character {t.value[0]!r}")
    t.lexer.skip(1)


condition_lexer = lex()


def p_expression(p):
    """
    expression : expression OR term
    """
    p[3][0]["condition"] = "or"
    p[0] = [*p[1], *p[3]]


def p_expression_term(p):
    """
    expression : term
    """
    p[0] = p[1]


def p_term(p):
    """
    term : term AND condition
    """
    p[3]["condition"] = "and"
    p[0] = [*p[1], p[3]]


def p_term_condition(p):
    """
    term : condition
    """
    p[0] = [p[1]]


def p_condition(p):
    """
    condition : NAME EQ STRING
              | NAME NEQ STRING
              | NAME REGEQ STRING
              | NAME REGNEQ STRING
              | NAME INCLUDE STRING
              | NAME EXCLUDE STRING
              | NAME GT STRING
              | NAME GTE STRING
              | NAME LT STRING
              | NAME LTE STRING
    """
    values = p[3][1:-1].split(",")
    p[0] = {"key": p[1], "method": METHOD_MAPPING[p[2]], "value": values}


def p_condition_number(p):
    """
    condition : NAME EQ NUMBER
              | NAME NEQ NUMBER
              | NAME GT NUMBER
              | NAME GTE NUMBER
              | NAME LT NUMBER
              | NAME LTE NUMBER
    """
    values = p[3].split(",")
    values = [float(value) if "." in value else int(value) for value in values if value]
    p[0] = {"key": p[1], "method": METHOD_MAPPING[p[2]], "value": values}


def p_error(p):
    raise ParseError(f"Syntax error where condition at {p!r}")


conditions_parser = yacc()
