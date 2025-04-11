import ply.lex as lex
import ply.yacc as yacc

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
    t.value = t.value[1:-1]
    return t


def t_SINGLE_QUOTED_STRING(t):  # noqa: F841
    r"""'(?:\\["\\tnr?]|\\[^"]|[^"\\])*'"""
    # 去掉引号
    t.value = t.value[1:-1]
    return t


def t_RAW_PATTERN(t):  # noqa: F841
    r"""(?:\\[|"'\s\+\?\.\*\{\}\(\)\^\$]|[^\s|"'\\-])+"""
    return t


def t_error(t):  # noqa: F841
    logger.info("lexical parsing failed: illegal character [%s] at position [%s]", t.value, t.lexpos)
    raise GrepParseError()


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
    # 对pattern中的转义字符进行处理
    while i < len(pattern):
        if pattern[i] == '\\' and i + 1 < len(pattern):
            if cmd != "egrep" and pattern[i + 1] in ["+", "?", "{", "}"]:
                # 直接取转义后的字符
                result.append(pattern[i + 1])
                i += 2
            elif cmd == "egrep":
                # grep命令下需要在这些字符前加上反斜杠
                result.append(pattern[i])
                i += 1
            elif pattern[i + 1] in [".", "*", "^", "$"]:
                result.append(pattern[i])
                i += 1
            else:
                # 直接取转义后的字符
                result.append(pattern[i + 1])
                i += 2
        else:
            if cmd != "egrep" and pattern[i] in ["+", "?", "{", "}"]:
                # grep命令下需要在这些字符前加上反斜杠
                result.append(f"\\{pattern[i]}")
                i += 1
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


def p_error(p):
    logger.info("syntax parsing failed: illegal character [%s] at position [%s]", p.value, p.lexpos)
    raise GrepParseError()


# 延迟初始化词法分析器
_base_lexer = None


def get_base_lexer():
    global _base_lexer
    if _base_lexer is None:
        _base_lexer = lex.lex()
    return _base_lexer


# 构建并返回语法分析器
parser = yacc.yacc()


def grep_parser(input_string):
    # 克隆 lexer
    local_lexer = get_base_lexer().clone()
    return parser.parse(input_string, lexer=local_lexer)
