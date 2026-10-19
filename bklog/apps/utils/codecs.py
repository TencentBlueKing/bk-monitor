import codecs


def unicode_str_encode(s):
    """
    将字符串转换为unicode编码
    例如: \t -> \\t
    """
    return codecs.encode(s, "unicode_escape").decode("utf-8")


def unicode_str_decode(s):
    """
    将unicode编码的字符串转换为正常字符串
    例如: \\t -> \t
    """
    return codecs.decode(s, "unicode_escape")


def unicode_str_decode_keep_non_ascii(s):
    """
    将字符串中的转义序列还原，同时保留原样输入的非 ASCII 字符
    例如: \\t，。 -> \t，。（unicode_str_decode 会把中文按 latin-1 解成乱码）
    """
    return s.encode("latin-1", "backslashreplace").decode("unicode_escape")
