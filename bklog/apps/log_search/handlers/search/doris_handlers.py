import ply.lex as lex
import ply.yacc as yacc

tokens = ('COMMAND', 'ARG', 'DOUBLE_QUOTED_STRING', 'SINGLE_QUOTED_STRING', 'RAW_PATTERN', 'PIPE')


def create_lexer():
    # 定义词法标记
    t_PIPE = r'\|'  # noqa: F841
    t_ignore = ' \t'  # noqa: F841

    def t_COMMAND(t):  # noqa: F841
        r"""(grep|egrep)\b"""
        return t

    def t_ARG(t):  # noqa: F841
        r"""-([ivE]+)\b"""
        t.value = t.value[1:]  # 去掉前面的'-'
        return t

    def t_DOUBLE_QUOTED_STRING(t):  # noqa: F841
        r'\"(?:\\["\\tnr?]|\\[^"]|[^"\\])*\"'
        # 处理双引号内的转义字符
        content = t.value[1:-1]

        result = []
        i = 0
        while i < len(content):
            if content[i] == '\\' and i + 1 < len(content):
                # 处理所有转义字符：将 \X 替换为 X（无论X是什么）
                result.append(content[i + 1])  # 直接取转义后的字符
                i += 2
            else:
                result.append(content[i])
                i += 1

        t.value = ''.join(result)
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

    # 错误处理
    def t_error(t):  # noqa: F841
        print(f"Illegal character '{t.value[0]}'")
        t.lexer.skip(1)

    # 构建并返回词法分析器
    return lex.lex()


def create_parser():
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

        p[0] = {'command': cmd or 'grep', 'args': (args or []) + (pattern_args or []), 'pattern': pattern}  # 默认命令是grep

    def p_cmd_prefix(p):  # noqa: F841
        """cmd_prefix :
        | COMMAND
        | COMMAND args
        | args"""
        if len(p) == 1:
            p[0] = (None, None)
        elif p.slice[1].type == 'COMMAND':
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
        p[0] = p[1]

    # 错误处理
    def p_error(p):  # noqa: F841
        if p:
            raise SyntaxError(f"Syntax error at '{p.value}'")
        else:
            raise SyntaxError("Syntax error at EOF")

    # 构建并返回语法分析器
    parser = yacc.yacc()
    return parser


class GrepParser:
    def __init__(self):
        self.lexer = create_lexer()
        self.parser = create_parser()

    def parse(self, input_string):
        """解析输入字符串并返回结构化数据"""
        return self.parser.parse(input_string, lexer=self.lexer)


if __name__ == '__main__':
    obj = GrepParser()
    # test_input = 'grep -v pattern | egrep "test" | xx'
    # test_input = 'grep "hello"'
    test_input = 'egrep "error|warning"'
    result = obj.parse(test_input)
    print(result)
