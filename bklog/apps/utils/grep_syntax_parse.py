from ply import lex, yacc

from apps.exceptions import GrepParseError
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
    r'\"(?:\\["\\tnr]|\\[^"]|[^"\\])*\"'
    # 去掉引号
    t.value = t.value[1:-1].replace('\\"', '"')
    return t


def t_SINGLE_QUOTED_STRING(t):  # noqa: F841
    r"""'(?:\\["\\tnr?]|\\[^"]|[^"\\])*'"""
    # 去掉引号
    t.value = t.value[1:-1].replace("\\'", "'")
    return t


def t_RAW_PATTERN(t):  # noqa: F841
    r"""(?:\\[|"'\s\+\?\.\*\{\}\(\)\^\$]|[^\s|"'\\-])+"""
    t.value = t.value.replace("\\ ", " ")
    return t


def t_error(t):  # noqa: F841
    logger.info("lexical parsing failed: illegal character [%s] at position [%s]", t.value, t.lexpos)
    raise GrepParseError(
        GrepParseError.MESSAGE.format(reason=f"illegal character [{t.value}] at position [{t.lexpos}]")
    )


# 构建词法分析器
grep_lexer = lex.lex()


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
    _, pattern = p[2]
    # args中存在E时, 使用egrep命令
    args = args or []
    for arg in args:
        if "E" in arg:
            cmd = "egrep"
    # 默认命令是grep
    p[0] = {"command": cmd or "grep", "args": args, "pattern": pattern}


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


def p_error(p):
    logger.info("syntax parsing failed: illegal character [%s] at position [%s]", p.value, p.lexpos)
    raise GrepParseError(
        GrepParseError.MESSAGE.format(reason=f"illegal character [{p.value}] at position [{p.lexpos}]")
    )


# 构建语法分析器
parser = yacc.yacc()


def grep_parser(input_string):
    return parser.parse(input_string, lexer=grep_lexer.clone())
