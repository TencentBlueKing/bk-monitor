from typing import List

import ply.lex as lex
import ply.yacc as yacc

from apps.utils.log import logger

tokens = ("COMMAND", "ARG", "DOUBLE_QUOTED_STRING", "SINGLE_QUOTED_STRING", "RAW_PATTERN", "PIPE")

# 定义词法规则
t_PIPE = r"\|"  # noqa: F841
t_ignore = " \t"  # noqa: F841


def t_COMMAND(t):  # noqa: F841
    r"""(grep|egrep)\b"""
    return t


def t_ARG(t):  # noqa: F841
    r"""-([a-zA-Z0-9]+)\b"""
    # 去掉前面的'-'
    t.value = t.value[1:]
    return t


def t_DOUBLE_QUOTED_STRING(t):  # noqa: F841
    r'\"(?:\\["\\tnr?]|\\[^"]|[^"\\])*\"'
    # 处理双引号内的转义字符
    t.value = t.value[1:-1]
    return t


def t_SINGLE_QUOTED_STRING(t):  # noqa: F841
    r"""'(\\['\\tnr]|\\x[0-9a-fA-F]{2}|[^'\\])*'"""
    # 单引号字符串不处理转义，直接去掉引号
    t.value = t.value[1:-1]
    return t


def t_RAW_PATTERN(t):  # noqa: F841
    r"""(?:\\[|"'\s\\]|[^\s|"'\\-])+"""
    if '\\' in t.value:
        t.value = (
            t.value.replace(r'\ ', ' ')
            .replace(r'\|', '|')
            .replace(r'\"', '"')
            .replace(r"\'", "'")
            .replace(r'\\\\', '\\')
        )
    return t


def t_error(t):  # noqa: F841
    # 跳过无法识别的字符
    logger.info("Illegal character: [%s]'", t.value[0])
    t.lexer.skip(1)


# 构建词法分析器
lexer = lex.lex()


# 定义语法规则
def p_commands(p):  # noqa: F841
    """commands : command
    | command PIPE commands"""
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = [p[1]] + p[3]


def p_command(p):  # noqa: F841
    """command : cmd_prefix args_pattern"""
    cmd, args = p[1]
    pattern_args, pattern = p[2]
    result = []
    i = 0
    # 对pattern进行转义
    while i < len(pattern):
        if pattern[i] == '\\' and i + 1 < len(pattern):
            if cmd != "egrep" and pattern[i + 1] in ["+", "?", "{", "}"]:
                # 直接取转义后的字符
                result.append(pattern[i + 1])
                i += 2
            elif pattern[i + 1] in ["."]:
                result.append(pattern[i])
                i += 1
            else:
                # 直接取转义后的字符
                result.append(pattern[i + 1])
                i += 2
        else:
            result.append(pattern[i])
            i += 1

    pattern = "".join(result)
    # 默认命令是grep
    p[0] = {"command": cmd or "grep", "args": (args or []) + (pattern_args or []), "pattern": pattern}


def p_cmd_prefix(p):  # noqa: F841
    """cmd_prefix :
    | COMMAND
    | COMMAND args
    | args"""
    if len(p) == 1:
        p[0] = (None, None)
    elif p.slice[1].type == "COMMAND":
        if len(p) == 2:
            p[0] = (p[1], None)
        else:
            p[0] = (p[1], p[2])
    else:
        p[0] = (None, p[1])


def p_args_pattern(p):  # noqa: F841
    """args_pattern : args pattern
    | pattern"""
    if len(p) == 3:
        p[0] = (p[1], p[2])
    else:
        p[0] = (None, p[1])


def p_args(p):  # noqa: F841
    """args : ARG
    | ARG args"""
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = [p[1]] + p[2]


def p_pattern_string(p):  # noqa: F841
    """pattern : DOUBLE_QUOTED_STRING
    | SINGLE_QUOTED_STRING"""
    p[0] = p[1]


def p_pattern_raw(p):  # noqa: F841
    """pattern : RAW_PATTERN"""
    # 直接将字符串值赋给pattern节点
    p[0] = p[1]


# 构建并返回语法分析器
parser = yacc.yacc()


def grep_parser(input_string):
    """解析输入字符串并返回结构化数据"""
    return parser.parse(input_string, lexer=lexer)


def convert_to_where_clause(commands: List[dict]):
    """
    将解析后的grep命令转换为 doris SQL的where子句
    :param commands: 解析后的grep命令列表
    :return: 查询条件
    """
    conditions = []

    for cmd in commands:
        args = cmd["args"]
        pattern = cmd["pattern"]

        # 构建正则表达式条件
        regex_op = "REGEXP"
        if "v" in args:
            regex_op = f"NOT {regex_op}"

        field_name = "log"
        if "i" in args:
            field_name = "LOWER(log)"

        # 构建条件表达式
        condition = f"{field_name} {regex_op} '{pattern}'"
        conditions.append(condition)

    # 组合所有条件
    where_clause = " AND ".join(conditions)
    return f"WHERE {where_clause}"
