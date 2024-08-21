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

tokens = ["FUNCTION", "LEFT_PARENTHESES", "RIGHT_PARENTHESES", "COMMA", "STRING", "NUMBER", "FLOAT", "TIME"]

t_ignore = " \t"

t_LEFT_PARENTHESES = r"\("
t_RIGHT_PARENTHESES = r"\)"
t_COMMA = r","
t_FUNCTION = r"[a-zA-Z][a-zA-Z_0-9]*"
t_NUMBER = r"\d+"
t_FLOAT = r"\d+\.\d+"
t_TIME = r"(\d+[smhdw])+"
t_STRING = r'("([^"]|\\")*")|(\'([^\']|\\\')*\')'


def t_error(t):
    print(f"Illegal character {t.value[0]!r}")
    t.lexer.skip(1)


function_lexer = lex()


def p_expression(p):
    """
    expression : FUNCTION LEFT_PARENTHESES params RIGHT_PARENTHESES
               | FUNCTION
               | FUNCTION LEFT_PARENTHESES RIGHT_PARENTHESES
    """
    p[0] = (p[1], p[3] if len(p) > 4 else [])


def p_params(p):
    """
    params : params COMMA param
    """
    p[0] = (*p[1], p[3])


def p_params_param(p):
    """
    params : param
    """
    p[0] = (p[1],)


def p_string(p):
    """
    param : STRING
    """
    p[0] = p[1][1:-1]


def p_number(p):
    """
    param : NUMBER
    """
    p[0] = int(p[1])


def p_float(p):
    """
    param : FLOAT
    """
    p[0] = float(p[1])


def p_time(p):
    """
    param : TIME
    """
    p[0] = p[1]


def p_error(p):
    from bkmonitor.as_code.ply.error import ParseError

    raise ParseError(f"Syntax error when parse function at {p!r}")


function_parser = yacc()
